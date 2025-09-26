#!/usr/bin/env bash
# Program smoke against /gpu/program with HTTPS and -k
# Usage: run_program_smoke.sh --path PATH [--endpoint URL] [--offset N] [--length N] [--program JSON] [--ws-port PORT]
set -euo pipefail

# Prefer env-based configuration (PFS_* or standard names), CLI flags override
ENDPOINT="${ENDPOINT:-${PFS_ENDPOINT:-}}"
PATH_IN="${FILE:-${PFS_FILE:-}}"
OFFSET="${OFFSET:-${PFS_OFFSET:-}}"
LENGTH="${LENGTH:-${PFS_LENGTH:-}}"
PROGRAM='[{"op":"xor","imm":255},{"op":"counteq","imm":0}]'
PROGRAM="${PROGRAM:-${PFS_PROGRAM:-$PROGRAM}}"
WS_PORT="${WS_PORT:-${PFS_WS_PORT:-8811}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint) ENDPOINT="$2"; shift 2;;
    --path) PATH_IN="$2"; shift 2;;
    --offset) OFFSET="$2"; shift 2;;
    --length) LENGTH="$2"; shift 2;;
    --program) PROGRAM="$2"; shift 2;;
    --ws-port) WS_PORT="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "$ENDPOINT" ]]; then
  ENDPOINT="https://127.0.0.1:${WS_PORT}"
fi
# Normalize path to file:// if bare path
DATA_URL="$PATH_IN"
if [[ -z "$DATA_URL" ]]; then
  echo "[gpu] Please set FILE=/path/to/file (or PFS_FILE) or pass --path" >&2
  exit 2
fi
if [[ "$DATA_URL" != http*://* && "$DATA_URL" != file://* ]]; then
  DATA_URL="file://$DATA_URL"
fi

# Build JSON
PAYLOAD=$(jq -cn --arg du "$DATA_URL" --argjson prog "$PROGRAM" --arg off "$OFFSET" --arg len "$LENGTH" '
  {data_url:$du, program:$prog}
  + ( ($off|length)>0 and ($len|length)>0 | if . then {offset: ($off|tonumber), length: ($len|tonumber)} else {} end)
')

# Post with -k (insecure dev TLS)
set -x
curl -fsS -k -H 'Content-Type: application/json' -d "$PAYLOAD" "$ENDPOINT/gpu/program" | jq . || curl -fsS -k -H 'Content-Type: application/json' -d "$PAYLOAD" "$ENDPOINT/gpu/program"
