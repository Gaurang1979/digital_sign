import frappe
from frappe import _
from frappe.model.document import Document


class DigitalSignPrintTemplate(Document):
	def validate(self):
		# Belt-and-suspenders: the parent's own validate() also does this
		# with the "which row" context needed for a good error message,
		# but keep a bare minimum check here too in case a row is ever
		# manipulated outside the normal parent-save flow.
		if self.width and self.width <= 0:
			frappe.throw(_("Signature Box Width must be greater than 0."))
