#!/usr/bin/env bash
# Env-driven translator daemon (watch-dir -> IPROGs)
# Env: WATCH_DIR=./ingest OUT_DIR=./iprog BLOB_NAME=pfs_vblob BLOB_SIZE=1073741824 BLOB_SEED=1337 WINDOW=65536
set -euo pipefail
WATCH_DIR="${WATCH_DIR:-./ingest}"
OUT_DIR="${OUT_DIR:-./iprog}"
BLOB_NAME="${BLOB_NAME:-pfs_vblob}"
BLOB_SIZE="${BLOB_SIZE:-1073741824}"
BLOB_SEED="${BLOB_SEED:-1337}"
WINDOW="${WINDOW:-65536}"

mkdir -p "$WATCH_DIR" "$OUT_DIR"
PYBIN=/home/punk/.venv/bin/python

if [[ ! -x "$PYBIN" ]]; then
  echo "[/home/punk/.venv/bin/python not found or not executable]" >&2
  exit 3
fi

exec "$PYBIN" -m packetfs.tools.translate_daemon \
  --watch-dir "$WATCH_DIR" \
  --out-dir "$OUT_DIR" \
  --blob-name "$BLOB_NAME" \
  --blob-size "$BLOB_SIZE" \
  --blob-seed "$BLOB_SEED" \
  --window "$WINDOW"
