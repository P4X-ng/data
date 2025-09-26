#!/usr/bin/env bash
set -euo pipefail
# Clean build and cache artifacts for pfs-infinity

ROOT_DIR=$(dirname "$(readlink -f "$0")")/..
cd "$ROOT_DIR"

# Paths to clean
CLEAN_DIRS=(
  ".build/ui"
  "__pycache__"
  "**/__pycache__"
  "*.pytest_cache"
  "logs"
)

# Remove directories/files safely
for p in "${CLEAN_DIRS[@]}"; do
  # Use globstar for ** if available
  shopt -s nullglob globstar 2>/dev/null || true
  for match in $p; do
    if [ -e "$match" ]; then
      echo "[clean] removing $match"
      rm -rf -- "$match"
    fi
  done
  shopt -u nullglob globstar 2>/dev/null || true
done

echo "[clean] done"
