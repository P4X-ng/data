#!/usr/bin/env bash
set -euo pipefail
# Wrapper to run asset_spider.py with optional flags
# Usage: run_spider.sh <seeds> <allow> <max_pages> <range(0|1)> <compute_kind> <compute_endpoint>

SEEDS=${1:-}
ALLOW=${2:-}
MAXPAGES=${3:-50}
RANGE=${4:-0}
CKIND=${5:-}
CENDP=${6:-}

if [[ -z "$SEEDS" || -z "$ALLOW" ]]; then
  echo "usage: $0 <seeds> <allow> [max_pages] [range(0|1)] [compute_kind] [compute_endpoint]" >&2
  exit 2
fi

PY=/home/punk/.venv/bin/python
SP=scripts/spider/asset_spider.py

export PYTHONPATH=.
CMD=("$PY" "$SP" --seeds "$SEEDS" --allow "$ALLOW" --max-pages "$MAXPAGES")
if [[ "$RANGE" == "1" ]]; then CMD+=(--range-probe); fi
if [[ -n "$CKIND" ]]; then CMD+=(--compute-kind "$CKIND"); fi
if [[ -n "$CENDP" ]]; then CMD+=(--compute-endpoint "$CENDP"); fi

exec "${CMD[@]}"