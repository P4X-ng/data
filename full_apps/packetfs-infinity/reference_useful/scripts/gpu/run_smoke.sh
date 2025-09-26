#!/usr/bin/env bash
# Helper: GPU smoke test wrapper for dev-gpu-smoke
# - Resolves default endpoint from WS_PORT if not supplied
# - Assembles args robustly and executes the Python bench via central venv
# Usage:
#   scripts/gpu/run_smoke.sh --venv /home/punk/.venv --path /dev/shm/pfs_blob.bin --imm 0 [--offset N] [--length N] [--endpoint URL] [--ws-port 8811]
set -euo pipefail

VENV=""
PATH_ARG=""
IMM_ARG=""
OFFSET_ARG=""
LENGTH_ARG=""
ENDPOINT_ARG=""
WS_PORT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV="$2"; shift 2;;
    --path) PATH_ARG="$2"; shift 2;;
    --imm) IMM_ARG="$2"; shift 2;;
    --offset) OFFSET_ARG="$2"; shift 2;;
    --length) LENGTH_ARG="$2"; shift 2;;
    --endpoint) ENDPOINT_ARG="$2"; shift 2;;
    --ws-port) WS_PORT="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "$VENV" || -z "$PATH_ARG" || -z "$IMM_ARG" ]]; then
  echo "usage: run_smoke.sh --venv VENV --path PATH --imm IMM [--offset N] [--length N] [--endpoint URL] [--ws-port PORT]" >&2
  exit 2
fi

# Determine endpoint
if [[ -z "$ENDPOINT_ARG" ]]; then
  if [[ -n "$WS_PORT" ]]; then
    ENDPOINT_ARG="http://127.0.0.1:${WS_PORT}"
  else
    # Fallback default
    ENDPOINT_ARG="http://127.0.0.1:8811"
  fi
fi

# Allow named-style inputs like 'path=/dev/shm/...', 'imm=0' which some callers pass
strip_prefix() {
  local val="$1"; shift
  local name="$1"; shift
  if [[ "$val" == ${name}=* ]]; then
    echo "${val#${name}=}"
  else
    echo "$val"
  fi
}
PATH_ARG=$(strip_prefix "$PATH_ARG" path)
IMM_ARG=$(strip_prefix "$IMM_ARG" imm)
OFFSET_ARG=$(strip_prefix "$OFFSET_ARG" offset)
LENGTH_ARG=$(strip_prefix "$LENGTH_ARG" length)
ENDPOINT_ARG=$(strip_prefix "$ENDPOINT_ARG" endpoint)

ARGS=("--endpoint" "$ENDPOINT_ARG" "--path" "$PATH_ARG" "--imm" "$IMM_ARG")
if [[ -n "$OFFSET_ARG" ]]; then ARGS+=("--offset" "$OFFSET_ARG"); fi
if [[ -n "$LENGTH_ARG" ]]; then ARGS+=("--length" "$LENGTH_ARG"); fi

echo "[gpu] counteq imm=${IMM_ARG} on ${PATH_ARG} $( [[ -n \"$OFFSET_ARG\" ]] && echo "offset=$OFFSET_ARG" ) $( [[ -n \"$LENGTH_ARG\" ]] && echo "length=$LENGTH_ARG" ) via ${ENDPOINT_ARG}/gpu/compute"
"${VENV}/bin/python" scripts/bench/gpu_bench.py "${ARGS[@]}"
