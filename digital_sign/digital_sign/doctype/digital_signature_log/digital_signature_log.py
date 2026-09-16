import frappe
from frappe.model.document import Document


class DigitalSignatureLog(Document):
	def on_update(self):
		# Audit trail: no edits after creation.
		if not self.is_new():
			frappe.throw("Digital Signature Log entries cannot be modified.")
