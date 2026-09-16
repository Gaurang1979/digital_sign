#!/usr/bin/env bash
#
# Server-side setup for DSC USB token signing on Ubuntu 22.04.
#
# Installs PC/SC middleware, registers the token's USB ID with libccid
# if missing, installs the vendor PKCS#11 library, and sets udev
# permissions so the ERPNext service account can reach the token.
#
# Run as:  sudo bash scripts/setup_token.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRIVER_DIR="$REPO_ROOT/drivers/HYP2003-Linux-x86_64"
LIB_DEST="/opt/hypersecu"
LIB_NAME="libcastle_v2.so.1.0.0"
CCID_PLIST="/usr/lib/pcsc/drivers/ifd-ccid.bundle/Contents/Info.plist"

# USB IDs of tokens known to need registering with libccid.
# Format: "VENDOR_ID PRODUCT_ID Friendly Name"
KNOWN_TOKENS=(
  "0x2CCF 0x080A HyperPKI HYP2003"
  "0x055C 0x0223 mToken CryptoIDA"
)

if [[ $EUID -ne 0 ]]; then
  echo "Run this with sudo." >&2
  exit 1
fi

echo "==> Installing PC/SC middleware"
# pcscd needs libpcsclite1 at a matching version. If the security repo
# is unreachable, apt may hold a newer libpcsclite1 than the pcscd it
# can see; --allow-downgrades lets them line up.
apt-get install -y opensc pcscd pcsc-tools || {
  echo "!! Standard install failed. Retrying with version alignment..."
  apt-get install -y --allow-downgrades opensc pcscd pcsc-tools libpcsclite1=1.9.5-3
}

systemctl enable --now pcscd

echo "==> Registering token USB IDs with libccid (if missing)"
if [[ ! -f "$CCID_PLIST" ]]; then
  echo "!! $CCID_PLIST not found -- is libccid installed?" >&2
  exit 1
fi

cp -n "$CCID_PLIST" "${CCID_PLIST}.orig" 2>/dev/null || true

for entry in "${KNOWN_TOKENS[@]}"; do
  read -r vid pid name <<<"$entry"
  if grep -qi "$vid" "$CCID_PLIST"; then
    echo "    $name ($vid) already registered, skipping"
    continue
  fi
  echo "    adding $name ($vid:$pid)"
  python3 - "$CCID_PLIST" "$vid" "$pid" "$name" <<'PYEOF'
import sys
path, vid, pid, name = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

with open(path) as f:
    lines = f.readlines()

def insert(lines, key, value):
    # Append to the array belonging to <key>, immediately before that
    # array's closing tag. All three arrays are positional, so the new
    # entry must land at the same index in each.
    k = next(i for i, l in enumerate(lines) if f"<key>{key}</key>" in l)
    close = next(i for i in range(k, len(lines)) if "</array>" in lines[i])
    lines.insert(close, f"\t\t<string>{value}</string>\n")
    return lines

lines = insert(lines, "ifdVendorID", vid)
lines = insert(lines, "ifdProductID", pid)
lines = insert(lines, "ifdFriendlyName", name)

with open(path, "w") as f:
    f.writelines(lines)
PYEOF
done

systemctl restart pcscd

echo "==> Installing vendor PKCS#11 library"
if [[ ! -f "$DRIVER_DIR/redist/$LIB_NAME" ]]; then
  echo "!! $DRIVER_DIR/redist/$LIB_NAME not found." >&2
  echo "   Obtain the Linux PKCS#11 library from your CA/token vendor" >&2
  echo "   and place it there, then re-run." >&2
  exit 1
fi

mkdir -p "$LIB_DEST"
cp "$DRIVER_DIR/redist/$LIB_NAME" "$LIB_DEST/"
chmod 755 "$LIB_DEST/$LIB_NAME"

echo "==> Applying udev rules for non-root token access"
bash "$DRIVER_DIR/config/config.sh"

echo
echo "Setup complete."
echo
echo "Plug in the token, then verify:"
echo "  pkcs11-tool --module $LIB_DEST/$LIB_NAME -L"
echo "  pkcs11-tool --module $LIB_DEST/$LIB_NAME -O"
echo
echo "Copy the ID of the certificate issued in your name into"
echo "Digital Sign Settings -> Certificate ID (hex)."
