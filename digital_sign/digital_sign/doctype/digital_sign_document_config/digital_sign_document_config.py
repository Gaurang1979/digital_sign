from frappe.model.document import Document


class DigitalSignDocumentConfig(Document):
	def validate(self):
		# Only submittable doctypes can meaningfully be "digitally signed"
		# post-submission -- catch misconfiguration early.
		import frappe

		is_submittable = frappe.db.get_value("DocType", self.document_type, "is_submittable")
		if not is_submittable:
			frappe.throw(f"{self.document_type} is not a submittable DocType, so it cannot be digitally signed.")
