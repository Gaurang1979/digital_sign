# Copyright (c) 2026, NDV and contributors
# For license information, please see license.txt

"""
Digital Signature Log's signed_file field moves from "a File's file_url
string" to "the signed PDF's bytes, base64-encoded, stored directly in
this field" - keeps the signed copy off the business document's own
Attachments list (previously it showed up there as a regular attachment)
and avoids keeping two copies (a File plus, potentially, this field) in
sync with each other.

Runs post_model_sync so the field is already Long Text (large enough for
base64 content) by the time this reads/writes it. For each existing log
row whose signed_file still looks like a URL (old style) rather than
base64 (new style), reads that File's bytes and re-stores them inline,
then removes the now-unnecessary File attachment.
"""

import base64

import frappe


def execute():
	if not frappe.db.table_exists("Digital Signature Log"):
		return
	if not frappe.db.has_column("Digital Signature Log", "signed_file"):
		return

	rows = frappe.db.sql(
		"""SELECT name, signed_file FROM `tabDigital Signature Log`
		   WHERE signed_file IS NOT NULL AND signed_file != ''""",
		as_dict=True,
	)

	migrated = 0
	for row in rows:
		value = row.signed_file or ""
		if not value.startswith("/"):
			continue  # already inline base64 content, nothing to do

		file_doc = frappe.db.get_value("File", {"file_url": value}, "name")
		if not file_doc:
			# Referenced File is already gone somehow - nothing to recover,
			# just clear the stale URL so it doesn't look like valid content.
			frappe.db.set_value("Digital Signature Log", row.name, "signed_file", "", update_modified=False)
			continue

		file = frappe.get_doc("File", file_doc)
		content = file.get_content()
		frappe.db.set_value(
			"Digital Signature Log",
			row.name,
			"signed_file",
			base64.b64encode(content).decode("ascii"),
			update_modified=False,
		)
		frappe.delete_doc("File", file_doc, force=True, ignore_permissions=True)
		migrated += 1

	frappe.db.commit()
	if migrated:
		frappe.logger().info(f"digital_sign: inlined {migrated} signed PDF(s) from File attachments into Digital Signature Log.")
