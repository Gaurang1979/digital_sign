"""
PDF cryptographic signing engine, built on pyHanko + PKCS#11.

Signs using a private key held on a hardware USB token (DSC token) via
the token vendor's PKCS#11 library. The private key never leaves the
token -- signing happens inside the token's secure chip.

Verified working against:
  Token:  Hypersecu HYP2003 (Capricorn DSC, CCA India chain)
  Module: /opt/hypersecu/libcastle_v2.so.1.0.0
  pyHanko 0.36.2

The token must be physically plugged into the ERPNext server, and
pcscd must be running, for signing to work.
"""

import io
import os
import re
from datetime import datetime, timezone

import frappe

from pyhanko.pdf_utils.images import PdfImage
from pyhanko.pdf_utils.layout import AxisAlignment, SimpleBoxLayoutRule
from pyhanko.sign import fields, signers
from pyhanko.sign.pkcs11 import PKCS11Signer, open_pkcs11_session
from pyhanko.sign.signers.pdf_signer import PdfSignatureMetadata
from pyhanko.stamp import TextStampStyle
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.text import TextBoxStyle


class SigningError(Exception):
	pass


def _parse_id(value: str):
	"""Token object IDs are shown by pkcs11-tool as hex. Accept either a
	hex string (what the admin pastes from `pkcs11-tool -O`) or plain
	text, and return raw bytes for pyHanko."""
	if not value:
		return None
	value = value.strip()
	try:
		return bytes.fromhex(value)
	except ValueError:
		return value.encode("utf-8")


def open_session(settings):
	"""Open a logged-in PKCS#11 session against the token.

	Caller is responsible for closing it (use `with` via sign_pdf_bytes,
	or close() in a finally block).
	"""
	if not settings.pkcs11_module_path:
		raise SigningError("PKCS#11 module path is not set in Digital Sign Settings")

	pin = settings.get_password("token_pin", raise_exception=False)
	if not pin:
		raise SigningError("Token PIN is not set in Digital Sign Settings")

	try:
		return open_pkcs11_session(
			settings.pkcs11_module_path,
			token_label=settings.token_label or None,
			user_pin=pin,
		)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Digital Sign: PKCS#11 session failed")
		raise SigningError(
			f"Could not open the token: {e}. Check that the USB token is plugged into "
			"the server, pcscd is running, and the PIN is correct."
		)


def build_signer(session, settings):
	"""Build a pyHanko signer bound to the chosen certificate/key on the
	token. Objects are selected by ID (preferred -- labels are often
	blank on DSC tokens) or by label if an ID isn't given."""
	cert_id = _parse_id(settings.certificate_id)
	key_id = _parse_id(settings.key_id) or cert_id

	kwargs = {}
	if cert_id:
		kwargs["cert_id"] = cert_id
		kwargs["key_id"] = key_id
	elif settings.certificate_label:
		kwargs["cert_label"] = settings.certificate_label
		kwargs["key_label"] = settings.key_label or settings.certificate_label
	else:
		raise SigningError(
			"Set either Certificate ID or Certificate Label in Digital Sign Settings "
			"so the correct certificate on the token can be selected."
		)

	try:
		return PKCS11Signer(session, **kwargs)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Digital Sign: signer init failed")
		raise SigningError(f"Could not select the certificate on the token: {e}")


def certificate_details(signer) -> dict:
	"""Human-readable subject/serial/validity for display and audit -
	always read fresh from whatever certificate is currently on the
	token, never cached, so a future certificate renewal (same token, new
	cert) is picked up automatically the next time this runs - no manual
	step needed beyond what already happens on every sign/refresh.

	IMPORTANT CAVEAT: "picked up automatically" only holds if the renewed
	certificate replaced the old one AT THE SAME PKCS#11 object ID. Some
	token renewal tools instead add the new certificate as a NEW object
	with a DIFFERENT ID, leaving the old (now expired) one still present
	- in that case Certificate ID / Private Key ID in Digital Sign
	Settings is still pointing at the stale object and needs to be
	updated by hand to the new one. is_expired below exists specifically
	to catch and surface that situation loudly instead of silently
	signing with a dead certificate.
	"""
	try:
		cert = signer.signing_cert
		# X.509 certificates always encode validity dates in UTC.
		# asn1crypto's .native gives a timezone-aware UTC datetime - str()
		# on that directly (the previous behaviour) shows raw UTC with a
		# "+00:00" suffix, which reads as flatly wrong to anyone not
		# thinking in UTC (a ~5.5 hour gap for an India-based site).
		# Convert to the site's own timezone before formatting.
		valid_until_utc = cert["tbs_certificate"]["validity"]["not_after"].native
		valid_until_local = frappe.utils.convert_utc_to_system_timezone(valid_until_utc)
		is_expired = valid_until_utc <= datetime.now(valid_until_utc.tzinfo or timezone.utc)
		return {
			"subject": cert.subject.human_friendly,
			"serial": str(cert.serial_number),
			"valid_until": valid_until_local.strftime("%Y-%m-%d %H:%M:%S") + f" ({frappe.utils.get_system_timezone()})",
			"is_expired": is_expired,
		}
	except Exception:
		return {"subject": "", "serial": "", "valid_until": "", "is_expired": None}


DEFAULT_STAMP_WIDTH = 160
DEFAULT_STAMP_HEIGHT = 80

_SIZE_PATTERN = re.compile(r":(\d+)x(\d+)")


def _parse_stamp_size(anchor_text: str):
	"""Size lives in the anchor text itself (e.g.
	##DIGITAL_SIGN_ANCHOR:160x80##) - the single source of truth is
	whatever's actually in the Print Format's HTML, not a separate field
	that has to be kept in sync with it by hand. Falls back to a sane
	default for anchors written without the :WxH suffix."""
	m = _SIZE_PATTERN.search(anchor_text)
	if m:
		return int(m.group(1)), int(m.group(2))
	return DEFAULT_STAMP_WIDTH, DEFAULT_STAMP_HEIGHT


def locate_anchor(pdf_bytes: bytes, anchor_text: str):
	"""Find anchor_text in the rendered PDF; return (page_index, x, y,
	width, height) in PDF user-space points (origin bottom-left) for the
	stamp's bottom-left corner and size."""
	import fitz  # PyMuPDF

	width, height = _parse_stamp_size(anchor_text)

	# PDF text extraction can introduce or collapse whitespace when the
	# anchor sits inline next to other text rather than on its own line -
	# try the exact string first, then a whitespace-normalised variant.
	candidates = [anchor_text]
	normalised = re.sub(r"\s+", " ", anchor_text).strip()
	if normalised != anchor_text:
		candidates.append(normalised)

	pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
	try:
		for page_index in range(pdf.page_count):
			page = pdf[page_index]
			for candidate in candidates:
				matches = page.search_for(candidate)
				if matches:
					rect = matches[0]
					# fitz rects are top-down; flip to PDF bottom-up space.
					return page_index, rect.x0, page.rect.height - rect.y1, width, height
		raise SigningError(
			f"Anchor text '{anchor_text}' was not found in the rendered print format. "
			"Add it to the Print Format's HTML (see Digital Sign Document Config). "
			"Common cause: styling the anchor with opacity:0 can make some PDF engines skip "
			"painting it entirely, dropping it from the searchable text layer too - use "
			"color:#ffffff (matching the background) instead."
		)
	finally:
		pdf.close()



def build_stamp_text(settings, reason: str, location: str, cert_info: dict) -> str:
	"""Compose the visible stamp text from the Settings toggles, or use
	the admin's custom template verbatim if one is set."""
	from frappe.utils import now_datetime

	date_str = now_datetime().strftime("%Y-%m-%d %H:%M")

	if settings.custom_stamp_text:
		return settings.custom_stamp_text.format(
			signer_name=settings.signer_name or "",
			date=date_str,
			reason=reason,
			location=location,
			certificate_serial=cert_info.get("serial", ""),
		)

	lines = []
	if settings.include_signer_name:
		lines.append(f"Digitally signed by: {settings.signer_name or ''}")
	if settings.include_reason:
		lines.append(f"Reason: {reason}")
	if settings.include_location and location:
		lines.append(f"Location: {location}")
	if settings.include_date:
		lines.append(f"Date: {date_str}")
	if settings.include_certificate_serial:
		lines.append(f"Cert Serial: {cert_info.get('serial', '')}")

	return "\n".join(lines) if lines else f"Digitally signed by: {settings.signer_name or ''}"


def sign_pdf_bytes(
	pdf_bytes: bytes,
	signer,
	page: int,
	x: float,
	y: float,
	width: float,
	height: float,
	stamp_text: str,
	reason: str = "",
	location: str = "",
	background_opacity: float = 0.5,
) -> bytes:
	"""Embed a visible, cryptographic (PAdES) signature at the given
	page/coordinates. Returns the signed PDF bytes.

	reason/location go into the signature's PDF metadata (what Adobe's
	signature-properties panel shows); stamp_text controls what is
	visually printed inside the stamp box, with a green tick watermark
	behind it at background_opacity (0-1, from Digital Sign Settings).
	"""
	writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))

	field_name = "DigitalSignature"
	fields.append_signature_field(
		writer,
		fields.SigFieldSpec(
			sig_field_name=field_name,
			on_page=max(page - 1, 0),
			box=(x, y, x + width, y + height),
		),
	)

	meta = PdfSignatureMetadata(
		field_name=field_name,
		reason=reason or None,
		location=location or None,
	)

	tick_path = os.path.join(os.path.dirname(__file__), "public", "images", "green_tick.png")
	stamp_style = TextStampStyle(
		stamp_text=stamp_text,
		border_width=0,
		background=PdfImage(tick_path) if os.path.exists(tick_path) else None,
		background_opacity=background_opacity,
		# Default font_size is 10, which with up to 5 lines enabled
		# (signer/reason/location/date/certificate serial) needs ~60-70pt
		# of height just for the text - overflows any reasonably compact
		# stamp box and overlaps whatever sits above/below it in the print
		# format. 7pt keeps all 5 lines legible while actually fitting
		# a ~70-80pt-tall box. pyHanko vertically centers text within
		# the box by default, so a tall-enough reserved HTML box centers
		# the whole stamp automatically - no extra positioning needed.
		text_box_style=TextBoxStyle(font_size=7, leading=8),
		# Centers the inner text box (as a block) within the full stamp
		# box horizontally and vertically - the box itself is exactly
		# (width, height) from the anchor text, so this keeps the stamp
		# content centered within that box rather than pinned to a
		# corner. background_layout defaults to the same MID/MID
		# centering already, so the tick watermark and the text block
		# both center consistently.
		inner_content_layout=SimpleBoxLayoutRule(x_align=AxisAlignment.ALIGN_MID, y_align=AxisAlignment.ALIGN_MID),
	)
	pdf_signer = signers.PdfSigner(meta, signer=signer, stamp_style=stamp_style)

	out = io.BytesIO()
	pdf_signer.sign_pdf(writer, output=out)
	return out.getvalue()
