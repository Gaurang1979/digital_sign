#!/usr/bin/env bash
#
# Walks the token stack layer by layer and reports where it breaks.
# Run this first whenever signing stops working.
#
#   bash scripts/diagnose_token.sh
#
LIB="${1:-/opt/hypersecu/libcastle_v2.so.1.0.0}"

echo "=== 1. USB layer (is the token physically visible?) ==="
lsusb | grep -iE "token|hypersecu|longmai|proton|feitian|watchdata" || {
  echo "    No token found in lsusb."
  echo "    -> Check it's plugged into THIS machine. If the server is a VM,"
  echo "       USB passthrough must be configured in the hypervisor."
}
echo

echo "=== 2. pcscd service ==="
systemctl is-active pcscd >/dev/null 2>&1 \
  && echo "    pcscd is running" \
  || echo "    pcscd NOT running -> sudo systemctl start pcscd"
echo

echo "=== 3. PC/SC reader layer (does pcscd see the token?) ==="
timeout 5 pcsc_scan 2>/dev/null | grep -iE "reader|ATR" | head -5 || {
  echo "    No reader detected."
  echo "    -> The token's USB ID may be missing from libccid."
  echo "       Re-run: sudo bash scripts/setup_token.sh"
}
echo

echo "=== 4. PKCS#11 layer (can the vendor library read the token?) ==="
if [[ ! -f "$LIB" ]]; then
  echo "    Library not found at $LIB"
  echo "    -> Run: sudo bash scripts/setup_token.sh"
else
  pkcs11-tool --module "$LIB" -L 2>&1 | sed 's/^/    /'
  echo
  echo "    If this says '(token not recognized)', the library is wrong for"
  echo "    this token model -- get the matching one from your CA."
fi
echo

echo "=== 5. Certificates on the token (no PIN needed) ==="
if [[ -f "$LIB" ]]; then
  pkcs11-tool --module "$LIB" -O 2>&1 | grep -E "Certificate Object|label:|ID:" | head -20 | sed 's/^/    /'
fi
echo

echo "Done. Layers 1-5 should all succeed before ERPNext signing will work."
