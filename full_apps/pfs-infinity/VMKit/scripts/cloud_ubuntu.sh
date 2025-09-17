#!/usr/bin/env bash
# Create a secure Quickemu config for Ubuntu cloud image with cloud-init
# Usage: cloud_ubuntu.sh NAME VERSION DOWNLOADS_DIR ABS_ROOT VMS_DIR
set -euo pipefail
NAME=${1:?name}
VERSION=${2:?version (22.04|24.04)}
DOWNLOADS_DIR=${3:?downloads}
ABS_ROOT=${4:?abs root}
VMS_DIR=${5:?vms dir}

case "$VERSION" in
  22.04) SERIES=jammy;;
  24.04) SERIES=noble;;
  *) echo "Unsupported Ubuntu version: $VERSION" >&2; exit 2;;
esac

IMG1="$SERIES-server-cloudimg-amd64.img"
IMG2="ubuntu-$VERSION-server-cloudimg-amd64.img"
URLBASE="https://cloud-images.ubuntu.com/$SERIES/current"
URL="$URLBASE/$IMG1"
if ! wget -q --spider "$URL"; then URL="$URLBASE/$IMG2"; IMG1="$IMG2"; fi
IMG="$IMG1"

mkdir -p "$DOWNLOADS_DIR/ubuntu-$VERSION"
if [ ! -f "$DOWNLOADS_DIR/ubuntu-$VERSION/$IMG" ]; then
  echo "Downloading $URL"
  wget -O "$DOWNLOADS_DIR/ubuntu-$VERSION/$IMG" "$URL"
else
  echo "Using existing image: $DOWNLOADS_DIR/ubuntu-$VERSION/$IMG"
fi

# Create cloud-init seed (default user 'user')
SEED_ISO=$("$(dirname "$0")/create-cloudinit.sh" "$NAME" "$SERIES" "$DOWNLOADS_DIR" "$ABS_ROOT" "${CLOUDINIT_USER:-user}" "${CLOUDINIT_PASSWORD:-}")

CONF="$VMS_DIR/$NAME.conf"
echo "guest_os=\"linux\"" > "$CONF"
echo "disk_img=\"$ABS_ROOT/downloads/ubuntu-$VERSION/$IMG\"" >> "$CONF"
echo "cloud_init=\"$SEED_ISO\"" >> "$CONF"
echo "secureboot=\"1\"" >> "$CONF"
echo "tpm=\"1\"" >> "$CONF"
echo "hostfwd=\"tcp::2222-:22\"" >> "$CONF"
chmod 0644 "$CONF"
echo "Created secure cloud conf with cloud-init: $CONF"
