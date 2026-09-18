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


def _cert_summary(cert) -> dict:
	"""Shared by certificate_details() (one specific cert, already
	selected) and list_certificates() (every cert on the token) - so the
	timezone conversion and expiry logic can't drift out of sync between
	the two."""
	# X.509 certificates always encode validity dates in UTC.
	# asn1crypto's .native gives a timezone-aware UTC datetime - str() on
	# that directly shows raw UTC with a "+00:00" suffix, which reads as
	# flatly wrong to anyone not thinking in UTC (a ~5.5 hour gap for an
	# India-based site). Convert to the site's own timezone before
	# formatting.
	valid_until_utc = cert["tbs_certificate"]["validity"]["not_after"].native
	valid_until_local = frappe.utils.convert_utc_to_system_timezone(valid_until_utc)
	is_expired = valid_until_utc <= datetime.now(valid_until_utc.tzinfo or timezone.utc)
	try:
		is_ca = bool(cert.ca)
	except Exception:
		is_ca = None
	return {
		"subject": cert.subject.human_friendly,
		"serial": str(cert.serial_number),
		"valid_until": valid_until_local.strftime("%Y-%m-%d %H:%M:%S") + f" ({frappe.utils.get_system_timezone()})",
		"is_expired": is_expired,
		"is_ca": is_ca,
	}


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
	updated by hand to the new one (see list_certificates() below, which
	is what "Browse Certificates on Token" uses to make that a point-and
	-click fix instead). is_expired below exists specifically to catch
	and surface that situation loudly instead of silently signing with a
	dead certificate.
	"""
	try:
		return _cert_summary(signer.signing_cert)
	except Exception:
		return {"subject": "", "serial": "", "valid_until": "", "is_expired": None}


def list_certificates(session) -> list:
	"""Every certificate object currently on the token (not just the one
	Digital Sign Settings is configured to use) - lets the admin actually
	see what's there and pick one, rather than having to run
	`pkcs11-tool -O` externally and paste a hex ID by hand. Used by the
	"Browse Certificates on Token" button in Digital Sign Settings."""
	import pkcs11
	from asn1crypto import x509

	certs = []
	for obj in session.get_objects({pkcs11.Attribute.CLASS: pkcs11.ObjectClass.CERTIFICATE}):
		try:
			cert_id = obj[pkcs11.Attribute.ID]
			label = obj[pkcs11.Attribute.LABEL]
			cert = x509.Certificate.load(obj[pkcs11.Attribute.VALUE])
			certs.append(
				{
					"id": cert_id.hex(),
					"label": label,
					**_cert_summary(cert),
				}
			)
		except Exception:
			continue  # not everything on a token parses as a usable end-entity cert - skip, don't fail the whole list
	return certs


DEFAULT_STAMP_WIDTH = 160
DEFAULT_STAMP_HEIGHT = 80


def locate_anchor(pdf_bytes: bytes, anchor_text: str):
	"""Find anchor_text in the rendered PDF; return (page_index, x, y,
	width, height) in PDF user-space points (origin bottom-left) for the
	stamp's TOP-left corner and size - the stamp is drawn extending
	downward-right from (x, y), matching where an anchor naturally sits
	right after a line of text in the HTML (immediately below that
	line), so the HTML anchor should be styled with top:0 (not bottom:0)
	within its reserved box. See sign_pdf_bytes() for the box math.

	Size is optional and lives ENTIRELY in the Print Format's own HTML -
	nothing needs to be typed into anchor_text (the Digital Sign Print
	Template field) to match. If the HTML's anchor carries a :WxH suffix
	right before its closing ## (e.g. ##DIGITAL_SIGN_ANCHOR:200x100##),
	that's detected directly from what's actually rendered on the page;
	anchor_text itself can stay as the plain, unsized marker for every
	template regardless of what size each one's HTML actually uses.
	Falls back to a default size when no :WxH is present anywhere.
	"""
	import fitz  # PyMuPDF

	anchor_text = anchor_text.strip()
	if anchor_text.endswith("##"):
		size_pattern = re.compile(re.escape(anchor_text[:-2]) + r"(?::(\d+)x(\d+))?" + re.escape("##"))
	else:
		size_pattern = re.compile(re.escape(anchor_text) + r"(?::(\d+)x(\d+))?")

	pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
	try:
		for page_index in range(pdf.page_count):
			page = pdf[page_index]

			# Discover what's actually there (base marker, or base marker
			# with a :WxH size embedded) via the page's extracted text -
			# search_for() needs an exact string, and the whole point
			# here is that we don't know the exact string (the size) in
			# advance. PDF text extraction can introduce or collapse
			# whitespace, so try both the raw and whitespace-normalised
			# page text.
			page_text = page.get_text()
			m = size_pattern.search(page_text) or size_pattern.search(re.sub(r"\s+", " ", page_text))
			if not m:
				continue  # not on this page - try the next one

			width = int(m.group(1)) if m.group(1) else DEFAULT_STAMP_WIDTH
			height = int(m.group(2)) if m.group(2) else DEFAULT_STAMP_HEIGHT

			# Now get this exact matched text's on-page position. Try it
			# as found, then a whitespace-normalised variant, same
			# reasoning as above but for search_for() specifically.
			matched_text = m.group(0)
			candidates = [matched_text]
			normalised = re.sub(r"\s+", " ", matched_text).strip()
			if normalised != matched_text:
				candidates.append(normalised)

			for candidate in candidates:
				matches = page.search_for(candidate)
				if matches:
					rect = matches[0]
					# fitz rects are top-down; flip to PDF bottom-up space.
					# rect.y0 (not y1) - the TOP of the anchor text's own
					# glyphs - since the stamp now extends downward-right
					# from this point, matching an anchor styled with
					# top:0 within its reserved box (see locate_anchor's
					# own docstring and sign_pdf_bytes for why).
					return page_index, rect.x0, page.rect.height - rect.y0, width, height

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


def _fit_stamp_box(stamp_text: str, declared_height: float):
	"""Computes the stamp's actual drawn height and text styling so it
	renders TIGHT to its actual content - no top/bottom padding or
	centering slack left over just because the HTML declared more space
	than the current number of enabled stamp fields (signer/reason/
	location/date/certificate serial - Digital Sign Settings) actually
	needs.

	declared_height (from the HTML's :WxH) acts purely as an upper
	bound: if the content needs less than that, the stamp is drawn at
	its own tight-fit height instead of stretched/centered to fill the
	full declared space. If it needs more, the font shrinks until it
	fits within declared_height (can't exceed what's declared). Any
	breathing room around the stamp - top, bottom, or between it and
	surrounding content - is left entirely to the HTML's own margin;
	nothing is added here.

	Returns (text_box_style, actual_height) - actual_height is what
	sign_pdf_bytes should use for the stamp's own box, not
	declared_height directly.
	"""
	num_lines = stamp_text.count("\n") + 1
	leading, font_size = 8, 7  # compact, legible default

	tight_height = num_lines * leading
	if tight_height <= declared_height:
		# Fits comfortably at the default size - draw at exactly the
		# tight-fit height, not the (possibly larger) declared one.
		actual_height = tight_height
	else:
		# More lines than declared_height comfortably fits at the
		# default size - shrink the font until it does. This is the one
		# case where the drawn height can't be smaller than what's
		# declared, since the content genuinely needs that much room.
		leading = max(declared_height / num_lines, 4)
		font_size = max(leading - 1, 3)
		actual_height = declared_height

	# text_sep=0: pyHanko's own internal padding inside the box
	# (default 10) is exactly the kind of extra space being removed here.
	return TextBoxStyle(font_size=font_size, leading=leading, text_sep=0), actual_height


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

	(x, y) is the TOP-left corner of the stamp box - it extends
	downward-right from there, matching where an anchor naturally sits
	right after a line of text in the HTML (immediately below that
	line). height is an UPPER BOUND, not the drawn height: the stamp is
	actually drawn tight to however many lines stamp_text has (via
	_fit_stamp_box()), so it doesn't render with empty top/bottom space
	just because height declared more room than the current content
	needs - any breathing room is expected to come from the HTML's own
	margin around the reserved box, not from padding added here.

	reason/location go into the signature's PDF metadata (what Adobe's
	signature-properties panel shows); stamp_text controls what is
	visually printed inside the stamp box, with a green tick watermark
	behind it at background_opacity (0-1, from Digital Sign Settings).
	"""
	text_box_style, actual_height = _fit_stamp_box(stamp_text, height)

	writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))

	field_name = "DigitalSignature"
	fields.append_signature_field(
		writer,
		fields.SigFieldSpec(
			sig_field_name=field_name,
			on_page=max(page - 1, 0),
			box=(x, y - actual_height, x + width, y),
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
		# text_box_style, actual_height computed together above by
		# _fit_stamp_box() - the box itself is now sized tight to the
		# content (actual_height), so there's no leftover top/bottom
		# space for centering to distribute in the first place.
		text_box_style=text_box_style,
		# Centers the inner text box (as a block) within the full stamp
		# box horizontally - width still comes from the HTML as
		# declared, so this keeps short lines centered within that width
		# rather than pinned to the left edge. background_layout
		# defaults to the same MID/MID centering, so the tick watermark
		# centers consistently too.
		inner_content_layout=SimpleBoxLayoutRule(x_align=AxisAlignment.ALIGN_MID, y_align=AxisAlignment.ALIGN_MID),
	)
	pdf_signer = signers.PdfSigner(meta, signer=signer, stamp_style=stamp_style)

	out = io.BytesIO()
	pdf_signer.sign_pdf(writer, output=out)
	return out.getvalue()
