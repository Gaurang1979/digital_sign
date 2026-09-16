// Loaded on every Desk page via app_include_js (see hooks.py - doctype_js
// has no "*" wildcard in Frappe, so this can't be scoped to "every doctype
// form" at the hook level). Instead, this registers a normal per-doctype
// frappe.ui.form.on() handler for each doctype actually present in
// frappe.boot.digital_sign_config - a small, known set - so it only does
// anything on forms that are actually configured for signing.

window.digital_sign = window.digital_sign || {};

if (!window.digital_sign._initialized) {
	const configured_doctypes = Object.keys(frappe.boot.digital_sign_config || {});
	configured_doctypes.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				digital_sign.setup_button(frm);
			},
		});
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
	// Both actions always sit in the one "Digital Sign" group - the
	// backend rejects signing an already-signed document (or revoking an
	// unsigned one) with a clear message, so there's no need to hide
	// either option based on current state.
	frm.page.remove_inner_button(__("Sign Document"), __("Digital Sign"));
	frm.page.remove_inner_button(__("Revoke Sign"), __("Digital Sign"));

	frm.add_custom_button(__("Sign Document"), () => digital_sign.open_sign_dialog(frm, config), __("Digital Sign"));
	frm.add_custom_button(__("Revoke Sign"), () => digital_sign.open_revoke_dialog(frm), __("Digital Sign"));

	if (status.signed) {
		const signed_on = status.signed_on ? frappe.datetime.str_to_user(status.signed_on) : "";
		frm.page.set_indicator(__("Signed"), "green");
		frm.page.$title_area.find(".indicator").off("click.digital_sign").on("click.digital_sign", () => {
			frappe.msgprint({
				title: __("Digital Signature"),
				message: __("Signed by {0} on {1}.", [status.signed_by, signed_on]),
				indicator: "green",
			});
		});
	} else {
		frm.page.clear_indicator();
	}
};

digital_sign.open_sign_dialog = function (frm, config) {
	const d = new frappe.ui.Dialog({
		title: __("Digital Sign Document"),
		fields: [
			{
				fieldname: "check_wrapper",
				fieldtype: "HTML",
				options: `<a href="#" class="digital-sign-test-anchor small text-muted">${__(
					"Test anchor placement before signing"
				)}</a><div class="digital-sign-test-result small" style="margin-top:6px;"></div>`,
			},
		],
		primary_action_label: __("Sign"),
		primary_action: () => {
			frappe.call({
				method: "digital_sign.digital_sign.api.sign_document",
				args: { doctype: frm.doctype, docname: frm.doc.name },
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

digital_sign.open_revoke_dialog = function (frm) {
	const d = new frappe.ui.Dialog({
		title: __("Revoke Digital Signature"),
		fields: [
			{
				fieldname: "warning",
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"This keeps the existing signed copy on record for audit purposes, but the document becomes unsigned going forward - Print / Download PDF will serve a fresh, unsigned copy, and it can be signed again."
				)}</p>`,
			},
			{
				fieldname: "reason",
				label: __("Reason (optional)"),
				fieldtype: "Small Text",
			},
		],
		primary_action_label: __("Revoke"),
		primary_action: (values) => {
			frappe.call({
				method: "digital_sign.digital_sign.api.revoke_signature",
				args: { doctype: frm.doctype, docname: frm.doc.name, reason: values.reason },
				freeze: true,
				freeze_message: __("Revoking..."),
				callback: (r) => {
					if (r.message && r.message.ok) {
						frappe.show_alert({ message: __("Signature revoked"), indicator: "orange" });
						d.hide();
						frm.reload_doc();
					}
				},
			});
		},
	});

	d.show();
};
