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

import frappe

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
	"""Human-readable subject/serial/validity for display and audit."""
	try:
		cert = signer.signing_cert
		return {
			"subject": cert.subject.human_friendly,
			"serial": str(cert.serial_number),
			"valid_until": str(cert["tbs_certificate"]["validity"]["not_after"].native),
		}
	except Exception:
		return {"subject": "", "serial": "", "valid_until": ""}


def locate_anchor(pdf_bytes: bytes, anchor_text: str):
	"""Find anchor_text in the rendered PDF; return (page_index, x, y) in
	PDF user-space points (origin bottom-left) for the stamp's
	bottom-left corner."""
	import re

	import fitz  # PyMuPDF

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
					return page_index, rect.x0, page.rect.height - rect.y1
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
	import os

	from pyhanko.pdf_utils.images import PdfImage

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
	)
	pdf_signer = signers.PdfSigner(meta, signer=signer, stamp_style=stamp_style)

	out = io.BytesIO()
	pdf_signer.sign_pdf(writer, output=out)
	return out.getvalue()
