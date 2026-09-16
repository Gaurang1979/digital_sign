# digital_sign

Role-based digital signing for ERPNext v16 using a hardware DSC USB
token (PKCS#11). Signatures are real PAdES cryptographic signatures —
verifiable in Adobe Reader, not stamped images.

Built and verified against: Hypersecu HYP2003 token, Capricorn DSC
(CCA India chain), Ubuntu 22.04, ERPNext v16, pyHanko 0.36.2.

---

## What it does

- **Digital Sign Settings** — one place to configure the token
  (PKCS#11 library path, token label, PIN, certificate ID) and choose
  what appears inside the visible stamp.
- **Digital Sign Document Config** — enable signing per DocType, set
  which roles may sign, where the stamp goes, and its size.
- **Digital Sign button** — appears in the document toolbar for
  submitted documents, only for users holding an allowed role. One
  click signs; afterwards it becomes a disabled **Signed** indicator.
- **Digital Signature Log** — immutable audit trail: who signed what,
  when, with which certificate.
- **Print / Download PDF** automatically serves the signed PDF once a
  document has been signed.

## Signature placement

You do **not** touch individual documents. Add an invisible anchor to
the **Print Format template** once:

```html
<span style="opacity:0;">##DIGITAL_SIGN_ANCHOR##</span>
```

At sign time the app renders the PDF, finds that text, and places the
stamp's bottom-left corner there, sized per the DocType's config. Since
a Print Format is shared by every document of that type, one edit
covers all of them.

The sign dialog has a **Test anchor placement** link that reports
whether the anchor was found and where, without signing — use it after
any Print Format change.

## Stamp content

Checkboxes in Settings control what's printed inside the stamp box:
signer name, date/time, reason, location, certificate serial. For full
control, **Custom Stamp Text** overrides them and supports
`{signer_name}` `{date}` `{reason}` `{location}` `{certificate_serial}`.

---

## Install

### 1. Server prerequisites (token stack)

```
sudo bash scripts/setup_token.sh
```

Installs PC/SC middleware, registers the token's USB ID with libccid,
installs the vendor PKCS#11 library to `/opt/hypersecu/`, and applies
udev rules.

Verify before continuing:

```
bash scripts/diagnose_token.sh
```

All four layers must pass. If any fail, see
[docs/SERVER_SETUP.md](docs/SERVER_SETUP.md) — it covers the common
failure modes in detail.

### 2. The ERPNext app

```
cd ~/frappe-bench/apps
git clone https://github.com/Gaurang1979/digital_sign.git
cd ~/frappe-bench
./env/bin/pip install -e apps/digital_sign
```

Register it in both app lists (a bare `echo >>` can glue lines together
if a file lacks a trailing newline):

```
python3 -c "
for p in ['apps.txt', 'sites/apps.txt']:
    with open(p) as f:
        lines = [l.strip() for l in f if l.strip()]
    if 'digital_sign' not in lines:
        lines.append('digital_sign')
    with open(p, 'w') as f:
        f.write('\n'.join(lines) + '\n')
"
```

```
bench --site <your-site> install-app digital_sign
bench --site <your-site> migrate
bench build
sudo supervisorctl restart all
```

> Use plain `bench build`, not `bench build --app digital_sign` — the
> filtered incremental build fails on newly added apps with
> `TypeError: paths[0] ... Received undefined`.

### 3. Configure

1. **Digital Sign Settings**
   - Enable, set Signer / Organization Name
   - PKCS#11 Module Path: `/opt/hypersecu/libcastle_v2.so.1.0.0`
   - Token Label: `HYP2003` (from `pkcs11-tool -L`)
   - Token PIN
   - Certificate ID (hex): the `ID:` of *your* certificate from
     `pkcs11-tool -O` — not the CA chain certificates
   - Leave Private Key ID blank unless your token uses a different ID
     for the key

   Saving opens the token and fills in the certificate subject, serial
   and expiry. If that fails, fix it before going further.

2. **Print Format** — add the anchor span (above).

3. **Digital Sign Document Config** — add a row per DocType, set
   allowed roles, anchor text, and stamp width/height.

4. Open a submitted document, test the anchor, sign, then check
   Print / Download PDF.

---

## Operational notes

- **The token must stay plugged into the server.** The private key is
  non-exportable by design; signing only happens where the token is.
- **The PIN is stored encrypted** in Settings, so signing is automatic
  for anyone with an allowed role.
- **The certificate identifies a person**, so every signature carries
  that name regardless of which ERPNext user clicked Sign. Keep the
  allowed-roles list narrow. The audit log records the triggering user.
- **One signature per document.** Re-signing is blocked once a
  successful signature exists.
- **Token handles one operation at a time** — concurrent signing
  requests may need a retry.

---

## Repository layout

```
digital_sign/      Frappe app (doctypes, signing engine, client JS)
drivers/           Vendor PKCS#11 driver for HYP2003 (Linux x86_64)
scripts/           setup_token.sh, diagnose_token.sh
docs/              SERVER_SETUP.md — layer-by-layer troubleshooting
```

## Licensing note

`drivers/` contains redistributable material from Hypersecu
Information Systems (Copyright © 2023). It is included for
convenience of deployment. If this repository is made public, confirm
redistribution terms with the vendor, or remove the directory and
obtain the library from your CA instead — `scripts/setup_token.sh`
will tell you where to place it.

The app code itself is MIT licensed.
