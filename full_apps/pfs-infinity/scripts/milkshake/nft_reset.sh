#!/usr/bin/env bash
set -euo pipefail
PORT=${1:-}
if [[ -z "$PORT" ]]; then
  echo "usage: $0 <PORT>" >&2
  exit 2
fi

sudo nft reset counters name cnt_${PORT} || true