#!/usr/bin/env bash
set -euo pipefail
# CPU baseline scaling sweep (aggregated MB/s)
# Usage:
#   scripts/benchmarks/cpu_baseline_sweep.sh \
#     --threads-list 1,2,4,8,16,32,64,96,128 \
#     --size-mb 4096 --op xor8 --imm 255 --out logs/cpu_baseline_sweep.csv

THREADS_LIST="1,2,4,8,16,32,64,96,128"
SIZE_MB=4096
OP="xor8"
IMM=255
OUT="logs/cpu_baseline_sweep.csv"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --threads-list) THREADS_LIST="$2"; shift 2;;
    --size-mb) SIZE_MB="$2"; shift 2;;
    --op) OP="$2"; shift 2;;
    --imm) IMM="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    -h|--help) echo "Usage: $0 --threads-list ... --size-mb N --op xor8|add8|checksum [--imm N] --out CSV"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

mkdir -p logs
: >"$OUT"
echo "threads,agg_mb_s" >>"$OUT"

# Sanitize in case caller passed a value like 'threads=1,2,...' or 'threads_list=1,2,...'
THREADS_LIST=${THREADS_LIST#threads=}
THREADS_LIST=${THREADS_LIST#threads_list=}
SIZE_MB=${SIZE_MB#size_mb=}
OP=${OP#op=}
IMM=${IMM#imm=}

IFS=',' read -r -a TL_ARR <<<"$THREADS_LIST"
for T in "${TL_ARR[@]}"; do
  if [[ "$T" -gt "$(getconf _NPROCESSORS_ONLN)" ]]; then
    echo "skip threads=$T > nproc" >&2
    continue
  fi
  echo "=== cpu baseline threads=$T ===" >&2
  out=$(scripts/benchmarks/cpu_multi_baseline.sh --threads "$T" --size-mb "$SIZE_MB" --op "$OP" --imm "$IMM") || out=""
  # Parse: CPU_MULTI_BASELINE RESULT ... agg_MBps=X.YZ
  mbps=$(awk -F'[ =]+' '/CPU_MULTI_BASELINE/ {for (i=1;i<=NF;i++) if ($i=="agg_MBps") {print $(i+1)}}' <<<"$out" 2>/dev/null || echo 0)
  if [[ -z "${mbps:-}" ]]; then mbps=0; fi
  echo "$T,$mbps" >>"$OUT"
done
