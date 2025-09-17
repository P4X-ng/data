#!/usr/bin/env bash
# DEMO: Create a cloud-init NoCloud seed ISO with password login enabled
# Writes DEMO banners to /etc/motd and /etc/issue
# Usage: demo/create-cloudinit-demo.sh NAME SERIES DOWNLOADS_DIR ABS_ROOT [USERNAME] [PASSWORD]
set -euo pipefail
NAME=${1:?name}
SERIES=${2:?series}
DOWNLOADS_DIR=${3:?downloads}
ABS_ROOT=${4:?abs root}
USERNAME=${5:-demo}
PASSWORD=${6:-demo}

OUT_DIR="$DOWNLOADS_DIR/ubuntu-24.04"
SEED_ISO="$OUT_DIR/${NAME}-seed-demo.iso"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

USER_DATA="$TMP_DIR/user-data"
META_DATA="$TMP_DIR/meta-data"
HASHED_PASS=$(openssl passwd -6 "$PASSWORD")

cat > "$USER_DATA" <<'EOC'
#cloud-config
write_files:
  - path: /etc/motd
    content: |
      ###############################################################
      #                           DEMO                              #
      #                  NOT FOR PRODUCTION                         #
      ###############################################################
  - path: /etc/issue
    content: |
      ###############################################################
      #                           DEMO                              #
      #                  NOT FOR PRODUCTION                         #
      ###############################################################
EOC

cat >> "$USER_DATA" <<EOF
users:
  - name: $USERNAME
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: false
    plain_text_passwd: false
    passwd: $HASHED_PASS
ssh_pwauth: true
chpasswd:
  expire: false
package_update: true
runcmd:
  - [ sh, -c, "systemctl enable ssh && systemctl start ssh || systemctl restart ssh" ]
EOF

cat > "$META_DATA" <<EOF
instance-id: $NAME
local-hostname: $NAME
EOF

mkdir -p "$OUT_DIR"
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
echo "$SEED_ISO"
