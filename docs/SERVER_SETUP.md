# Server Setup & Troubleshooting

Getting a DSC USB token working for server-side signing on Linux has
four distinct layers. Each one can fail independently, and the error
messages don't always make it obvious which layer is at fault. Work
top to bottom.

```
  1. USB          kernel sees the device            -> lsusb
  2. PC/SC        pcscd + libccid see a reader      -> pcsc_scan
  3. PKCS#11      vendor library reads the token    -> pkcs11-tool -L
  4. ERPNext      app signs through the library     -> Digital Sign Settings
```

`bash scripts/diagnose_token.sh` walks all four and reports where it
stops.

---

## Layer 1 — USB

```
lsusb
```

The token should appear, e.g.:

```
Bus 001 Device 007: ID 2ccf:080a Hypersecu USB TOKEN
Bus 001 Device 008: ID 055c:0223 Proton Electronic Ind. mToken CryptoIDA
```

**Not listed?**

- Confirm it's plugged into the *server*, not the machine you're
  SSH'ing from.
- If the server is a VM, USB passthrough must be enabled in the
  hypervisor. A device on the host is not automatically visible inside
  the guest.

Note the `ID vvvv:pppp` values — you need them for layer 2.

**Tokens are frequently mislabelled.** A token sold as "ePass2003" may
report as Hypersecu or Longmai silicon. Trust `lsusb`, not the label
or the CA's paperwork, when choosing drivers.

---

## Layer 2 — PC/SC (pcscd + libccid)

```
sudo apt install -y opensc pcscd pcsc-tools
sudo systemctl enable --now pcscd
pcsc_scan
```

Success looks like a reader name plus an ATR hex string.

**"Waiting for the first reader..." forever?**

libccid only recognises USB IDs listed in its config. Check:

```
grep -i "2ccf" /usr/lib/pcsc/drivers/ifd-ccid.bundle/Contents/Info.plist
```

If absent, `scripts/setup_token.sh` adds it. It must be added to three
parallel arrays — `ifdVendorID`, `ifdProductID`, `ifdFriendlyName` — at
the *same index* in each, or every entry after it misaligns. Use the
script rather than hand-editing.

Then `sudo systemctl restart pcscd`.

### apt dependency conflict

You may hit:

```
pcscd : Depends: libpcsclite1 (= 1.9.5-3) but 1.9.5-3ubuntu1 is to be installed
```

This happens when `security.ubuntu.com` is unreachable, so apt can see
the patched `libpcsclite1` but not the matching `pcscd`. Fix by
aligning versions explicitly:

```
sudo apt install --allow-downgrades -y opensc pcscd pcsc-tools libpcsclite1=1.9.5-3
```

If the Ubuntu mirrors are unreachable entirely (symptom: TCP connects
then hangs with no HTTP response), fetch the `.deb`s from a mirror on
different infrastructure:

```
wget http://mirrors.kernel.org/ubuntu/pool/universe/p/pcsc-lite/pcscd_1.9.5-3_amd64.deb
wget http://mirrors.kernel.org/ubuntu/pool/universe/o/opensc/opensc_0.22.0-1ubuntu2_amd64.deb
wget http://mirrors.kernel.org/ubuntu/pool/universe/o/opensc/opensc-pkcs11_0.22.0-1ubuntu2_amd64.deb
wget http://mirrors.kernel.org/ubuntu/pool/universe/p/pcsc-perl/libpcsc-perl_1.4.14-5build2_amd64.deb
wget http://mirrors.kernel.org/ubuntu/pool/universe/p/pcsc-tools/pcsc-tools_1.6.0-1_amd64.deb
sudo apt install --allow-downgrades -y ./*.deb libpcsclite1=1.9.5-3
```

---

## Layer 3 — PKCS#11

```
pkcs11-tool --module /opt/hypersecu/libcastle_v2.so.1.0.0 -L
```

Success shows the token label, manufacturer, serial:

```
Slot 0 (0x1): ES SLOT 1
  token label        : HYP2003
  token manufacturer : Hypersecu
```

**"(token not recognized)"?**

You're using the wrong PKCS#11 library. OpenSC's generic
`opensc-pkcs11.so` does *not* support most Indian DSC tokens — it reads
the ATR but has no driver for the proprietary card OS, giving
`Card is invalid or cannot be handled`. Building a newer OpenSC from
source does not help; the card profile simply isn't implemented.

You need the **token vendor's own Linux PKCS#11 library**. Ask your CA
or reseller for:

> "The Linux PKCS#11 shared library (.so) for Ubuntu 22.04 x86_64 —
> not the Windows driver, not the browser extension. Token USB ID is
> `vvvv:pppp`."

Giving the USB ID avoids the mislabelling problem. Typical filenames:
`libcastle_v2.so.*` (Hypersecu), `libshuttle_p11*.so`,
`libcastle*.so` (Longmai).

Then list the objects on the token:

```
pkcs11-tool --module /opt/hypersecu/libcastle_v2.so.1.0.0 -O
```

You'll see several certificates — your signing certificate plus the CA
chain. Pick the one whose subject is **you/your organisation**, not the
CA ones. Copy its `ID:` hex value.

Confirm the private key is usable (prompts for PIN):

```
pkcs11-tool --module /opt/hypersecu/libcastle_v2.so.1.0.0 -l -O --type privkey
```

End-to-end crypto test:

```
echo "test" > /tmp/t.txt
pkcs11-tool --module /opt/hypersecu/libcastle_v2.so.1.0.0 -l \
  --id <YOUR_CERT_ID_HEX> -s -m SHA256-RSA-PKCS -i /tmp/t.txt -o /tmp/t.sig
```

A 256-byte output for RSA-2048 means the full chain works.

---

## Layer 4 — ERPNext

See the main [README](../README.md) for app install and Digital Sign
Settings configuration.

---

## Operational notes

**The token must stay plugged into the server.** The private key is
non-exportable by design (that's the point of a hardware token), so
signing can only happen where the token physically is.

**One operation at a time.** The PKCS#11 session is opened and closed
per signature. Simultaneous signing requests may need a retry.

**The certificate identifies a person.** Every signature carries that
person's name regardless of which ERPNext user clicked Sign. Keep the
allowed-roles list narrow; the Digital Signature Log records which user
triggered each signature.

**Trust in the recipient's PDF reader** depends on the certificate's CA.
A CCA-licensed Indian CA (Capricorn, eMudhra, Sify, etc.) chains to
roots Adobe trusts. A self-signed certificate will show as
valid-but-untrusted.

**After a reboot**, verify `pcscd` came up and the token is still
detected — `bash scripts/diagnose_token.sh` is the quickest check.
