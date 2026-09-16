app_name = "digital_sign"
app_title = "Digital Sign"
app_publisher = "Sundaram Technologies"
app_description = "Generic, role-based digital signing for ERPNext documents with per-document signature placement."
app_email = "gaurang@sundaramtech.com"
app_license = "mit"

# Load the sign button on every doctype form. The JS itself is a no-op
# unless the current doctype is enabled in Digital Sign Document Config.
doctype_js = {"*": "public/js/digital_sign_button.js"}

# Push enabled-doctype config into frappe.boot once per session instead of
# an API call on every form load.
extend_bootinfo = "digital_sign.digital_sign.boot.boot_session"

# Intercept the standard "Download PDF" / Print PDF whitelisted call.
# If a signed PDF already exists for this document, serve that instead
# of a freshly (unsigned) rendered one.
# NOTE: verify this dotted path matches your installed Frappe version --
# see the "Before you go live" section in README.md.
override_whitelisted_methods = {
	"frappe.www.printview.download_pdf": "digital_sign.digital_sign.api.download_pdf"
}
