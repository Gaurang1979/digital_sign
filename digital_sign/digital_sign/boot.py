import frappe


def boot_session(bootinfo):
	"""Attach digital-sign config for enabled doctypes to frappe.boot.

	Keeps the client-side button logic cheap: no API call on every form
	load, just a lookup in frappe.boot.digital_sign_config.
	"""
	bootinfo.digital_sign_config = get_config()


def get_config():
	"""{doctype: [template, template, ...]} - a DocType can have more than
	one signing template (different Print Formats), stored as rows in
	one Digital Sign Document Config's child table."""
	if not frappe.db.get_single_value("Digital Sign Settings", "enabled"):
		return {}

	configs = frappe.get_all("Digital Sign Document Config", fields=["name", "document_type"])

	result = {}
	for cfg in configs:
		rows = frappe.get_all(
			"Digital Sign Print Template",
			filters={"parent": cfg.name, "parenttype": "Digital Sign Document Config", "enabled": 1},
			fields=["name", "print_format", "anchor_text", "width", "height"],
		)
		if not rows:
			continue

		templates = []
		for row in rows:
			roles = frappe.get_all(
				"Digital Sign Role",
				filters={"parent": row.name, "parenttype": "Digital Sign Print Template"},
				pluck="role",
			)
			templates.append(
				{
					"config_name": row.name,
					"anchor_text": row.anchor_text,
					"print_format": row.print_format,
					"width": row.width or 150,
					"height": row.height or 50,
					"allowed_roles": roles,
				}
			)
		if templates:
			result[cfg.document_type] = templates
	return result
