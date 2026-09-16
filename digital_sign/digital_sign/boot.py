import frappe


def boot_session(bootinfo):
	"""Attach digital-sign config for enabled doctypes to frappe.boot.

	Keeps the client-side button logic cheap: no API call on every form
	load, just a lookup in frappe.boot.digital_sign_config.
	"""
	bootinfo.digital_sign_config = get_config()


def get_config():
	"""{doctype: [template, template, ...]} - a DocType can have more than
	one Digital Sign Document Config row (different Print Formats, e.g.
	a domestic vs. an export version of the same DocType), so this is
	always a list even when there's only one."""
	if not frappe.db.get_single_value("Digital Sign Settings", "enabled"):
		return {}

	rows = frappe.get_all(
		"Digital Sign Document Config",
		filters={"enabled": 1},
		fields=["name", "document_type", "anchor_text", "print_format", "width", "height"],
	)

	config = {}
	for row in rows:
		roles = frappe.get_all("Digital Sign Role", filters={"parent": row.name}, pluck="role")
		config.setdefault(row.document_type, []).append(
			{
				"config_name": row.name,
				"anchor_text": row.anchor_text,
				"print_format": row.print_format,
				"width": row.width or 150,
				"height": row.height or 50,
				"allowed_roles": roles,
			}
		)
	return config
