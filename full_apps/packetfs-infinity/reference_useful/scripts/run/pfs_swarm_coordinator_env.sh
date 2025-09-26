#!/usr/bin/env bash
# Env-driven wrapper for pfs_swarm_coordinator.py
# Env:
#  PFS_ENDPOINT (or ENDPOINT) default http://127.0.0.1:8811
#  PFS_FILE (or FILE) path to process; converted to file:// URL
#  PFS_WINMB (or WINMB) window size MiB [default 1]
#  PFS_DEVICES (or DEVICES) GPU device ids (e.g., 0,1) [default 0]
#  PFS_CONCURRENCY (or CONCURRENCY) per-device concurrency [default 8]
#  PFS_MAX (or MAX) max windows [optional]
#  PFS_PROGRAM (or PROGRAM) JSON program [default XOR+COUNTEQ]
# Uses central venv python by default at /home/punk/.venv/bin/python
set -euo pipefail
PYTHON="${PYTHON:-/home/punk/.venv/bin/python}"
ENDPOINT="${PFS_ENDPOINT:-${ENDPOINT:-http://127.0.0.1:8811}}"
FILE_IN="${PFS_FILE:-${FILE:-}}"
WINMB="${PFS_WINMB:-${WINMB:-1}}"
DEVICES="${PFS_DEVICES:-${DEVICES:-0}}"
CONC="${PFS_CONCURRENCY:-${CONCURRENCY:-8}}"
MAX_WINDOWS="${PFS_MAX:-${MAX:-}}"
PROGRAM="${PFS_PROGRAM:-${PROGRAM:-[{\"op\":\"xor\",\"imm\":255},{\"op\":\"counteq\",\"imm\":0},{\"op\":\"crc32c\"}]}}"

if [[ -z "$FILE_IN" ]]; then
  echo "[coord] Please set PFS_FILE=/path/to/file (or FILE)" >&2
  exit 2
fi
DATA_URL="$FILE_IN"
if [[ "$DATA_URL" != http*://* && "$DATA_URL" != file://* ]]; then
  DATA_URL="file://$DATA_URL"
fi

CMD=("$PYTHON" scripts/run/pfs_swarm_coordinator.py --endpoint "$ENDPOINT" --path "$FILE_IN" --winmb "$WINMB" --devices "$DEVICES" --concurrency "$CONC" --program "$PROGRAM")
if [[ -n "${MAX_WINDOWS}" ]]; then
  CMD+=(--max-windows "$MAX_WINDOWS")
fi

printf '[coord] endpoint=%s file=%s winmb=%s devices=%s conc=%s max=%s\n' "$ENDPOINT" "$FILE_IN" "$WINMB" "$DEVICES" "$CONC" "${MAX_WINDOWS:-0}"
exec "${CMD[@]}"
