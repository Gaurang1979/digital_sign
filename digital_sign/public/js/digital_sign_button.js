// Loaded on every doctype form (see hooks.py doctype_js["*"]).
// No-ops unless the current doctype is enabled in Digital Sign Document
// Config AND the current user holds one of its allowed roles.

window.digital_sign = window.digital_sign || {};

// This file is bundled into every doctype's JS via hooks.py doctype_js["*"],
// so its top-level code runs once per distinct doctype bundle loaded in the
// session. Guard the wildcard registration so repeat loads don't stack up
// duplicate refresh handlers / custom buttons.
if (!window.digital_sign._initialized) {
	frappe.ui.form.on("*", {
		refresh(frm) {
			digital_sign.setup_button(frm);
		},
	});
	window.digital_sign._initialized = true;
}

digital_sign.setup_button = function (frm) {
	if (frm.is_new()) return;

	const all_config = frappe.boot.digital_sign_config || {};
	const config = all_config[frm.doctype];
	if (!config) return;

	if (frm.doc.docstatus !== 1) return; // only submitted documents

	const user_roles = frappe.user_roles || [];
	const allowed = config.allowed_roles || [];
	const can_sign = allowed.some((r) => user_roles.includes(r));
	if (!can_sign) return;

	// Check signed status, then render the button accordingly. Placed
	// directly in the main button bar (no group argument) so it sits
	// next to Print/Email/etc rather than tucked into a dropdown.
	frappe.call({
		method: "digital_sign.digital_sign.api.get_signature_status",
		args: { doctype: frm.doctype, docname: frm.doc.name },
		callback: (r) => {
			const status = r.message || { signed: false };
			digital_sign.render_button(frm, config, status);
		},
	});
};

digital_sign.render_button = function (frm, config, status) {
	// Remove any previous instance of this button before re-adding, so
	// repeated refreshes (e.g. after signing) don't stack duplicates.
	frm.custom_buttons && frm.page.remove_inner_button(status.signed ? "Signed" : "Digital Sign");

	if (status.signed) {
		const signed_on = status.signed_on ? frappe.datetime.str_to_user(status.signed_on) : "";
		const $btn = frm.add_custom_button(__("Signed"), () => {
			frappe.msgprint({
				title: __("Digital Signature"),
				message: __("Signed by {0} on {1}.", [status.signed_by, signed_on]),
				indicator: "green",
			});
		});
		if ($btn && $btn.prop) {
			$btn.prop("disabled", true).addClass("disabled").css("opacity", 0.6);
		}
		return;
	}

	frm.add_custom_button(__("Digital Sign"), () => digital_sign.open_sign_dialog(frm, config));
};

digital_sign.open_sign_dialog = function (frm, config) {
	const d = new frappe.ui.Dialog({
		title: __("Digital Sign Document"),
		fields: [
			{
				fieldname: "reason",
				label: __("Reason (optional)"),
				fieldtype: "Data",
			},
			{
				fieldname: "check_wrapper",
				fieldtype: "HTML",
				options: `<a href="#" class="digital-sign-test-anchor small text-muted">${__(
					"Test anchor placement before signing"
				)}</a><div class="digital-sign-test-result small" style="margin-top:6px;"></div>`,
			},
			{
				fieldname: "help",
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"The signature will be stamped automatically at the anchor location defined in this document's Print Format. This is a one-time action per document."
				)}</p>`,
			},
		],
		primary_action_label: __("Sign"),
		primary_action: (values) => {
			frappe.call({
				method: "digital_sign.digital_sign.api.sign_document",
				args: {
					doctype: frm.doctype,
					docname: frm.doc.name,
					reason: values.reason,
				},
				freeze: true,
				freeze_message: __("Signing document..."),
				callback: (r) => {
					if (r.message && r.message.ok) {
						frappe.show_alert({ message: __("Document signed successfully"), indicator: "green" });
						d.hide();
						frm.reload_doc();
					}
				},
			});
		},
	});

	d.$wrapper.find(".digital-sign-test-anchor").on("click", function (e) {
		e.preventDefault();
		const $result = d.$wrapper.find(".digital-sign-test-result");
		$result.html(__("Checking..."));
		frappe.call({
			method: "digital_sign.digital_sign.api.test_anchor",
			args: { doctype: frm.doctype, docname: frm.doc.name },
			callback: (r) => {
				const res = r.message;
				if (res && res.found) {
					$result.html(
						`<span class="indicator-pill green">${__("Found")}</span> ${__("page")} ${res.page}, x=${
							res.x
						}pt, y=${res.y}pt`
					);
				} else {
					$result.html(
						`<span class="indicator-pill red">${__("Not found")}</span> ${
							(res && res.message) || __("Anchor text not found in this Print Format.")
						}`
					);
				}
			},
		});
	});

	d.show();
};
