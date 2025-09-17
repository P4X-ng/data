#!/usr/bin/env bash
set -euo pipefail

# Usage:
#  enqueue_blob.sh --name pfs_vblob_test --size-mb 1024 --seed 1337 --win 4096 --k 50 --mods 64,128,256,512,4096 \
#                  --keep 0|1 --zlib 0|1 --lags 0|1 --lags-set "1,2,4,8" --delta 0|1 --dupes 0|1 --magic 0|1

VENV_PY="/home/punk/.venv/bin/python"
ROOT_DIR="$(cd "$(dirname "$0")"/../.. && pwd)"
ENQ="$ROOT_DIR/scripts/patterns/enqueue.py"

# Defaults
NAME="${NAME:-pfs_vblob_test}"
SIZE_MB="${SIZE_MB:-100}"
SEED="${SEED:-1337}"
WIN="${WIN:-4096}"
K="${K:-50}"
MODS="${MODS:-64,128,256,512,4096}"
KEEP="${KEEP:-0}"
ZLIB="${ZLIB:-0}"
LAGS="${LAGS:-0}"
LAGS_SET="${LAGS_SET:-}"
DELTA="${DELTA:-0}"
DUPES="${DUPES:-0}"
MAGIC="${MAGIC:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --size-mb) SIZE_MB="$2"; shift 2;;
    --seed) SEED="$2"; shift 2;;
    --win) WIN="$2"; shift 2;;
    --k) K="$2"; shift 2;;
    --mods) MODS="$2"; shift 2;;
    --keep) KEEP="$2"; shift 2;;
    --zlib) ZLIB="$2"; shift 2;;
    --lags) LAGS="$2"; shift 2;;
    --lags-set) LAGS_SET="$2"; shift 2;;
    --delta) DELTA="$2"; shift 2;;
    --dupes) DUPES="$2"; shift 2;;
    --magic) MAGIC="$2"; shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

ARGS=(blob --name "$NAME" --size-mb "$SIZE_MB" --seed "$SEED" --win "$WIN" --k "$K" --mods "$MODS")
[[ "$KEEP" == "1" ]] && ARGS+=(--keep)
[[ "$ZLIB" == "1" ]] && ARGS+=(--zlib)
[[ "$LAGS" == "1" ]] && ARGS+=(--lags)
[[ -n "$LAGS_SET" ]] && ARGS+=(--lags-set "$LAGS_SET")
[[ "$DELTA" == "1" ]] && ARGS+=(--delta)
[[ "$DUPES" == "1" ]] && ARGS+=(--dupes)
[[ "$MAGIC" == "1" ]] && ARGS+=(--magic)

exec "$VENV_PY" "$ENQ" "${ARGS[@]}"
