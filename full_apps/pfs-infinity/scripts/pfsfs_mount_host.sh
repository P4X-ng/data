#!/usr/bin/env bash
set -euo pipefail
# Mount PacketFS FUSE on the host and prepare a share directory for VM guest via virtiofs
# Usage:
#   scripts/pfsfs_mount_host.sh \
#     --mnt .vm/pfs.mnt \
#     --iprog-dir ./iprog \
#     --blob-name pfs_vblob \
#     --blob-size 1073741824 \
#     [--blob-seed 1337] [--window 65536] [--embed 1]
#
# Notes:
# - Uses central venv at /home/punk/.venv per repo rules.
# - Falls back to invoking module via PYTHONPATH=realsrc if CLI is not installed.
# - Idempotent: if already mounted, exits success.

MNT=""
IPROG_DIR=""
BLOB_NAME="pfs_vblob"
BLOB_SIZE="1073741824"
BLOB_SEED="1337"
WINDOW="65536"
EMBED="1"

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mnt) MNT=${2:?}; shift 2;;
    --iprog-dir) IPROG_DIR=${2:?}; shift 2;;
    --blob-name) BLOB_NAME=${2:?}; shift 2;;
    --blob-size) BLOB_SIZE=${2:?}; shift 2;;
    --blob-seed) BLOB_SEED=${2:?}; shift 2;;
    --window) WINDOW=${2:?}; shift 2;;
    --embed) EMBED=${2:?}; shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "$MNT" || -z "$IPROG_DIR" ]]; then
  echo "usage: $0 --mnt MNT_DIR --iprog-dir IPROG_DIR [--blob-name NAME] [--blob-size BYTES] [--blob-seed N] [--window N] [--embed 0|1]" >&2
  exit 2
fi

mkdir -p "$MNT" "$IPROG_DIR"

# If already mounted, exit success
if mountpoint -q "$MNT"; then
  echo "[pfsfs] Already mounted at $MNT"
  exit 0
fi

VENV=/home/punk/.venv
PFSFS_BIN="$VENV/bin/pfsfs-mount"
PYBIN="$VENV/bin/python"

# Try CLI first
if [[ -x "$PFSFS_BIN" ]]; then
  echo "[pfsfs] mounting via $PFSFS_BIN (background)"
  set +e
  "$PFSFS_BIN" \
    --iprog-dir "$IPROG_DIR" \
    --mount "$MNT" \
    --blob-name "$BLOB_NAME" \
    --blob-size "$BLOB_SIZE" \
    --blob-seed "$BLOB_SEED" \
    --window "$WINDOW" \
    ${EMBED:+--embed-pvrt} &
  pid=$!
  set -e
  # Wait up to ~5s for mount to appear
  for i in {1..50}; do
    if mountpoint -q "$MNT"; then
      echo "[pfsfs] mounted at $MNT (pid $pid)"
      exit 0
    fi
    sleep 0.1
  done
  echo "[pfsfs] mount did not appear at $MNT within timeout" >&2
  exit 1
fi

# Fallback to module path using realsrc at repo root (../../.. from this script)
if [[ -x "$PYBIN" ]]; then
  echo "[pfsfs] mounting via module fallback (background)"
  REPO_ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
  set +e
  env PYTHONPATH="$REPO_ROOT/realsrc" "$PYBIN" -m packetfs.filesystem.pfsfs_mount \
    --iprog-dir "$IPROG_DIR" \
    --mount "$MNT" \
    --blob-name "$BLOB_NAME" \
    --blob-size "$BLOB_SIZE" \
    --blob-seed "$BLOB_SEED" \
    --window "$WINDOW" \
    ${EMBED:+--embed-pvrt} &
  pid=$!
  set -e
  for i in {1..50}; do
    if mountpoint -q "$MNT"; then
      echo "[pfsfs] mounted at $MNT (pid $pid)"
      exit 0
    fi
    sleep 0.1
  done
  echo "[pfsfs] mount did not appear at $MNT within timeout (fallback)" >&2
  exit 1
fi

echo "[pfsfs] Could not find $PFSFS_BIN or $PYBIN" >&2
exit 1
