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

		frm.add_custom_button(__("Browse Certificates on Token"), () => digital_sign_browse_certificates(frm));
	},
});

function digital_sign_browse_certificates(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Certificates on Token"),
		size: "large",
		fields: [{ fieldname: "cert_list", fieldtype: "HTML" }],
	});
	d.fields_dict.cert_list.$wrapper.html(`<p class="text-muted">${__("Reading token...")}</p>`);
	d.show();

	frappe.call({
		method: "digital_sign.digital_sign.doctype.digital_sign_settings.digital_sign_settings.list_token_certificates",
		freeze: true,
		freeze_message: __("Reading certificates from token..."),
		callback: (r) => {
			const certs = r.message || [];
			if (!certs.length) {
				d.fields_dict.cert_list.$wrapper.html(
					`<p class="text-muted">${__("No certificates found on the token.")}</p>`
				);
				return;
			}

			const rows = certs
				.map((c) => {
					const subject = frappe.utils.escape_html(c.subject || "");
					const serial = frappe.utils.escape_html(c.serial || "");
					const valid_until = frappe.utils.escape_html(c.valid_until || "");
					const current = c.id === frm.doc.certificate_id ? ` <span class="indicator-pill blue">${__("Current")}</span>` : "";
					const status = c.is_expired
						? `<span class="indicator-pill red">${__("Expired")}</span>`
						: `<span class="indicator-pill green">${__("Valid")}</span>`;
					const kind = c.is_ca ? `<span class="text-muted small">${__("CA certificate")}</span>` : "";
					return `<tr>
						<td>${subject}${current}<br>${kind}</td>
						<td>${serial}</td>
						<td>${valid_until}</td>
						<td>${status}</td>
						<td><button class="btn btn-xs btn-default digital-sign-use-cert" data-cert-id="${frappe.utils.escape_html(c.id)}">${__("Use This")}</button></td>
					</tr>`;
				})
				.join("");

			d.fields_dict.cert_list.$wrapper.html(`
				<table class="table table-bordered">
					<tr><th>${__("Subject")}</th><th>${__("Serial")}</th><th>${__("Valid Until")}</th><th>${__("Status")}</th><th></th></tr>
					${rows}
				</table>
				<p class="text-muted small">${__("CA certificates are shown for reference only - you normally want your own end-entity certificate, not the issuer's.")}</p>
			`);

			d.fields_dict.cert_list.$wrapper.find(".digital-sign-use-cert").on("click", function () {
				const certificate_id = $(this).data("cert-id");
				frappe.call({
					method: "digital_sign.digital_sign.doctype.digital_sign_settings.digital_sign_settings.use_certificate",
					args: { certificate_id },
					freeze: true,
					freeze_message: __("Setting certificate..."),
					callback: (res) => {
						if (res.message && res.message.ok) {
							frappe.show_alert({ message: __("Certificate updated"), indicator: "green" });
							d.hide();
							frm.reload_doc();
						}
					},
				});
			});
		},
	});
}
