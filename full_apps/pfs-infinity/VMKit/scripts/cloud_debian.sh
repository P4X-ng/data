#!/usr/bin/env bash
# Create a secure Quickemu config for Debian cloud image with cloud-init (random password by default)
# Usage: cloud_debian.sh NAME VERSION DOWNLOADS_DIR ABS_ROOT VMS_DIR
set -euo pipefail
NAME=${1:?name}
VERSION=${2:?version (12|11)}
DOWNLOADS_DIR=${3:?downloads}
ABS_ROOT=${4:?abs root}
VMS_DIR=${5:?vms dir}

case "$VERSION" in
  12) SERIES=bookworm;;
  11) SERIES=bullseye;;
  *) echo "Unsupported Debian version: $VERSION" >&2; exit 2;;
esac

mkdir -p "$DOWNLOADS_DIR/debian-$VERSION"
URLBASE="https://cloud.debian.org/images/cloud/$SERIES/latest"
CAND1="debian-$VERSION-genericcloud-amd64.qcow2"
CAND2="debian-$VERSION-generic-amd64.qcow2"
IMG=""
if wget -q --spider "$URLBASE/$CAND1"; then IMG="$CAND1"; elif wget -q --spider "$URLBASE/$CAND2"; then IMG="$CAND2"; else
  echo "Could not find Debian cloud image at $URLBASE" >&2; exit 3
fi
OUT_DIR="$DOWNLOADS_DIR/debian-$VERSION"
TARGET="$OUT_DIR/$IMG"
if [ ! -f "$TARGET" ]; then
  echo "Downloading $URLBASE/$IMG"
  wget -O "$TARGET" "$URLBASE/$IMG"
else
  echo "Using existing image: $TARGET"
fi

# Fetch checksums and verify (prefer SHA512)
( cd "$OUT_DIR" && {
    SUM_OK=0
    if wget -q -O SHA512SUMS "$URLBASE/SHA512SUMS"; then
      if grep -E "\s$IMG$" SHA512SUMS | sha512sum -c -; then SUM_OK=1; else echo "SHA512 verification failed for $IMG" >&2; exit 4; fi
    elif wget -q -O SHA256SUMS "$URLBASE/SHA256SUMS"; then
      if grep -E "\s$IMG$" SHA256SUMS | sha256sum -c -; then SUM_OK=1; else echo "SHA256 verification failed for $IMG" >&2; exit 4; fi
    else
      echo "Warning: No checksum file available at $URLBASE; skipping verification" >&2
      SUM_OK=1
    fi
    [ "$SUM_OK" = 1 ]
  } )

# cloud-init seed (default user 'user', random password unless CLOUDINIT_PASSWORD provided)
SEED_ISO=$("$(dirname "$0")/create-cloudinit.sh" "$NAME" "$SERIES" "$DOWNLOADS_DIR" "$ABS_ROOT" "${CLOUDINIT_USER:-user}" "${CLOUDINIT_PASSWORD:-}")

CONF="$VMS_DIR/$NAME.conf"
echo "guest_os=\"linux\"" > "$CONF"
echo "disk_img=\"$ABS_ROOT/downloads/debian-$VERSION/$IMG\"" >> "$CONF"
echo "cloud_init=\"$SEED_ISO\"" >> "$CONF"
echo "secureboot=\"1\"" >> "$CONF"
echo "tpm=\"1\"" >> "$CONF"
echo "hostfwd=\"tcp::2222-:22\"" >> "$CONF"
chmod 0644 "$CONF"
echo "Created secure Debian cloud conf with cloud-init: $CONF"
