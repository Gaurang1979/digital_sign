import frappe
from frappe import _
from frappe.utils.pdf import get_pdf

from digital_sign.digital_sign.boot import get_config
from digital_sign.digital_sign.signing import (
	SigningError,
	build_signer,
	build_stamp_text,
	certificate_details,
	locate_anchor,
	open_session,
	sign_pdf_bytes,
)


def _get_doc_config(doctype):
	config = get_config()
	if doctype not in config:
		frappe.throw(_("Digital signing is not enabled for {0}").format(doctype))
	return config[doctype]


def _check_permission(doctype, docname):
	config = _get_doc_config(doctype)
	user_roles = set(frappe.get_roles())
	allowed_roles = set(config.get("allowed_roles") or [])

	if not allowed_roles:
		frappe.throw(
			_("No roles are configured to sign {0}. Check Digital Sign Document Config.").format(doctype)
		)
	if not (user_roles & allowed_roles):
		frappe.throw(_("You are not permitted to digitally sign {0}").format(doctype), frappe.PermissionError)

	doc = frappe.get_doc(doctype, docname)
	if doc.docstatus != 1:
		frappe.throw(_("Only submitted documents can be digitally signed"))

	return doc, config


def _latest_signed_file(doctype, docname):
	return frappe.db.get_value(
		"Digital Signature Log",
		{"reference_doctype": doctype, "reference_name": docname, "status": "Success"},
		"signed_file",
		order_by="signed_on desc",
	)


@frappe.whitelist()
def get_signature_status(doctype, docname):
	"""Has this document already been signed? Drives the disabled
	'Signed' button on the form."""
	log = frappe.db.get_value(
		"Digital Signature Log",
		{"reference_doctype": doctype, "reference_name": docname, "status": "Success"},
		["name", "signed_by", "signed_on"],
		order_by="signed_on desc",
		as_dict=True,
	)
	if not log:
		return {"signed": False}
	return {
		"signed": True,
		"log": log.name,
		"signed_by": log.signed_by,
		"signed_on": str(log.signed_on),
	}


@frappe.whitelist()
def test_anchor(doctype, docname):
	"""Report whether the configured anchor text is found in this
	document's print format, and where -- without signing."""
	doc, config = _check_permission(doctype, docname)

	pdf_bytes = get_pdf(frappe.get_print(doctype, docname, print_format=None))
	try:
		page_index, x, y = locate_anchor(pdf_bytes, config["anchor_text"])
	except SigningError as e:
		return {"found": False, "message": str(e)}

	return {"found": True, "page": page_index + 1, "x": round(x, 1), "y": round(y, 1)}


@frappe.whitelist()
def sign_document(doctype, docname, reason=None):
	doc, config = _check_permission(doctype, docname)

	if _latest_signed_file(doctype, docname):
		frappe.throw(_("This document has already been digitally signed."))

	settings = frappe.get_single("Digital Sign Settings")
	if not settings.enabled:
		frappe.throw(_("Digital Sign Settings is disabled"))

	reason = reason or settings.default_reason or "Digitally Signed"
	location = settings.default_location or ""

	pdf_bytes = get_pdf(frappe.get_print(doctype, docname, print_format=None))

	try:
		page_index, x, y = locate_anchor(pdf_bytes, config["anchor_text"])
	except SigningError as e:
		frappe.throw(str(e))

	# The token allows one operation at a time, so the session is opened
	# per signing request and always closed, even on failure -- a leaked
	# session would block every later signature until a restart.
	session = None
	try:
		session = open_session(settings)
		signer = build_signer(session, settings)
		cert_info = certificate_details(signer)
		stamp_text = build_stamp_text(settings, reason, location, cert_info)

		signed_bytes = sign_pdf_bytes(
			pdf_bytes=pdf_bytes,
			signer=signer,
			page=page_index + 1,
			x=x,
			y=y,
			width=config["width"],
			height=config["height"],
			stamp_text=stamp_text,
			reason=reason,
			location=location,
		)
	except SigningError as e:
		frappe.throw(str(e))
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Digital Sign: signing failed")
		frappe.throw(_("Signing failed: {0}").format(e))
	finally:
		if session is not None:
			try:
				session.close()
			except Exception:
				pass

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{docname}-signed.pdf",
			"attached_to_doctype": doctype,
			"attached_to_name": docname,
			"is_private": 1,
			"content": signed_bytes,
		}
	).insert(ignore_permissions=True)

	log = frappe.get_doc(
		{
			"doctype": "Digital Signature Log",
			"reference_doctype": doctype,
			"reference_name": docname,
			"signed_by": frappe.session.user,
			"signed_on": frappe.utils.now_datetime(),
			"page": page_index + 1,
			"x": x,
			"y": y,
			"signed_file": file_doc.file_url,
			"certificate_subject": cert_info["subject"],
			"certificate_serial": cert_info["serial"],
			"status": "Success",
		}
	).insert(ignore_permissions=True)

	frappe.db.commit()
	return {"ok": True, "log": log.name, "file_url": file_doc.file_url}


@frappe.whitelist()
def download_pdf(doctype, name, format=None, doc=None, no_letterhead=0, letterhead=None, **kwargs):
	"""Override for frappe.www.printview.download_pdf: serve the signed
	PDF once one exists, else fall through to Frappe's own handler.

	NOTE: confirm this signature matches your Frappe version --
	  bench --site <site> console
	  >>> import inspect, frappe.www.printview as pv
	  >>> inspect.signature(pv.download_pdf)
	"""
	signed_file_url = _latest_signed_file(doctype, name)

	if signed_file_url:
		file_doc = frappe.get_doc("File", {"file_url": signed_file_url})
		frappe.local.response.filename = f"{name}-signed.pdf"
		frappe.local.response.filecontent = file_doc.get_content()
		frappe.local.response.type = "download"
		return

	from frappe.www.printview import download_pdf as original_download_pdf

	return original_download_pdf(
		doctype=doctype,
		name=name,
		format=format,
		doc=doc,
		no_letterhead=no_letterhead,
		letterhead=letterhead,
		**kwargs,
	)
