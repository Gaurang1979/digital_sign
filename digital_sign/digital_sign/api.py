import base64

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


def _templates_for(doctype):
	config = get_config()
	templates = config.get(doctype) or []
	if not templates:
		frappe.throw(_("Digital signing is not enabled for {0}").format(doctype))
	return templates


def _get_template(doctype, config_name=None):
	"""Resolve one specific template. If config_name isn't given, this
	only succeeds when the doctype has exactly one enabled template -
	callers with more than one must specify which."""
	templates = _templates_for(doctype)

	if config_name:
		for t in templates:
			if t["config_name"] == config_name:
				return t
		frappe.throw(_("{0} is not an enabled Digital Sign Document Config for {1}").format(config_name, doctype))

	if len(templates) > 1:
		frappe.throw(_("{0} has more than one signing template configured - specify which one.").format(doctype))
	return templates[0]


def _check_permission(doctype, docname, config_name=None):
	"""Permission check scoped to one specific template's own allowed
	roles (not a union across every template for the doctype)."""
	template = _get_template(doctype, config_name)
	user_roles = set(frappe.get_roles())
	allowed_roles = set(template.get("allowed_roles") or [])

	if not allowed_roles:
		frappe.throw(
			_("No roles are configured to sign with {0}. Check Digital Sign Document Config.").format(
				template["config_name"]
			)
		)
	if not (user_roles & allowed_roles):
		frappe.throw(_("You are not permitted to digitally sign {0}").format(doctype), frappe.PermissionError)

	doc = frappe.get_doc(doctype, docname)
	if doc.docstatus != 1:
		frappe.throw(_("Only submitted documents can be digitally signed"))

	return doc, template


def _check_permission_any(doctype, docname):
	"""For actions (like revoke) that aren't tied to a specific signing
	template - allowed if the user holds an allowed role on ANY enabled
	template for this doctype."""
	templates = _templates_for(doctype)
	user_roles = set(frappe.get_roles())
	allowed_roles = set()
	for t in templates:
		allowed_roles |= set(t.get("allowed_roles") or [])

	if not (user_roles & allowed_roles):
		frappe.throw(_("You are not permitted to manage digital signatures on {0}").format(doctype), frappe.PermissionError)

	doc = frappe.get_doc(doctype, docname)
	if doc.docstatus != 1:
		frappe.throw(_("Only submitted documents can be digitally signed"))
	return doc


def _latest_log(doctype, docname):
	"""Most recent Digital Signature Log entry regardless of status - this
	is the source of truth for current state. A document can be signed,
	then revoked, then signed again; each is its own immutable row, and
	only the latest one matters for "is this currently signed"."""
	return frappe.db.get_value(
		"Digital Signature Log",
		{"reference_doctype": doctype, "reference_name": docname},
		["name", "status", "signed_by", "performed_by_name", "signed_on", "signed_file"],
		order_by="signed_on desc",
		as_dict=True,
	)


def _render_pdf(doctype, docname, template):
	return get_pdf(frappe.get_print(doctype, docname, print_format=template.get("print_format")))


@frappe.whitelist()
def get_signature_status(doctype, docname):
	"""Currently signed, or not - drives which button(s) the form shows."""
	log = _latest_log(doctype, docname)
	if not log or log.status != "Success":
		return {"signed": False}
	return {
		"signed": True,
		"log": log.name,
		"signed_by": log.signed_by,
		"performed_by_name": log.performed_by_name or log.signed_by,
		"signed_on": str(log.signed_on),
	}


@frappe.whitelist()
def test_anchor(doctype, docname, config_name=None):
	"""Report whether the configured anchor text is found in this
	document's print format, and where -- without signing."""
	doc, template = _check_permission(doctype, docname, config_name)

	pdf_bytes = _render_pdf(doctype, docname, template)
	try:
		page_index, x, y = locate_anchor(pdf_bytes, template["anchor_text"])
	except SigningError as e:
		return {"found": False, "message": str(e)}

	return {"found": True, "page": page_index + 1, "x": round(x, 1), "y": round(y, 1)}


@frappe.whitelist()
def sign_document(doctype, docname, config_name=None):
	doc, template = _check_permission(doctype, docname, config_name)

	existing = _latest_log(doctype, docname)
	if existing and existing.status == "Success":
		frappe.throw(_("This document is already digitally signed. Revoke the existing signature first."))

	settings = frappe.get_single("Digital Sign Settings")
	if not settings.enabled:
		frappe.throw(_("Digital Sign Settings is disabled"))

	reason = settings.default_reason or "Digitally Signed"
	location = settings.default_location or ""

	pdf_bytes = _render_pdf(doctype, docname, template)

	try:
		page_index, x, y = locate_anchor(pdf_bytes, template["anchor_text"])
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
			width=template["width"],
			height=template["height"],
			stamp_text=stamp_text,
			reason=reason,
			location=location,
			background_opacity=(settings.stamp_background_opacity or 50) / 100,
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

	log = frappe.get_doc(
		{
			"doctype": "Digital Signature Log",
			"reference_doctype": doctype,
			"reference_name": docname,
			"signed_by": frappe.session.user,
			"performed_by_name": frappe.utils.get_fullname(frappe.session.user),
			"signed_on": frappe.utils.now_datetime(),
			"page": page_index + 1,
			"x": x,
			"y": y,
			# Stored inline (base64) rather than as a File attached to the
			# business document - keeps it out of that document's own
			# Attachments list and avoids a second, duplicate on-disk copy.
			"signed_file": base64.b64encode(signed_bytes).decode("ascii"),
			"certificate_subject": cert_info["subject"],
			"certificate_serial": cert_info["serial"],
			"status": "Success",
			"remarks": f"Signed using template: {template['config_name']}",
		}
	).insert(ignore_permissions=True)

	frappe.db.commit()
	return {"ok": True, "log": log.name}


@frappe.whitelist()
def revoke_signature(doctype, docname, reason=None):
	"""Records a revocation as a new, separate Digital Signature Log entry
	(the log is immutable - existing entries are never edited or deleted).
	The previously signed PDF stays on that earlier entry as a historical
	record; it just stops being served by download_pdf / Print once
	revoked, and the document becomes eligible to be signed again."""
	_check_permission_any(doctype, docname)

	existing = _latest_log(doctype, docname)
	if not existing or existing.status != "Success":
		frappe.throw(_("This document is not currently signed - nothing to revoke."))

	log = frappe.get_doc(
		{
			"doctype": "Digital Signature Log",
			"reference_doctype": doctype,
			"reference_name": docname,
			"signed_by": frappe.session.user,
			"performed_by_name": frappe.utils.get_fullname(frappe.session.user),
			"signed_on": frappe.utils.now_datetime(),
			"status": "Revoked",
			"remarks": reason or "",
		}
	).insert(ignore_permissions=True)

	frappe.db.commit()
	return {"ok": True, "log": log.name}


@frappe.whitelist()
def download_pdf(doctype, name, format=None, doc=None, no_letterhead=0, letterhead=None, **kwargs):
	"""Override for frappe.www.printview.download_pdf: serve the signed
	PDF once one exists (and hasn't since been revoked), else fall
	through to Frappe's own handler.

	NOTE: confirm this signature matches your Frappe version --
	  bench --site <site> console
	  >>> import inspect, frappe.www.printview as pv
	  >>> inspect.signature(pv.download_pdf)
	"""
	log = _latest_log(doctype, name)

	if log and log.status == "Success" and log.signed_file:
		frappe.local.response.filename = f"{name}-signed.pdf"
		frappe.local.response.filecontent = base64.b64decode(log.signed_file)
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


@frappe.whitelist()
def check_anchor_for_config(document_type, print_format, anchor_text):
	"""Used by Digital Sign Document Config's own pre-save validation
	(see digital_sign_document_config.py) - tests the anchor against the
	most recently submitted document of this type, since a config row
	isn't tied to any one document itself."""
	sample_name = frappe.db.get_value(document_type, {"docstatus": 1}, "name", order_by="modified desc")
	if not sample_name:
		return {"checked": False, "message": _("No submitted {0} exists yet to test against.").format(document_type)}

	pdf_bytes = get_pdf(frappe.get_print(document_type, sample_name, print_format=print_format))
	try:
		page_index, x, y = locate_anchor(pdf_bytes, anchor_text)
	except SigningError as e:
		return {"checked": True, "found": False, "sample": sample_name, "message": str(e)}

	return {"checked": True, "found": True, "sample": sample_name, "page": page_index + 1, "x": round(x, 1), "y": round(y, 1)}
