#!/usr/bin/env bash
set -euo pipefail
# cpu_multi_baseline.sh — spawn N pinned pfs_cpu_baseline workers and aggregate throughput
#
# Usage:
#   scripts/benchmarks/cpu_multi_baseline.sh --threads N --size-mb TOTAL --op xor8|add8|checksum [--imm N]
#
# Notes:
# - TOTAL is divided evenly across workers (rounded down to bytes).
# - Uses taskset to pin each worker to a distinct CPU core modulo nproc.
# - Expects dev/wip/native/pfs_cpu_baseline to be built (use: just build-cpu-baseline).

THREADS=8
SIZE_MB=2048
OP="xor8"
IMM=255

while [[ $# -gt 0 ]]; do
  case "$1" in
    --threads) THREADS="$2"; shift 2 ;;
    --size-mb) SIZE_MB="$2"; shift 2 ;;
    --op) OP="$2"; shift 2 ;;
    --imm) IMM="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 --threads N --size-mb TOTAL --op xor8|add8|checksum [--imm N]"; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

BIN=dev/wip/native/pfs_cpu_baseline
if [[ ! -x "$BIN" ]]; then
  echo "Missing $BIN. Build it first: just build-cpu-baseline" >&2
  exit 1
fi

TOTAL_BYTES=$(( SIZE_MB * 1024 * 1024 ))
PER_BYTES=$(( TOTAL_BYTES / THREADS ))
if (( PER_BYTES <= 0 )); then echo "Per-thread size is zero; increase --size-mb or reduce --threads" >&2; exit 2; fi

CPUS=$(nproc)
PIDS=()
TMPD=$(mktemp -d)
trap 'rm -rf "$TMPD"' EXIT

for ((i=0;i<THREADS;i++)); do
  core=$(( i % CPUS ))
  out="$TMPD/worker_$i.txt"
  ( taskset -c "$core" "$BIN" --size-bytes "$PER_BYTES" --op "$OP" --imm "$IMM" >"$out" 2>&1 ) &
  PIDS+=("$!")
  echo "[cpu-multi] started worker $i core=$core size=$PER_BYTES"
done

FAIL=0
for pid in "${PIDS[@]}"; do
  wait "$pid" || FAIL=1
done

AGG=0.0
for f in "$TMPD"/worker_*.txt; do
  if grep -q "CPU_BASELINE" "$f"; then
    mbps=$(awk -F'[ =]+' '/CPU_BASELINE/ {for (i=1;i<=NF;i++) if ($i=="MBps") {print $(i+1)}}' "$f" 2>/dev/null || echo 0)
    # Sum as floating point via awk
    AGG=$(awk -v a="$AGG" -v b="$mbps" 'BEGIN{printf "%.6f", a+b}')
  fi
 done

printf "CPU_MULTI_BASELINE RESULT threads=%d total_bytes=%d per_bytes=%d op=%s imm=%d agg_MBps=%.6f\n" \
  "$THREADS" "$TOTAL_BYTES" "$PER_BYTES" "$OP" "$IMM" "$AGG"
