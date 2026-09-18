# digital_sign

Role-based digital signing for ERPNext v16 using a hardware DSC USB
token (PKCS#11). Signatures are real PAdES cryptographic signatures —
verifiable in Adobe Reader, not stamped images.

Built and verified against: Hypersecu HYP2003 token, Capricorn DSC
(CCA India chain), Ubuntu 22.04, ERPNext v16, pyHanko 0.36.2.

---

## What it does

- **Digital Sign Settings** — one place to configure the token
  (PKCS#11 library path, token label, PIN, certificate ID), choose
  what appears inside the visible stamp, and set the green-tick
  watermark's opacity.
- **Digital Sign Document Config** — one row per DocType, with a
  **Templates** table inside it: one row per Print Format that DocType
  can be signed with (e.g. a domestic vs. export Print Format for the
  same DocType), each with its own allowed roles, anchor text, and
  stamp size. The sign dialog lets the user pick when more than one
  template applies to them. Saving automatically tests every enabled
  row's anchor against the most recently submitted document of that
  type and blocks the save with a clear, row-specific error if it
  isn't actually found - no more discovering a bad anchor only when
  someone tries to sign.
- **Digital Sign button** — a "Digital Sign" group button in the
  document toolbar for submitted documents, visible only to users
  holding an allowed role, with two actions: **Sign Document** and
  **Revoke Sign**. The backend rejects signing an already-signed
  document (or revoking an unsigned one) with a clear message. Once
  signed, the page shows a green "Signed" indicator — click it to see
  who signed and when.
- **Digital Signature Log** — immutable audit trail: every sign *and*
  revoke is its own permanent row (revoking never edits or deletes a
  prior entry) — who did what, when, with which certificate.
- **Print / Download PDF** automatically serves the signed PDF while
  the latest action for that document is a signature; after a revoke it
  reverts to serving a fresh unsigned render, and the document can be
  signed again from there.

## Signature placement

You do **not** touch individual documents. Add an invisible anchor to
the **Print Format template** once, sized to reserve the same space
the stamp will actually take up (otherwise the stamp overlaps whatever
content already sits there). Size lives entirely in the Print Format's
HTML, not in the Anchor Text field on Digital Sign Print Template -
that field can stay at its plain default (`##DIGITAL_SIGN_ANCHOR##`)
for every template regardless of what size each one's HTML actually
uses; nothing needs to be typed into two places to match:

```html
<div style="width:160px; height:40px; color:#ffffff; overflow:hidden;">##DIGITAL_SIGN_ANCHOR:160x40##</div>
```

A plain block-level `div` with explicit width/height - no
`position:absolute`, no `inline-block` - reliably reserves that much
space in the page's normal layout flow, and the anchor text sits at
its top-left by default with no extra positioning needed. (An earlier
version of this guidance used `position:absolute`, which some PDF
engines - wkhtmltopdf specifically - don't reliably reserve space for;
if a stamp has overlapped or drifted to the wrong spot, switch to this
plain `div` instead.)

There's no hidden default forcing a particular height - `160x40` above
is just an example. With every stamp field enabled in Settings (signer
name, reason, location, date, certificate serial) that's up to 5 lines
of text at 7pt, needing something like 70-80pt tall to stay legible;
with fewer fields enabled, a shorter box works fine. Leaving off the
`:WxH` suffix entirely (plain `##DIGITAL_SIGN_ANCHOR##`) falls back to
160x80 automatically - the signing code detects whichever variant is
actually rendered on the page, purely from the HTML, every time.

**Keep the `div`'s own `width`/`height` matching the number in the
anchor text exactly** - the `div` reserves the layout space, and the
anchor text tells the signing code how big to actually draw the stamp;
if the two disagree, the stamp will be sized correctly but may not fit
the space you reserved for it.

The stamp is drawn extending **downward-right** from exactly where the
anchor text sits (its top-left corner), filling the box below and
right of it. The stamp content (text and the tick background) is
centered both directions within that box automatically
- the small `margin` above adds a buffer so it never quite touches
text directly above the box either.

Use `color:#ffffff` (matched to a white background — adjust if yours
isn't white), **not** `opacity:0`. Some PDF engines skip painting
`opacity:0` text entirely, which drops it from the PDF's searchable
text layer too — the anchor becomes genuinely unfindable, not just
invisible. `color` matching keeps the text actually painted (findable)
while still being invisible to the eye.

At sign time the app renders the PDF, finds that text, and places the
stamp's bottom-left corner there, sized per the template row's config.
Since a Print Format is shared by every document of that type, one
edit covers all of them.

Signing itself is a simple confirmation - click **Digital Sign → Sign
Document**, confirm, done. The anchor is verified up front when the
template is saved (see above), not re-checked at sign time.

## Stamp content

Checkboxes in Settings control what's printed inside the stamp box:
signer name, date/time, reason, location, certificate serial. For full
control, **Custom Stamp Text** overrides them and supports
`{signer_name}` `{date}` `{reason}` `{location}` `{certificate_serial}`.

The stamp itself has no border, and shows a green tick watermark behind
the text - **Background Tick Opacity** in Settings controls how visible
that watermark is (0 removes it, 100 is fully solid; default 50).

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
   - Save with just the above filled in, then click **Browse
     Certificates on Token** — lists every certificate actually on the
     token (subject, serial, valid until, expired/valid) and sets
     Certificate ID / Private Key ID for you with one click on **Use
     This**. This is the easy path, especially after renewing a
     certificate on an existing token (the renewed certificate often
     ends up as a *new* object with a different ID rather than
     replacing the old one in place - Browse makes picking the right
     one a click instead of manually diffing `pkcs11-tool -O` output).
   - Alternatively, set Certificate ID (hex) by hand from `pkcs11-tool
     -O`'s `ID:` field for *your* certificate — not the CA chain
     certificates. Leave Private Key ID blank unless your token uses a
     different ID for the key.

   Saving (or clicking Refresh Certificate Info) opens the token and
   fills in the certificate subject, serial and expiry. If the
   certificate found is already expired, Settings shows a red warning
   naming the likely cause (see above) - Browse Certificates on Token
   is the fastest way to fix it.

2. **Print Format** — add the anchor span (above).

3. **Digital Sign Document Config** — one document per DocType. Inside
   it, add a row to the **Templates** table per Print Format you want
   to sign with: allowed roles, the Print Format itself, anchor text,
   and stamp size. Add another row in the same table for a second
   template on the same DocType. Saving verifies every enabled row's
   anchor is actually found - fix it here
   before it ever reaches a real signature attempt.

4. Open a submitted document, use **Digital Sign → Sign Document**
   (pick a template first if more than one applies), confirm, then
   check Print / Download PDF. **Digital Sign → Revoke Sign** reverses
   it (keeps the old signed copy on record, but the document goes back
   to unsigned and can be signed again).

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
