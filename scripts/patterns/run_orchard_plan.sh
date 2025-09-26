#!/usr/bin/env bash
set -euo pipefail
# run_orchard_plan.sh — Build orchard VirtualBlob snapshot, index it, plan a target file, and pack the blueprint.
# Env/flags (env takes precedence over flags if both provided):
#   NAME (default pfs_vblob_orchard_v3)
#   SIZE_MB (default 1024)
#   SEED (default 1337)
#   PROFILE (default orchard)
#   TARGET (default /usr/bin/bash)
#   WIN (default 4096)
#   FANOUT4 (default 8) STEP4 (default 2)
#   FANOUT8 (default 8) STEP8 (default 8)
#   HINTS (optional path to hints.json)
#
# Usage examples:
#   scripts/patterns/run_orchard_plan.sh
#   TARGET=/bin/ls SIZE_MB=512 scripts/patterns/run_orchard_plan.sh
#   scripts/patterns/run_orchard_plan.sh --target /usr/bin/bash --size-mb 1024

ROOT_DIR="$(cd "$(dirname "$0")"/../.. && pwd)"
VENV_PY="/home/punk/.venv/bin/python"

# defaults
NAME="${NAME:-pfs_vblob_orchard_v3}"
SIZE_MB="${SIZE_MB:-1024}"
SEED="${SEED:-1337}"
PROFILE="${PROFILE:-orchard}"
TARGET="${TARGET:-/usr/bin/bash}"
WIN="${WIN:-4096}"
FANOUT4="${FANOUT4:-8}"; STEP4="${STEP4:-2}"
FANOUT8="${FANOUT8:-8}"; STEP8="${STEP8:-8}"
HINTS="${HINTS:-}"

# simple flag parser
while [ $# -gt 0 ]; do
  case "$1" in
    --name) shift; NAME="$1";;
    --size-mb) shift; SIZE_MB="$1";;
    --seed) shift; SEED="$1";;
    --profile) shift; PROFILE="$1";;
    --target) shift; TARGET="$1";;
    --win) shift; WIN="$1";;
    --fanout4) shift; FANOUT4="$1";;
    --step4) shift; STEP4="$1";;
    --fanout8) shift; FANOUT8="$1";;
    --step8) shift; STEP8="$1";;
    --hints) shift; HINTS="$1";;
    *) echo "[warn] unknown arg: $1";;
  esac
  shift || true
done

log(){ printf "[orchard-plan] %s\n" "$*"; }

# 1) Build snapshot
log "Build snapshot: name=$NAME size_mb=$SIZE_MB seed=$SEED profile=$PROFILE"
SNAP_LOG=$(mktemp "/tmp/blob_build_${NAME}.XXXXXX.log")
NAME="$NAME" SIZE_MB="$SIZE_MB" SEED="$SEED" PROFILE="$PROFILE" SNAPSHOT="snapshot.bin" \
  "$ROOT_DIR/scripts/patterns/blob_build.sh" | tee "$SNAP_LOG"
SNAP_PATH=$(sed -n 's/^snapshot: //p' "$SNAP_LOG" | tail -n1 || true)
if [ -z "$SNAP_PATH" ] || [ ! -f "$SNAP_PATH" ]; then
  echo "[err] snapshot path not captured/does not exist" >&2
  exit 2
fi
log "snapshot=$SNAP_PATH"

# 2) Indices
IDX4="${SNAP_PATH%.*}.kg4.pkl"; IDX8="${SNAP_PATH%.*}.kg8.pkl"
log "Index k=4 fanout=$FANOUT4 step=$STEP4 -> $IDX4"
"$VENV_PY" "$ROOT_DIR/scripts/patterns/blob_index_build.py" --snapshot "$SNAP_PATH" --k 4 --fanout "$FANOUT4" --step "$STEP4"
log "Index k=8 fanout=$FANOUT8 step=$STEP8 -> $IDX8"
"$VENV_PY" "$ROOT_DIR/scripts/patterns/blob_index_build.py" --snapshot "$SNAP_PATH" --k 8 --fanout "$FANOUT8" --step "$STEP8"

# 3) Plan target
PLAN_LOG=$(mktemp "/tmp/plan_${NAME}.XXXXXX.log")
log "Plan target=$TARGET win=$WIN"
if [ -n "$HINTS" ]; then
  "$VENV_PY" "$ROOT_DIR/scripts/patterns/planner.py" --path "$TARGET" --snapshot "$SNAP_PATH" \
    --index "$IDX4" --index2 "$IDX8" --win "$WIN" --hints "$HINTS" | tee "$PLAN_LOG"
else
  "$VENV_PY" "$ROOT_DIR/scripts/patterns/planner.py" --path "$TARGET" --snapshot "$SNAP_PATH" \
    --index "$IDX4" --index2 "$IDX8" --win "$WIN" | tee "$PLAN_LOG"
fi
BP_PATH=$(sed -n 's/^blueprint: //p' "$PLAN_LOG" | awk '{print $1}' | tail -n1 || true)
if [ -z "$BP_PATH" ] || [ ! -f "$BP_PATH" ]; then
  echo "[err] blueprint path not detected" >&2
  exit 3
fi
log "blueprint=$BP_PATH"

# 4) Pack blueprint and summarize
"$VENV_PY" "$ROOT_DIR/scripts/patterns/blueprint_pack.py" --in "$BP_PATH" || true
FILE_BYTES=$(stat -c %s "$TARGET")
RAW_SPILL=$("$VENV_PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("raw_spill_bytes",0))' "$BP_PATH")
JSON_BYTES=$(stat -c %s "$BP_PATH")
PBB_PATH="${BP_PATH%.json}.pbb"
PBB_BYTES=0; [ -f "$PBB_PATH" ] && PBB_BYTES=$(stat -c %s "$PBB_PATH")
RAW_RATIO="0"
if [ "$FILE_BYTES" -gt 0 ]; then
  RAW_RATIO=$(python -c 'import sys; fsz=int(sys.argv[1]); raw=int(sys.argv[2]); print(f"{raw/fsz:.6f}")' "$FILE_BYTES" "$RAW_SPILL")
fi
log "RESULT file_bytes=$FILE_BYTES raw_spill=$RAW_SPILL raw_ratio=$RAW_RATIO json_bytes=$JSON_BYTES pbb_bytes=$PBB_BYTES"

# final echo for machine parsing
printf "%s\n" "$BP_PATH"
