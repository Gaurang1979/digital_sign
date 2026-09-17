import frappe
from frappe import _
from frappe.model.document import Document

from digital_sign.digital_sign.signing import (
	SigningError,
	build_signer,
	certificate_details,
	open_session,
)


class DigitalSignSettings(Document):
	def validate(self):
		if not self.enabled:
			return
		if not (self.pkcs11_module_path and self.get_password("token_pin", raise_exception=False)):
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