# Copyright (c) 2026, NDV and contributors
# For license information, please see license.txt

"""Digital Signature Log gets a fetched performed_by_name (full name,
not just the User ID/email) so the list clearly shows who signed and who
revoked. New entries set it explicitly at insert time (see api.py) - this
backfills any rows that already existed before that field did."""

import frappe


def execute():
	if not frappe.db.has_column("Digital Signature Log", "performed_by_name"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabDigital Signature Log` dsl
		JOIN `tabUser` u ON u.name = dsl.signed_by
		SET dsl.performed_by_name = u.full_name
		WHERE IFNULL(dsl.performed_by_name, '') = ''
		"""
	)
	frappe.db.commit()
