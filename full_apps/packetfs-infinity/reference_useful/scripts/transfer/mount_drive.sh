#!/usr/bin/env bash
# Env-driven wrapper to mount PacketFS (compile-on-close) via host helper
# Env (with defaults in Justfile):
#  MNT=./pfs.mnt IPROG_DIR=./iprog BLOB_NAME=pfs_vblob BLOB_SIZE=1073741824 BLOB_SEED=1337 WINDOW=65536 EMBED=1
set -euo pipefail
MNT="${MNT:-./pfs.mnt}"
IPROG_DIR="${IPROG_DIR:-./iprog}"
BLOB_NAME="${BLOB_NAME:-pfs_vblob}"
BLOB_SIZE="${BLOB_SIZE:-1073741824}"
BLOB_SEED="${BLOB_SEED:-1337}"
WINDOW="${WINDOW:-65536}"
EMBED="${EMBED:-1}"

mkdir -p "$MNT" "$IPROG_DIR"
exec bash scripts/pfsfs_mount_host.sh \
  --mnt "$MNT" \
  --iprog-dir "$IPROG_DIR" \
  --blob-name "$BLOB_NAME" \
  --blob-size "$BLOB_SIZE" \
  --blob-seed "$BLOB_SEED" \
  --window "$WINDOW" \
  --embed "$EMBED"
