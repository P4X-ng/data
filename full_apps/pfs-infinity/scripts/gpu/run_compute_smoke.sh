#!/usr/bin/env bash
# Env-driven GPU compute smoke against /gpu/compute (HTTPS -k)
# Env:
#  PFS_FILE=/path/to/file (or FILE)
#  PFS_ENDPOINT=https://host:port (or ENDPOINT) [default: https://127.0.0.1:${PFS_WS_PORT:-8811}]
#  PFS_IMM=0..255 (or IMM) [default: 0]
#  PFS_OFFSET, PFS_LENGTH optional
#  PFS_WS_PORT (or WS_PORT) default 8811
set -euo pipefail

ENDPOINT="${PFS_ENDPOINT:-${ENDPOINT:-}}"
FILE_IN="${PFS_FILE:-${FILE:-}}"
IMM="${PFS_IMM:-${IMM:-0}}"
OFFSET="${PFS_OFFSET:-${OFFSET:-}}"
LENGTH="${PFS_LENGTH:-${LENGTH:-}}"
WS_PORT="${PFS_WS_PORT:-${WS_PORT:-8811}}"

if [[ -z "$ENDPOINT" ]]; then
  ENDPOINT="https://127.0.0.1:${WS_PORT}"
fi
if [[ -z "$FILE_IN" ]]; then
  echo "[gpu] Please set PFS_FILE=/path/to/file (or FILE)" >&2
  exit 2
fi
DATA_URL="$FILE_IN"
if [[ "$DATA_URL" != http*://* && "$DATA_URL" != file://* ]]; then
  DATA_URL="file://$DATA_URL"
fi

# Build JSON
PAYLOAD=$(jq -cn --arg du "$DATA_URL" --arg op "counteq" --arg imm "$IMM" --arg off "$OFFSET" --arg len "$LENGTH" '
  {data_url:$du, op:$op, imm: ($imm|tonumber)}
  + ( ($off|length)>0 and ($len|length)>0 | if . then {offset: ($off|tonumber), length: ($len|tonumber)} else {} end)
')

set -x
curl -fsS -k -H 'Content-Type: application/json' -d "$PAYLOAD" "$ENDPOINT/gpu/compute" | jq . || curl -fsS -k -H 'Content-Type: application/json' -d "$PAYLOAD" "$ENDPOINT/gpu/compute"
