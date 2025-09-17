#!/usr/bin/env bash
# Create a secure Quickemu config for Fedora Cloud Base with cloud-init (random password by default)
# Usage: cloud_fedora.sh NAME VERSION DOWNLOADS_DIR ABS_ROOT VMS_DIR
set -euo pipefail
NAME=${1:?name}
VERSION=${2:?version}
DOWNLOADS_DIR=${3:?downloads}
ABS_ROOT=${4:?abs root}
VMS_DIR=${5:?vms dir}

SERIES="fedora-$VERSION"
OUT_DIR="$DOWNLOADS_DIR/fedora-$VERSION"
mkdir -p "$OUT_DIR"

BASE_URL="https://download.fedoraproject.org/pub/fedora/linux/releases/$VERSION/Cloud/x86_64/images"
IMG_CAND="$BASE_URL/Fedora-Cloud-Base-Generic.x86_64-$VERSION-latest.qcow2"
IMG_NAME="Fedora-Cloud-Base-Generic.x86_64-$VERSION-latest.qcow2"
if ! wget -q --spider "$IMG_CAND"; then
  # Fallback: try to fetch listing and pick latest .qcow2
  PAGE=$(mktemp); trap 'rm -f "$PAGE"' EXIT; wget -q -O "$PAGE" "$BASE_URL/" || true
FOUND=$(grep -oE "Fedora-Cloud-Base-Generic\.x86_64-[0-9]+[^\" ]*\.qcow2" "$PAGE" | tail -n 1 || true)
  if [ -n "$FOUND" ]; then IMG_NAME="$FOUND"; IMG_CAND="$BASE_URL/$FOUND"; else
    echo "Could not find Fedora Cloud Base image at $BASE_URL" >&2; exit 2
  fi
fi

if [ ! -f "$OUT_DIR/$IMG_NAME" ]; then
  echo "Downloading $IMG_CAND"
  wget -O "$OUT_DIR/$IMG_NAME" "$IMG_CAND"
else
  echo "Using existing image: $OUT_DIR/$IMG_NAME"
fi

# Create cloud-init seed (default user 'user', override with CLOUDINIT_USER/PASSWORD)
SEED_ISO=$("$(dirname "$0")/create-cloudinit.sh" "$NAME" "$SERIES" "$DOWNLOADS_DIR" "$ABS_ROOT" "${CLOUDINIT_USER:-user}" "${CLOUDINIT_PASSWORD:-}")

CONF="$VMS_DIR/$NAME.conf"
echo "guest_os=\"linux\"" > "$CONF"
echo "disk_img=\"$ABS_ROOT/downloads/fedora-$VERSION/$IMG_NAME\"" >> "$CONF"
echo "cloud_init=\"$SEED_ISO\"" >> "$CONF"
# Verify checksum if available
CHECK="$OUT_DIR/CHECKSUM"
if wget -q -O "$CHECK" "$BASE_URL/CHECKSUM"; then
  HASH=$(grep -E "SHA256 \($IMG_NAME\) =" "$CHECK" | sed -E 's/.*=\s*//')
  if [ -n "$HASH" ]; then echo "$HASH  $OUT_DIR/$IMG_NAME" | sha256sum -c - || { echo "SHA256 verification failed for $IMG_NAME" >&2; exit 5; }; fi
else
  echo "Warning: Fedora CHECKSUM not found; skipping verification" >&2
fi

echo "secureboot=\"1\"" >> "$CONF"
echo "tpm=\"1\"" >> "$CONF"
echo "hostfwd=\"tcp::2222-:22\"" >> "$CONF"
chmod 0644 "$CONF"
echo "Created secure Fedora cloud conf with cloud-init: $CONF"
