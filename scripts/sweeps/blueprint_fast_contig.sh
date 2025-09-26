#!/usr/bin/env bash
# Fast contiguous blueprint sweep wrapper (small, quick) 
# Env defaults match prior fast run; writes to ${OUT:-logs/bp_fast_contig.csv}

set -euo pipefail
OUT=${OUT:-"logs/bp_fast_contig.csv"}
SIZE_MB=${SIZE_MB:-400}
BLOB_MB=${BLOB_MB:-100}
BLOB_NAME=${BLOB_NAME:-pfs_vblob_test}
SEG=${SEG:-80}
PCPU=${PCPU:-200000}
THREADS=${THREADS:-16}
BATCH=${BATCH:-16}
NUMA=${NUMA:-auto}
HUGEHINT=${HUGEHINT:-1}
OPS_PER_BYTE=${OPS_PER_BYTE:-1}
CPU_BASELINE=${CPU_BASELINE:-1}

PY=${PY:-/home/punk/.venv/bin/python}
PROJ_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$PROJ_ROOT"

BIN=dev/wip/native/blueprint_reconstruct
if [[ ! -x "$BIN" ]]; then
  echo "[build] $BIN"
  mkdir -p dev/wip/native
  gcc -O3 -march=native -DNDEBUG -pthread -o "$BIN" src/dev/wip/native/blueprint_reconstruct.c || {
    echo "Build failed for $BIN" >&2; exit 1; }
fi

mkdir -p "$(dirname "$OUT")"
PYTHONPATH=src "$PY" src/dev/working/tools/bench_blueprint_sweep.py \
  --size-mb "$SIZE_MB" --blob-size-mb "$BLOB_MB" --blob-name "$BLOB_NAME" \
  --threads "$THREADS" --batch "$BATCH" --numa "$NUMA" ${HUGEHINT:+--hugehint} \
  --pcpu "$PCPU" --seg "$SEG" --ops-per-byte "$OPS_PER_BYTE" ${CPU_BASELINE:+--cpu-baseline} \
  --out "$OUT"

echo "Wrote ${OUT}"
