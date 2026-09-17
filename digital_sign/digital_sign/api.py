import base64
import inspect

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


def _render_pdf_isolated(doctype, docname, print_format):
	"""frappe.get_print() can internally route through Frappe's website
	printview page renderer for certain print formats (confirmed: some
	e-invoice-style formats do this, "Sales Order Final" apparently
	doesn't), and that path reads doctype/name from frappe.form_dict - the
	CURRENT REQUEST's global state - rather than from the arguments
	passed to get_print() directly. Calling this from inside an unrelated
	request (e.g. the anchor pre-check running nested inside a Document
	Config save) leaves form_dict populated with THAT request's own data,
	so the nested render can end up asking for the wrong document
	entirely (observed: "Sales Invoice None not found", since a Document
	Config save's form_dict has no top-level "name" matching a Sales
	Invoice). Snapshot and set form_dict explicitly around the call, and
	always restore it afterward, so the nested render sees the right
	document regardless of what triggered it - cheap enough to do on
	every render, not just the ones known to hit this."""
	original_form_dict = frappe.local.form_dict
	frappe.local.form_dict = frappe._dict({"doctype": doctype, "name": docname, "format": print_format})
	try:
		return get_pdf(frappe.get_print(doctype, docname, print_format=print_format))
	finally:
		frappe.local.form_dict = original_form_dict


def _render_pdf(doctype, docname, template):
	return _render_pdf_isolated(doctype, docname, template.get("print_format"))


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
		page_index, x, y, width, height = locate_anchor(pdf_bytes, template["anchor_text"])
	except SigningError as e:
		return {"found": False, "message": str(e)}

	return {"found": True, "page": page_index + 1, "x": round(x, 1), "y": round(y, 1), "width": width, "height": height}


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
		page_index, x, y, width, height = locate_anchor(pdf_bytes, template["anchor_text"])
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

		if cert_info.get("is_expired"):
			raise SigningError(
				f"The certificate on the token (Serial: {cert_info.get('serial')}, "
				f"Valid Until: {cert_info.get('valid_until')}) has already expired. "
				"If you've renewed the certificate on this same token, the new certificate may have "
				"been added as a NEW object with a DIFFERENT ID rather than replacing the old one - "
				"run pkcs11-tool --module <path> -O on the server to find the current (non-CA) "
				"certificate's ID, then update Certificate ID / Private Key ID in Digital Sign Settings."
			)

		stamp_text = build_stamp_text(settings, reason, location, cert_info)

		signed_bytes = sign_pdf_bytes(
			pdf_bytes=pdf_bytes,
			signer=signer,
			page=page_index + 1,
			x=x,
			y=y,
			width=width,
			height=height,
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
def download_pdf(doctype, name, format=None, doc=None, no_letterhead=0, letterhead=None, language=None, **kwargs):
	"""Override for the "Download PDF" whitelisted call: serve the signed
	PDF once one exists (and hasn't since been revoked), else fall
	through to Frappe's own handler.

	The function itself moved from frappe.www.printview to
	frappe.utils.print_format at some point in Frappe's history - the
	*method name* the frontend actually calls (and that
	override_whitelisted_methods in hooks.py keys on) stayed
	frappe.www.printview.download_pdf, but the real implementation to
	fall through to now lives at the newer path. If this breaks again on
	a future Frappe version, confirm with:
	  bench --site <site> console
	  >>> import inspect, frappe.utils.print_format as pf
	  >>> inspect.signature(pf.download_pdf)
	"""
	log = _latest_log(doctype, name)

	if log and log.status == "Success" and log.signed_file:
		frappe.local.response.filename = f"{name}-signed.pdf"
		frappe.local.response.filecontent = base64.b64decode(log.signed_file)
		frappe.local.response.type = "download"
		return

	try:
		from frappe.utils.print_format import download_pdf as original_download_pdf
	except ImportError:
		from frappe.www.printview import download_pdf as original_download_pdf

	# The real function has a fixed signature (no **kwargs catch-all), so
	# blindly forwarding everything Frappe's frontend sent (settings,
	# pdf_generator, _lang, etc.) crashes with "unexpected keyword
	# argument" the moment the request includes anything outside that
	# exact list. Introspect its actual signature and only pass what it
	# declares - adapts automatically to whichever Frappe version is
	# running instead of hardcoding one fixed parameter list. Anything
	# dropped here is still available to it via frappe.form_dict directly
	# if it needs it internally.
	all_args = {
		"doctype": doctype,
		"name": name,
		"format": format,
		"doc": doc,
		"no_letterhead": no_letterhead,
		"letterhead": letterhead,
		"language": language,
		**kwargs,
	}
	accepted_params = set(inspect.signature(original_download_pdf).parameters)
	call_args = {k: v for k, v in all_args.items() if k in accepted_params}

	return original_download_pdf(**call_args)


@frappe.whitelist()
def check_anchor_for_config(document_type, print_format, anchor_text):
	"""Used by Digital Sign Document Config's own pre-save validation
	(see digital_sign_document_config.py) - tests the anchor against a
	recently submitted document of this type, since a config row isn't
	tied to any one document itself.

	Tries a few candidate documents, not just the single most recent one:
	some print formats reference a related document (e.g. Return Against,
	Amended From) without checking whether it's actually set, and crash
	while rendering for any sample where that happens to be blank - that's
	a pre-existing fragility in the print format itself, not something
	this check should hard-fail the whole config save over.
	"""
	sample_names = frappe.get_all(
		document_type,
		filters={"docstatus": 1},
		pluck="name",
		order_by="modified desc",
		limit=3,
	)
	if not sample_names:
		return {"checked": False, "message": _("No submitted {0} exists yet to test against.").format(document_type)}

	last_render_error = None
	last_traceback = None
	for sample_name in sample_names:
		# frappe.throw()/msgprint() inside Frappe's own print-rendering
		# code (e.g. a PrintFormatError from a bad Jinja reference) queues
		# the message for display as a side effect BEFORE raising -
		# catching the exception below doesn't un-queue it, so without
		# this it would still visibly surface to the user even though
		# we're deliberately swallowing the actual error and retrying.
		message_log_mark = len(frappe.local.message_log)
		try:
			pdf_bytes = _render_pdf_isolated(document_type, sample_name, print_format)
		except Exception as e:
			last_render_error = e
			# frappe.get_traceback() only returns anything useful while
			# still inside this except block (it reads Python's current
			# exception context, sys.exc_info()) - capture it now, since
			# calling it again after the loop ends returns nothing.
			last_traceback = frappe.get_traceback()
			del frappe.local.message_log[message_log_mark:]
			continue  # this specific document's data tripped up the print format - try another

		try:
			page_index, x, y, width, height = locate_anchor(pdf_bytes, anchor_text)
		except SigningError as e:
			return {"checked": True, "found": False, "sample": sample_name, "message": str(e)}

		return {
			"checked": True,
			"found": True,
			"sample": sample_name,
			"page": page_index + 1,
			"x": round(x, 1),
			"y": round(y, 1),
			"width": width,
			"height": height,
		}

	# Every sample we tried failed to even render - that's a Print Format
	# problem, not something to block saving the signing config over.
	frappe.log_error(last_traceback or str(last_render_error), "Digital Sign: anchor pre-check render failed")
	return {
		"checked": False,
		"message": _(
			"Couldn't render {0} with Print Format {1} to test the anchor (tried {2} document(s)) - {3}"
		).format(document_type, print_format, len(sample_names), str(last_render_error)),
	}
