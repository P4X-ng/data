#!/usr/bin/env bash
set -euo pipefail
# Rebuild static UI assets for pfs-infinity
# - Copies app/static/* to .build/ui/
# - Leaves room to plug in a bundler/minifier later

ROOT_DIR=$(dirname "$(readlink -f "$0")")/..
cd "$ROOT_DIR"

SRC_DIR=app/static
OUT_DIR=.build/ui

if [ ! -d "$SRC_DIR" ]; then
  echo "[ui-rebuild] No $SRC_DIR directory found; nothing to rebuild" >&2
  exit 0
fi

mkdir -p "$OUT_DIR"
# Copy all static assets
rsync -a --delete "$SRC_DIR/" "$OUT_DIR/"

# Optional: very light HTML tidy (strip trailing spaces) without external deps
if [ -f "$OUT_DIR/index.html" ]; then
  sed -i 's/[[:space:]]\+$//' "$OUT_DIR/index.html"
fi

echo "[ui-rebuild] UI assets staged to $OUT_DIR"
