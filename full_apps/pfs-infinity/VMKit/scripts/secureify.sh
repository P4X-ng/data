#!/usr/bin/env bash
# Make a Quickemu .conf secure and fix relative download paths to absolute
# Usage: secureify.sh NAME VMS_DIR DOWNLOADS_DIR ABS_DOWNLOADS
set -euo pipefail
NAME=${1:?name required}
VMS_DIR=${2:?vms dir}
DOWNLOADS_DIR=${3:?downloads dir}
ABS_DOWNLOADS=${4:?abs downloads root}

conf=""
if [ -f "$VMS_DIR/$NAME.conf" ]; then
  conf="$VMS_DIR/$NAME.conf"
elif [ -f "$DOWNLOADS_DIR/$NAME.conf" ]; then
  conf="$DOWNLOADS_DIR/$NAME.conf"
else
  echo "No conf found for $NAME in $VMS_DIR or $DOWNLOADS_DIR" >&2
  exit 2
fi

# Fix relative paths to be absolute under ABS_DOWNLOADS/downloads
sed -i "s#\(disk_img=\)\"\./\?downloads/\([^\"]\+\)\"#\1\"$ABS_DOWNLOADS/downloads/\2\"#" "$conf" || true
sed -i "s#\(iso=\)\"\./\?downloads/\([^\"]\+\)\"#\1\"$ABS_DOWNLOADS/downloads/\2\"#" "$conf" || true

# Skip SB/TPM for macOS/BSD families or if SECURE=0
if grep -qiE 'guest_os=.*(mac|darwin|bsd)' "$conf" || [ "${SECURE:-1}" = "0" ]; then
  echo "Skipping SB/TPM toggle for $conf (guest_os mac/bsd or SECURE=0)"
  exit 0
fi

# Ensure secure boot and TPM on
if grep -q '^secureboot=' "$conf"; then
  sed -i 's/^secureboot=.*/secureboot="1"/' "$conf"
else
  echo 'secureboot="1"' >> "$conf"
fi
if grep -q '^tpm=' "$conf"; then
  sed -i 's/^tpm=.*/tpm="1"/' "$conf"
else
  echo 'tpm="1"' >> "$conf"
fi

echo "Secured: $conf (secureboot=1, tpm=1)"
