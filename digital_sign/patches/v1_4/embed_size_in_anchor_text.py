# Copyright (c) 2026, NDV and contributors
# For license information, please see license.txt

"""
Digital Sign Print Template's width/height fields are removed - stamp
size now lives embedded directly in the anchor text itself (e.g.
##DIGITAL_SIGN_ANCHOR:160x80##), so it can never drift out of sync with
what the Print Format's HTML actually reserves for it (a separate field
that has to be kept in sync by hand was a recurring source of overlap
bugs).

Runs pre_model_sync, while the width/height columns still exist to read
from - by post_model_sync, schema sync will have already dropped them.
Sites that never ran v1_1 (the original Document Config restructure)
have nothing to do here yet; v1_1 (post_model_sync) embeds size for
those directly since it already builds each row's anchor_text from
scratch.
"""

import re

import frappe

_SIZE_PATTERN = re.compile(r":(\d+)x(\d+)")


def execute():
	if not frappe.db.table_exists("Digital Sign Print Template"):
		return
	if not frappe.db.has_column("Digital Sign Print Template", "width"):
		return  # already migrated, or never had these fields to begin with

	rows = frappe.db.sql(
		"""SELECT name, anchor_text, width, height FROM `tabDigital Sign Print Template`""",
		as_dict=True,
	)

	updated = 0
	for row in rows:
		anchor_text = row.anchor_text or "##DIGITAL_SIGN_ANCHOR##"
		if _SIZE_PATTERN.search(anchor_text):
			continue  # already sized somehow - don't overwrite

		w = int(row.width) if row.width else 160
		h = int(row.height) if row.height else 80
		new_anchor_text = f"{anchor_text[:-2]}:{w}x{h}##" if anchor_text.endswith("##") else f"{anchor_text}:{w}x{h}"

		frappe.db.set_value(
			"Digital Sign Print Template", row.name, "anchor_text", new_anchor_text, update_modified=False
		)
		updated += 1

	frappe.db.commit()
	if updated:
		frappe.logger().info(f"digital_sign: embedded size into {updated} template row(s)' anchor text.")
