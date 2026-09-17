import frappe
from frappe import _
from frappe.model.document import Document


class DigitalSignDocumentConfig(Document):
	def validate(self):
		self._validate_submittable()
		self._validate_has_roles()
		self._validate_templates()

	def _validate_submittable(self):
		# Only submittable doctypes can meaningfully be "digitally signed"
		# post-submission -- catch misconfiguration early.
		is_submittable = frappe.db.get_value("DocType", self.document_type, "is_submittable")
		if not is_submittable:
			frappe.throw(_("{0} is not a submittable DocType, so it cannot be digitally signed.").format(self.document_type))

	def _validate_has_roles(self):
		has_enabled_template = any(row.enabled for row in self.templates)
		if has_enabled_template and not self.allowed_roles:
			frappe.throw(_("Add at least one Allowed Role - otherwise nobody will be able to sign {0}.").format(self.document_type))

	def _validate_templates(self):
		seen_print_formats = set()

		for row in self.templates:
			if row.print_format in seen_print_formats:
				frappe.throw(
					_("Row {0}: Print Format {1} is used more than once - each template needs a distinct Print Format.").format(
						row.idx, frappe.bold(row.print_format)
					)
				)
			seen_print_formats.add(row.print_format)

			self._validate_anchor_present(row)

	def _validate_anchor_present(self, row):
		# Catches the single most common mistake (anchor added to the
		# wrong Print Format, or not added at all) at save time instead
		# of leaving it to surface only when someone tries to sign.
		if not row.enabled:
			return

		from digital_sign.digital_sign.api import check_anchor_for_config

		result = check_anchor_for_config(self.document_type, row.print_format, row.anchor_text)

		if not result.get("checked"):
			# No submitted document of this type exists yet - nothing to
			# test against. Don't block saving for that reason alone,
			# just flag it so it isn't mistaken for a pass.
			frappe.msgprint(
				_("Row {0} ({1}): {2}").format(row.idx, row.print_format, result.get("message")),
				indicator="orange",
				alert=True,
			)
			return

		if not result.get("found"):
			frappe.throw(
				_(
					"Row {0}: Anchor text {1} was not found when tested against {2} using Print Format {3}: {4} "
					"Add the anchor to that Print Format's HTML before saving, or fix the Anchor Text."
				).format(
					row.idx,
					frappe.bold(row.anchor_text),
					result.get("sample"),
					frappe.bold(row.print_format),
					result.get("message") or "",
				)
			)

		frappe.msgprint(
			_("Row {0} ({1}): anchor verified - found on page {2} of {3}.").format(
				row.idx, row.print_format, result.get("page"), result.get("sample")
			),
			indicator="green",
			alert=True,
		)
