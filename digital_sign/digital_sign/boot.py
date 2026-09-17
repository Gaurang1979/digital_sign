import frappe


def boot_session(bootinfo):
	"""Attach digital-sign config for enabled doctypes to frappe.boot.

	Keeps the client-side button logic cheap: no API call on every form
	load, just a lookup in frappe.boot.digital_sign_config.
	"""
	bootinfo.digital_sign_config = get_config()


def get_config():
	"""{doctype: [template, template, ...]} - a DocType can have more than
	one signing template (different Print Formats), stored as rows in one
	Digital Sign Document Config's Templates table. Allowed Roles lives on
	the parent (shared across every template for that doctype) rather than
	per-template - Table MultiSelect fields don't work reliably nested
	inside a child table, a longstanding Frappe limitation - but every
	template dict still carries its own allowed_roles key so api.py and
	the frontend don't need to know that."""
	if not frappe.db.get_single_value("Digital Sign Settings", "enabled"):
		return {}

	configs = frappe.get_all("Digital Sign Document Config", fields=["name", "document_type"])

	result = {}
	for cfg in configs:
		roles = frappe.get_all(
			"Digital Sign Role",
			filters={"parent": cfg.name, "parenttype": "Digital Sign Document Config"},
			pluck="role",
		)

		rows = frappe.get_all(
			"Digital Sign Print Template",
			filters={"parent": cfg.name, "parenttype": "Digital Sign Document Config", "enabled": 1},
			fields=["name", "print_format", "anchor_text", "width", "height"],
		)
		if not rows:
			continue

		templates = [
			{
				"config_name": row.name,
				"anchor_text": row.anchor_text,
				"print_format": row.print_format,
				"width": row.width or 150,
				"height": row.height or 50,
				"allowed_roles": roles,
			}
			for row in rows
		]
		result[cfg.document_type] = templates
	return result
