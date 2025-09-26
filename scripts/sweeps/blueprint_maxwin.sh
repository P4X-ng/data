#!/usr/bin/env bash
# Blueprint max-win sweep wrapper
# Env-driven; uses central venv at /home/punk/.venv and PYTHONPATH=src
# Writes CSV to ${OUT:-logs/bp_maxwin.csv}

set -euo pipefail

# Defaults
OUT=${OUT:-"logs/bp_maxwin.csv"}
SIZE_MB=${SIZE_MB:-600}
BLOB_MB=${BLOB_MB:-100}
BLOB_NAME=${BLOB_NAME:-pfs_vblob_test}
SEED=${SEED:-1337}
PCPU=${PCPU:-"200000,400000,800000,1300000,2600000"}
SEG=${SEG:-"80,256,4096"}
THREADS=${THREADS:-"8,16,32,48"}
BATCH=${BATCH:-"8,16,32"}
MODES=${MODES:-"contig,scatter"}
HUGEHINT=${HUGEHINT:-1}
NUMA=${NUMA:-auto}
OPS_PER_BYTE=${OPS_PER_BYTE:-1}
CPU_BASELINE=${CPU_BASELINE:-1}
CPU_DUMB=${CPU_DUMB:-0}
MEASURE_CPU=${MEASURE_CPU:-1}
MLOCK=${MLOCK:-0}
OUT_HUGEDIR=${OUT_HUGEDIR:-""}
BLOB_HUGEDIR=${BLOB_HUGEDIR:-""}

PY=${PY:-/home/punk/.venv/bin/python}
PROJ_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$PROJ_ROOT"

# Ensure native reconstructor exists (no-libnuma build fallback)
BIN=dev/wip/native/blueprint_reconstruct
if [[ ! -x "$BIN" ]]; then
  echo "[build] $BIN"
  mkdir -p dev/wip/native
  gcc -O3 -march=native -DNDEBUG -pthread -o "$BIN" src/dev/wip/native/blueprint_reconstruct.c || {
    echo "Build failed for $BIN" >&2; exit 1; }
fi

# Build args
ARGS=(
  src/dev/working/tools/bench_blueprint_maxwin.py
  --size-mb "$SIZE_MB" --blob-size-mb "$BLOB_MB" --blob-name "$BLOB_NAME" --seed "$SEED"
  --pcpu "$PCPU" --seg "$SEG" --threads "$THREADS" --batch "$BATCH" --modes "$MODES"
  --numa "$NUMA" --ops-per-byte "$OPS_PER_BYTE" --out "$OUT"
)

# Flags
(( HUGEHINT )) && ARGS+=(--hugehint)
(( CPU_BASELINE )) && ARGS+=(--cpu-baseline)
(( CPU_DUMB )) && ARGS+=(--cpu-dumb)
(( MEASURE_CPU )) && ARGS+=(--measure-cpu)
(( MLOCK )) && ARGS+=(--mlock)
[[ -n "$OUT_HUGEDIR" ]] && ARGS+=(--out-hugefs-dir "$OUT_HUGEDIR")
[[ -n "$BLOB_HUGEDIR" ]] && ARGS+=(--blob-hugefs-dir "$BLOB_HUGEDIR")

mkdir -p "$(dirname "$OUT")"
PYTHONPATH=src "$PY" "${ARGS[@]}"

echo "Wrote ${OUT}"
