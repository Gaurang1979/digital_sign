app_name = "digital_sign"
app_title = "Digital Sign"
app_publisher = "Sundaram Technologies"
app_description = "Generic, role-based digital signing for ERPNext documents with per-document signature placement."
app_email = "gaurang@sundaramtech.com"
app_license = "mit"

# Load on every Desk page (doctype_js has no "*" wildcard support in
# Frappe - see https://github.com/frappe/frappe/issues/17169 - so this
# can't be done via doctype_js["*"]). The script itself registers
# frappe.ui.form.on() per-doctype from frappe.boot.digital_sign_config,
# so it only does anything on the small set of doctypes actually
# configured in Digital Sign Document Config.
#
# NOTE: the source file MUST be named *.bundle.js - Frappe's esbuild
# (since build.json was deprecated) only auto-discovers entry points by
# that filename suffix, anywhere under public/. A plain .js file here is
# silently invisible to the build - it compiles "successfully" having
# bundled nothing, with no error at all.
#
# NOTE: this value must match the BARE filename exactly as it appears as
# a key in sites/assets/assets.json (no "public/js/" prefix) - Frappe
# resolves app_include_js by exact-string lookup against that file to
# find the actual hashed output path. A prefixed/mismatched string here
# misses the lookup and falls back to a literal (broken) raw path.
app_include_js = "digital_sign_button.bundle.js"

# Push enabled-doctype config into frappe.boot once per session instead of
# an API call on every form load.
extend_bootinfo = "digital_sign.digital_sign.boot.boot_session"

# Intercept the standard "Download PDF" / Print PDF whitelisted call.
# If a signed PDF already exists for this document, serve that instead
# of a freshly (unsigned) rendered one.
# NOTE: verify this dotted path matches your installed Frappe version --
# see the "Before you go live" section in README.md.
override_whitelisted_methods = {
	# Frappe's actual "PDF"/"Download PDF" button calls
	# frappe.utils.print_format.download_pdf (confirmed from the exact
	# request URL it sends) - frappe.www.printview.download_pdf is kept
	# too since that's the older/legacy name some Frappe versions and
	# direct API callers still use.
	"frappe.utils.print_format.download_pdf": "digital_sign.digital_sign.api.download_pdf",
	"frappe.www.printview.download_pdf": "digital_sign.digital_sign.api.download_pdf",
}
