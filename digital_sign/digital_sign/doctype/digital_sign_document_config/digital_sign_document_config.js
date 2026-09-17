// Copyright (c) 2026, NDV and contributors
// For license information, please see license.txt

frappe.ui.form.on("Digital Sign Document Config", {
	refresh(frm) {
		// Print Format choices in the Templates table should only ever be
		// ones that actually apply to this row's Document Type. Registered
		// once here (the standard Frappe idiom for filtering a child
		// table's own Link field) rather than per-row - the filter
		// function itself reads frm.doc.document_type fresh every time a
		// dropdown is opened, so it doesn't need re-registering when that
		// value changes.
		frm.set_query("print_format", "templates", () => ({
			filters: { doc_type: frm.doc.document_type },
		}));
	},

	document_type(frm) {
		// Existing template rows were picked against the old DocType - a
		// change here almost certainly invalidates them.
		if ((frm.doc.templates || []).length) {
			frm.clear_table("templates");
			frm.refresh_field("templates");
		}
	},
});
