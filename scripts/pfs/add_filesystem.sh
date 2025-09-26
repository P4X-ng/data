#!/usr/bin/env bash
# Add a host filesystem (block device partition) read-only and sync into PacketFS via pfsrsync
# Usage: add_filesystem.sh <device> <mount_path> <name> <target_host:port>
# Example: add_filesystem.sh /dev/sda1 /mnt/data_ro data localhost:8811

set -euo pipefail

DEVICE=${1:-}
MNT=${2:-}
LABEL=${3:-}
TARGET=${4:-}

INFO='[*]'
OK='[+]'
ERR='[!]'

if [[ -z "$DEVICE" || -z "$MNT" || -z "$LABEL" || -z "$TARGET" ]]; then
  echo "$ERR usage: $0 <device> <mount_path> <name> <target_host:port>" >&2
  exit 2
fi

# Sanity checks
if [[ ! -b "$DEVICE" ]]; then
  echo "$ERR $DEVICE is not a block device" >&2
  exit 1
fi

if ! command -v pfsrsync >/dev/null 2>&1; then
  echo "$ERR pfsrsync not found in PATH. Please install or export PATH to it." >&2
  exit 1
fi

# Mount read-only, safest flags
echo "$INFO creating mount dir: $MNT"
sudo mkdir -p "$MNT"

# Determine filesystem type (best effort)
FSTYPE=$(lsblk -no FSTYPE "$DEVICE" | head -n1 || true)

echo "$INFO mounting $DEVICE ($FSTYPE) at $MNT read-only"
# NB: avoid automounts; use noatime,nosuid,nodev,noexec where possible
# Some FS may reject some flags; we attempt and then fallback to minimal ro
if ! sudo mount -o ro,nosuid,nodev,noexec,noatime "$DEVICE" "$MNT" 2>/dev/null; then
  echo "$INFO retrying minimal ro mount"
  sudo mount -o ro "$DEVICE" "$MNT"
fi

echo "$OK mounted $DEVICE -> $MNT"

# Destination path inside PacketFS mount on the remote side
DEST_PATH="/mnt/packetfs/$LABEL"

# Ensure destination path hint (best effort): this triggers server to create target directory if supported
echo "$INFO syncing $MNT -> $TARGET:$DEST_PATH via pfsrsync"

# Allow caller to pass extra flags via env PFSRSYNC_FLAGS
PFSRSYNC_FLAGS=${PFSRSYNC_FLAGS:-"--compress"}

# Perform initial sync
pfsrsync "$MNT" "$TARGET:$DEST_PATH" $PFSRSYNC_FLAGS

# Optional watch mode if requested (requires inotifywait)
if [[ "${WATCH:-0}" == "1" ]]; then
  if ! command -v inotifywait >/dev/null 2>&1; then
    echo "$ERR WATCH=1 requested but inotify-tools not installed; install 'inotify-tools' to enable continuous sync" >&2
    exit 0
  fi
  echo "$INFO entering watch mode (inotify); changes under $MNT will trigger resync"
  while true; do
    inotifywait -r -e create,modify,delete,move "$MNT" >/dev/null 2>&1 || true
    echo "$INFO change detected; syncing..."
    pfsrsync "$MNT" "$TARGET:$DEST_PATH" $PFSRSYNC_FLAGS || true
    sleep 1
  done
fi

echo "$OK filesystem $DEVICE exposed to PacketFS as $DEST_PATH"
