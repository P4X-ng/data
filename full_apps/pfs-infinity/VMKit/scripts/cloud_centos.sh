#!/usr/bin/env bash
# Create a secure Quickemu config for CentOS Stream cloud image with cloud-init (random password by default)
# Usage: cloud_centos.sh NAME VERSION DOWNLOADS_DIR ABS_ROOT VMS_DIR
set -euo pipefail
NAME=${1:?name}
VERSION=${2:?version (9|8)}
DOWNLOADS_DIR=${3:?downloads}
ABS_ROOT=${4:?abs root}
VMS_DIR=${5:?vms dir}

case "$VERSION" in
  9) STREAM="9-stream";;
  8) STREAM="8-stream";;
  *) echo "Unsupported CentOS Stream version: $VERSION" >&2; exit 2;;
esac

OUT_DIR="$DOWNLOADS_DIR/centos-$VERSION"
BASE_URL="https://cloud.centos.org/centos/$STREAM/x86_64/images"
IMG_NAME="CentOS-Stream-GenericCloud-$VERSION-latest.x86_64.qcow2"
URL="$BASE_URL/$IMG_NAME"
if ! wget -q --spider "$URL"; then
  PAGE=$(mktemp); trap 'rm -f "$PAGE"' EXIT; wget -q -O "$PAGE" "$BASE_URL/" || true
  FOUND=$(grep -oE "CentOS-Stream-GenericCloud-$VERSION-[^\" ]+\.x86_64\.qcow2" "$PAGE" | tail -n 1 || true)
  if [ -n "$FOUND" ]; then IMG_NAME="$FOUND"; URL="$BASE_URL/$FOUND"; else
    echo "Could not find CentOS Stream cloud image at $BASE_URL" >&2; exit 3
  fi
fi

mkdir -p "$OUT_DIR"
if [ ! -f "$OUT_DIR/$IMG_NAME" ]; then
  echo "Downloading $URL"
  wget -O "$OUT_DIR/$IMG_NAME" "$URL"
else
  echo "Using existing image: $OUT_DIR/$IMG_NAME"
fi

# Create cloud-init seed (default user 'user', override with CLOUDINIT_USER/PASSWORD)
SEED_ISO=$("$(dirname "$0")/create-cloudinit.sh" "$NAME" "centos-$VERSION" "$DOWNLOADS_DIR" "$ABS_ROOT" "${CLOUDINIT_USER:-user}" "${CLOUDINIT_PASSWORD:-}")

CONF="$VMS_DIR/$NAME.conf"
echo "guest_os=\"linux\"" > "$CONF"
echo "disk_img=\"$ABS_ROOT/downloads/centos-$VERSION/$IMG_NAME\"" >> "$CONF"
echo "cloud_init=\"$SEED_ISO\"" >> "$CONF"
# Verify checksum if available
CHECK="$OUT_DIR/CHECKSUM"
if wget -q -O "$CHECK" "$BASE_URL/CHECKSUM"; then
  HASH=$(grep -E "SHA256 \($IMG_NAME\) =" "$CHECK" | sed -E 's/.*=\s*//')
  if [ -n "$HASH" ]; then echo "$HASH  $OUT_DIR/$IMG_NAME" | sha256sum -c - || { echo "SHA256 verification failed for $IMG_NAME" >&2; exit 5; }; fi
else
  echo "Warning: CentOS CHECKSUM not found; skipping verification" >&2
fi

echo "secureboot=\"1\"" >> "$CONF"
echo "tpm=\"1\"" >> "$CONF"
echo "hostfwd=\"tcp::2222-:22\"" >> "$CONF"
chmod 0644 "$CONF"
echo "Created secure CentOS Stream cloud conf with cloud-init: $CONF"
