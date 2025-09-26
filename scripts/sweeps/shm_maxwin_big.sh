#!/usr/bin/env bash
# SHM max-win sweep (bigger ring/queues/duration) wrapper
# Calls existing scripts/benchmarks/shm_maxwin_sweep.sh with env/args.

set -euo pipefail
OUT=${OUT:-"logs/reports/shm_maxwin_sweep_big.csv"}
RING_POW2=${RING_POW2:-20}
QUEUES_LIST=${QUEUES_LIST:-"1,3,5"}
PCPU_THREADS_LIST=${PCPU_THREADS_LIST:-"1,2,4,8,16"}
SEG_LEN=${SEG_LEN:-80}
DURATION=${DURATION:-12}

PROJ_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$PROJ_ROOT"

mkdir -p "$(dirname "$OUT")"
bash scripts/benchmarks/shm_maxwin_sweep.sh \
  --ring-pow2 "$RING_POW2" --queues-list "$QUEUES_LIST" \
  --pcpu-threads-list "$PCPU_THREADS_LIST" --seg-len "$SEG_LEN" \
  --duration "$DURATION" --out "$OUT"

echo "Wrote ${OUT}"
