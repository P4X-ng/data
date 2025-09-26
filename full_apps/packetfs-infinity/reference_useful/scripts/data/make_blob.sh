#!/usr/bin/env bash
set -euo pipefail
# Make a fast local blob in tmpfs (/dev/shm) for windowed streaming tests.
# Usage: make_blob.sh <path> <size_mb> [pattern]
#   path      : destination file path (e.g., /dev/shm/pfs_blob.bin)
#   size_mb   : size in MiB
#   pattern   : optional fill pattern: zero|rand|ramp (default: zero)

PATH_OUT=${1:-}
SIZE_MB=${2:-}
PATTERN=${3:-zero}

if [[ -z "$PATH_OUT" || -z "$SIZE_MB" ]]; then
  echo "usage: $0 <path> <size_mb> [pattern]" >&2
  exit 2
fi

mkdir -p "$(dirname "$PATH_OUT")"
SIZE_BYTES=$(( SIZE_MB * 1024 * 1024 ))

# Create sparse file quickly
fallocate -l "$SIZE_BYTES" "$PATH_OUT"

# Optional simple fill (small regions) without long-running writes
case "$PATTERN" in
  zero)
    : # already zeroed by sparse allocation
    ;;
  rand)
    # write 8 MiB random header tail to make it non-trivial
    dd if=/dev/urandom of="$PATH_OUT" bs=1M count=8 conv=notrunc status=none
    ;;
  ramp)
    python3 - "$PATH_OUT" <<'PY'
import sys, mmap, os
p=sys.argv[1]
fd=os.open(p, os.O_RDWR)
size=os.path.getsize(p)
with mmap.mmap(fd, size) as m:
    step=4096
    b = bytearray(range(256))
    for off in range(0, min(size, 8*1024*1024), step):
        m[off:off+256] = b
os.close(fd)
PY
    ;;
  *)
    echo "[make_blob] unknown pattern '$PATTERN', using zero" >&2 ;;
esac

echo "[make_blob] created $PATH_OUT ($SIZE_MB MiB) pattern=$PATTERN"