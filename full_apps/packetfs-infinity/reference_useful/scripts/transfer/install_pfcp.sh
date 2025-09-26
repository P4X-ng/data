#!/usr/bin/env bash
# Install pfcp symlink into central venv
set -euo pipefail

VENV_PATH="${1:-}"
if [[ -z "$VENV_PATH" ]]; then
  echo "usage: install_pfcp.sh VENV_PATH" >&2
  exit 2
fi

PFCP_SRC="$(pwd)/scripts/pfcp"
PFCP_DST="${VENV_PATH}/bin/pfcp"

if [[ -f "$PFCP_DST" || -L "$PFCP_DST" ]]; then
  echo "[pfcp] Already installed at $PFCP_DST"
else
  ln -s "$PFCP_SRC" "$PFCP_DST"
  echo "[pfcp] Installed to $PFCP_DST"
  echo "[pfcp] Usage: pfcp file.txt server:"
fi
