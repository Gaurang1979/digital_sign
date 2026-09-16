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
