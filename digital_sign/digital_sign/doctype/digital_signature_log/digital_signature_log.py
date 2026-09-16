import frappe
from frappe.model.document import Document


class DigitalSignatureLog(Document):
	def on_update(self):
		# Audit trail: no edits after the initial creation.
		#
		# is_new() is NOT reliable here - on_update fires on every save,
		# including the very first insert (see Frappe's
		# run_post_save_methods()), and by that point the record already
		# has a real row in the DB, so is_new() can already read False
		# even for a brand-new document. get_doc_before_save() is the
		# actual reliable signal: it's None only when there was nothing
		# in the DB before this save started - i.e. a genuine first
		# insert - and holds the prior row's state on any real edit.
		if self.get_doc_before_save() is not None:
			frappe.throw("Digital Signature Log entries cannot be modified.")
