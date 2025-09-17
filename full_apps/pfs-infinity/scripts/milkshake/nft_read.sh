#!/usr/bin/env bash
set -euo pipefail
# Read nftables counter for PORT
PORT=${1:-}
if [[ -z "$PORT" ]]; then
  echo "usage: $0 <PORT>" >&2
  exit 2
fi

sudo nft list counters | awk -v p="$PORT" '/name cnt_/ {name=$2} /packets/ {pk=$2} /bytes/ {by=$2; if (name=="cnt_"p) {print pk, by}}'