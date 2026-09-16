import frappe
from frappe import _
from frappe.model.document import Document


class DigitalSignDocumentConfig(Document):
	def validate(self):
		self._validate_submittable()
		self._validate_has_roles()
		self._validate_anchor_present()

	def _validate_submittable(self):
		# Only submittable doctypes can meaningfully be "digitally signed"
		# post-submission -- catch misconfiguration early.
		is_submittable = frappe.db.get_value("DocType", self.document_type, "is_submittable")
		if not is_submittable:
			frappe.throw(_("{0} is not a submittable DocType, so it cannot be digitally signed.").format(self.document_type))

	def _validate_has_roles(self):
		if self.enabled and not self.allowed_roles:
			frappe.throw(_("Add at least one Allowed Role - otherwise nobody will be able to sign with this template."))

	def _validate_anchor_present(self):
		# Catches the single most common mistake (anchor added to the
		# wrong Print Format, or not added at all) at save time instead
		# of leaving it to surface only when someone tries to sign.
		if not (self.enabled and self.document_type and self.print_format and self.anchor_text):
			return

		from digital_sign.digital_sign.api import check_anchor_for_config

		result = check_anchor_for_config(self.document_type, self.print_format, self.anchor_text)

		if not result.get("checked"):
			# No submitted document of this type exists yet - nothing to
			# test against. Don't block saving the config for that reason
			# alone, just flag it so it isn't mistaken for a pass.
			frappe.msgprint(result.get("message"), indicator="orange", alert=True)
			return

		if not result.get("found"):
			frappe.throw(
				_(
					"Anchor text {0} was not found when tested against {1} using Print Format {2}: {3}"
					" Add the anchor to that Print Format's HTML before saving, or fix the Anchor Text."
				).format(
					frappe.bold(self.anchor_text),
					result.get("sample"),
					frappe.bold(self.print_format),
					result.get("message") or "",
				)
			)

		frappe.msgprint(
			_("Anchor verified - found on page {0} of {1}.").format(result.get("page"), result.get("sample")),
			indicator="green",
			alert=True,
		)
