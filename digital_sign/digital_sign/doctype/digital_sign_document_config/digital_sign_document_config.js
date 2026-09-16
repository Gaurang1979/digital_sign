// Copyright (c) 2026, NDV and contributors
// For license information, please see license.txt

frappe.ui.form.on("Digital Sign Document Config", {
	document_type(frm) {
		// Existing template rows were picked against the old DocType - a
		// change here almost certainly invalidates them.
		if ((frm.doc.templates || []).length) {
			frm.clear_table("templates");
			frm.refresh_field("templates");
		}
	},
});

frappe.ui.form.on("Digital Sign Print Template", {
	form_render(frm, cdt, cdn) {
		// Print Format choices should only ever be ones that actually
		// apply to the parent's Document Type.
		frm.set_query("print_format", "templates", () => ({
			filters: { doc_type: frm.doc.document_type },
		}));
	},
});
