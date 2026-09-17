# Copyright (c) 2026, NDV and contributors
# For license information, please see license.txt

"""
Digital Sign Document Config moves from "one standalone row per
DocType+Print Format" back to "one row per DocType, with a
Digital Sign Print Template child-table row per Print Format" - lets
someone actually see and add multiple templates for the same DocType in
one place instead of hunting for a second top-level document to create.

Runs post_model_sync so the new templates/Digital Sign Print Template
schema already exists to write into. Reads the old flat columns via raw
SQL, since by this point the DocType's own meta no longer declares them
(Frappe doesn't drop the now-orphaned columns during sync, so the data
is still physically there to read).
"""

import frappe


def execute():
	if not frappe.db.table_exists("Digital Sign Document Config"):
		return
	if not frappe.db.has_column("Digital Sign Document Config", "print_format"):
		return  # already on the new (parent + templates table) shape

	old_rows = frappe.db.sql(
		"""
		SELECT name, document_type, enabled, anchor_text, print_format, width, height
		FROM `tabDigital Sign Document Config`
		""",
		as_dict=True,
	)
	if not old_rows:
		return

	old_roles = {}
	if frappe.db.table_exists("Digital Sign Role"):
		role_rows = frappe.db.sql(
			"""SELECT parent, role FROM `tabDigital Sign Role`
			   WHERE parenttype='Digital Sign Document Config'""",
			as_dict=True,
		)
		for r in role_rows:
			old_roles.setdefault(r.parent, []).append(r.role)

	by_doctype = {}
	for row in old_rows:
		by_doctype.setdefault(row.document_type, []).append(row)

	# The Digital Sign Print Template doctype was just created by this
	# same migrate run's schema sync - post_model_sync guarantees its
	# table exists, but Frappe's in-memory meta cache doesn't auto-refresh
	# mid-process for a doctype introduced in that same run. Without this,
	# parent.append("templates", {}) / child.append("allowed_roles", {})
	# below fail with AttributeError, since _init_child can't find fields
	# on a doctype it doesn't yet know exists.
	frappe.reload_doctype("Digital Sign Document Config", force=True)
	frappe.reload_doctype("Digital Sign Print Template", force=True)
	frappe.reload_doctype("Digital Sign Role", force=True)

	# Delete every old row first - a new parent doc's autoname resolves to
	# the bare document_type, which would collide with an old row already
	# sitting under that exact name otherwise.
	for row in old_rows:
		frappe.delete_doc("Digital Sign Document Config", row.name, force=True, ignore_permissions=True)

	for document_type, rows in by_doctype.items():
		parent = frappe.new_doc("Digital Sign Document Config")
		parent.document_type = document_type
		for row in rows:
			child = parent.append("templates", {})
			child.enabled = row.enabled
			child.print_format = row.print_format
			child.anchor_text = row.anchor_text
			child.width = row.width
			child.height = row.height
			for role in old_roles.get(row.name, []):
				child.append("allowed_roles", {"role": role})
		# Skip the (now much heavier, per-row PDF-rendering) validate()
		# during a bulk migration - the data is coming straight from
		# already-working rows, nothing new to verify.
		parent.flags.ignore_validate = True
		parent.insert(ignore_permissions=True)

	frappe.db.commit()
	frappe.logger().info(
		f"digital_sign: consolidated {len(old_rows)} Digital Sign Document Config row(s) "
		f"into {len(by_doctype)} parent doc(s) with a templates child table."
	)
