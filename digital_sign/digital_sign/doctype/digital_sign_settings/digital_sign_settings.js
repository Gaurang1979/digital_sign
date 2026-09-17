// Copyright (c) 2026, NDV and contributors
// For license information, please see license.txt

frappe.ui.form.on("Digital Sign Settings", {
	refresh(frm) {
		if (!frm.doc.enabled) return;

		frm.add_custom_button(__("Refresh Certificate Info"), () => {
			frappe.call({
				method: "digital_sign.digital_sign.doctype.digital_sign_settings.digital_sign_settings.test_token",
				freeze: true,
				freeze_message: __("Reading certificate from token..."),
				callback: (r) => {
					if (r.message && r.message.ok) {
						frappe.show_alert({ message: __("Certificate info refreshed"), indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		});
	},
});
