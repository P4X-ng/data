#!/usr/bin/env bash
# Unmount PacketFS (if mounted)
# Env: MNT=./pfs.mnt
set -euo pipefail
MNT="${MNT:-./pfs.mnt}"
if mountpoint -q "$MNT"; then
  if command -v fusermount3 >/dev/null 2>&1; then
    fusermount3 -u "$MNT" || true
  else
    fusermount -u "$MNT" || umount "$MNT" || true
  fi
  echo "[pfsfs] unmounted $MNT"
else
  echo "[pfsfs] not mounted: $MNT"
fi
