#!/usr/bin/env bash
# Create a cloud-init NoCloud seed ISO for Quickemu
# Usage: create-cloudinit.sh NAME SERIES DOWNLOADS_DIR ABS_ROOT [USERNAME] [PASSWORD]
# Behavior:
# - Default: random password generated and printed to stderr; SSH key added if available
# - If PASSWORD argument provided (or CLOUDINIT_PASSWORD env), uses that password instead
set -euo pipefail

NAME=${1:?name required}
SERIES=${2:?series required (e.g., noble, jammy)}
DOWNLOADS_DIR=${3:?downloads dir}
ABS_ROOT=${4:?abs repo root}
USERNAME=${5:-user}
PASSWORD=${6:-}

OUT_DIR="$DOWNLOADS_DIR/$SERIES"
SEED_ISO="$OUT_DIR/${NAME}-seed.iso"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

# Generate user-data & meta-data
USER_DATA="$TMP_DIR/user-data"
META_DATA="$TMP_DIR/meta-data"

# Determine SSH public key
PUBKEY=""
# Allow explicit key override via env
if [ -n "${CLOUDINIT_PUBKEY:-}" ] && [ -f "${CLOUDINIT_PUBKEY}" ]; then
  PUBKEY=$(cat "${CLOUDINIT_PUBKEY}")
fi
for k in "$HOME/.ssh/id_ed25519.pub" "$HOME/.ssh/id_rsa.pub" "$HOME/.ssh/id_ecdsa.pub"; do
  if [ -z "$PUBKEY" ] && [ -f "$k" ]; then PUBKEY=$(cat "$k"); break; fi
done

# Always set a password (generated if not provided) and include SSH key if found
# NOTE: Avoid pipelines that can trigger SIGPIPE under 'set -o pipefail'
# Prefer Python's secrets; fallback to OpenSSL; final fallback tolerates SIGPIPE
generate_password() {
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
import secrets, string
print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16)))
PY
  elif command -v openssl >/dev/null 2>&1; then
    # Tolerate pipeline SIGPIPE with a fallback default
    openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 16 || printf 'A1b2C3d4E5f6G7h8'
  else
    # Minimal fallback; tolerate SIGPIPE
    tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16 || printf 'A1b2C3d4E5f6G7h8'
  fi
}
if [ -z "$PASSWORD" ]; then
  PASSWORD="$(generate_password)"
fi
HASHED_PASS=$(openssl passwd -6 "$PASSWORD")
cat > "$USER_DATA" <<EOF
#cloud-config
users:
  - name: $USERNAME
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: false
    plain_text_passwd: false
    passwd: $HASHED_PASS
$( [ -n "$PUBKEY" ] && echo "ssh_authorized_keys:\n      - $PUBKEY" )
ssh_pwauth: true
chpasswd:
  expire: false
package_update: true
write_files:
  - path: /etc/motd
    permissions: '0644'
    content: |
      ==============================================
      VMKit cloud provisioning
      Username: $USERNAME
      Password: $PASSWORD
      NOTE: CHANGE THIS PASSWORD IMMEDIATELY
      ==============================================
  - path: /etc/issue
    permissions: '0644'
    content: |
      VMKit login on \l
      User: $USERNAME  Password: $PASSWORD
      CHANGE PASSWORD NOW
runcmd:
  - [ sh, -c, "systemctl enable ssh && systemctl start ssh || systemctl restart ssh" ]
EOF

cat > "$META_DATA" <<EOF
instance-id: $NAME
local-hostname: $NAME
EOF

mkdir -p "$OUT_DIR"

# Create ISO
if command -v cloud-localds >/dev/null 2>&1; then
  cloud-localds "$SEED_ISO" "$USER_DATA" "$META_DATA"
elif command -v genisoimage >/dev/null 2>&1; then
  genisoimage -output "$SEED_ISO" -volid cidata -joliet -rock "$TMP_DIR"
elif command -v xorrisofs >/dev/null 2>&1; then
  xorrisofs -output "$SEED_ISO" -volid cidata -joliet -rock "$TMP_DIR"
else
  echo "No ISO tool found. Install cloud-image-utils or genisoimage/xorrisofs." >&2
  exit 1
fi

chmod 0644 "$SEED_ISO"
# Store credentials and print to stderr (seed path remains on stdout)
CREDS_FILE="$OUT_DIR/${NAME}-credentials.txt"
{
  echo "name=$NAME"
  echo "username=$USERNAME"
  echo "password=$PASSWORD"
  echo "seed_iso=$SEED_ISO"
} > "$CREDS_FILE"
echo "[cloud-init] Credentials for $NAME -> user: $USERNAME pass: $PASSWORD (stored: $CREDS_FILE)" >&2
echo "$SEED_ISO"
