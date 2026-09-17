import frappe
from frappe import _
from frappe.model.document import Document

from digital_sign.digital_sign.signing import (
	SigningError,
	build_signer,
	certificate_details,
	list_certificates,
	open_session,
)


class DigitalSignSettings(Document):
	def validate(self):
		if not self.enabled:
			return
		if not (self.pkcs11_module_path and self.get_password("token_pin", raise_exception=False)):
			return
		if not (self.certificate_id or self.certificate_label):
			# Nothing to fetch yet - this is the normal state right after
			# filling in just the token connection details, before using
			# "Browse Certificates on Token" (which only needs the above,
			# deliberately not Certificate ID) to actually pick one.
			return
		# Touching the token on every save is intentional: it surfaces a
		# missing/unplugged token or wrong PIN here, rather than at the
		# moment someone tries to sign a real document.
		self.refresh_certificate_details()

	def refresh_certificate_details(self):
		session = None
		try:
			session = open_session(self)
			signer = build_signer(session, self)
			info = certificate_details(signer)
		except SigningError as e:
			frappe.throw(str(e))
		finally:
			if session is not None:
				try:
					session.close()
				except Exception:
					pass

		self.certificate_subject = info["subject"]
		self.certificate_serial = info["serial"]
		self.certificate_valid_until = info["valid_until"]

		if info.get("is_expired"):
			# Not a hard block on save - the admin may well be in the
			# middle of fixing Certificate ID after a renewal, and
			# forcing them to abandon that edit to get past this would
			# be worse than just warning loudly. sign_document() itself
			# (see api.py) DOES hard-block signing with an expired
			# certificate - this is purely so it's impossible to miss
			# here too, as early as possible.
			frappe.msgprint(
				_(
					"This certificate (Serial: {0}) has already expired (Valid Until: {1}). If you've "
					"renewed the certificate on this same token, the new one may have a different object "
					"ID than what's configured here - run pkcs11-tool --module &lt;path&gt; -O on the "
					"server to find the current certificate's ID and update Certificate ID / Private Key "
					"ID above."
				).format(self.certificate_serial, self.certificate_valid_until),
				title=_("Certificate Expired"),
				indicator="red",
			)


@frappe.whitelist()
def test_token():
	"""Manual check: confirm the token is reachable and the configured
	certificate can be selected, without signing anything."""
	doc = frappe.get_single("Digital Sign Settings")
	doc.refresh_certificate_details()
	doc.save()
	return {
		"ok": True,
		"subject": doc.certificate_subject,
		"serial": doc.certificate_serial,
		"valid_until": doc.certificate_valid_until,
	}


@frappe.whitelist()
def list_token_certificates():
	"""Every certificate currently on the token, for the "Browse
	Certificates on Token" dialog - so picking (or re-picking, after a
	renewal) the signing certificate is a point-and-click choice instead
	of running pkcs11-tool externally and pasting a hex ID by hand.

	Only needs Module Path / Token Label / PIN to already be saved -
	deliberately does NOT need Certificate ID to already be set, since
	the whole point is to help pick that."""
	settings = frappe.get_single("Digital Sign Settings")
	session = None
	try:
		session = open_session(settings)
		return list_certificates(session)
	except SigningError as e:
		frappe.throw(str(e))
	finally:
		if session is not None:
			try:
				session.close()
			except Exception:
				pass


@frappe.whitelist()
def use_certificate(certificate_id):
	"""Sets Certificate ID (and Private Key ID, assuming the common case
	where they match) to the chosen token object, then re-fetches its
	details the normal way - called from "Browse Certificates on Token"
	once the admin picks one."""
	settings = frappe.get_single("Digital Sign Settings")
	settings.certificate_id = certificate_id
	settings.key_id = certificate_id
	settings.save()
	return {
		"ok": True,
		"subject": settings.certificate_subject,
		"serial": settings.certificate_serial,
		"valid_until": settings.certificate_valid_until,
	}