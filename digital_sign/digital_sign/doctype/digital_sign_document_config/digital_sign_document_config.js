// Copyright (c) 2026, NDV and contributors
// For license information, please see license.txt

frappe.ui.form.on("Digital Sign Document Config", {
	document_type(frm) {
		// Print Format choices should only ever be ones that actually apply
		// to the selected DocType - avoids picking a stray format that
		// belongs to something else entirely.
		frm.set_value("print_format", "");
	},

	setup(frm) {
		frm.set_query("print_format", () => ({
			filters: { doc_type: frm.doc.document_type },
		}));
	},
});
