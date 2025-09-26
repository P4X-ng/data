#!/usr/bin/env bash
set -euo pipefail

# pNIC aggregator scaling sweep
# Usage example:
#   scripts/benchmarks/pnic_agg_sweep.sh \
#     --nproducers 16 --threads-list 1,2,4,8,16,32,64,96,128 \
#     --duration 4 --ring-pow2 16 --dpf 64 --align 64 --blob-mb 1024 \
#     --op xor --imm 255 --out logs/pnic_agg_sweep.csv

NPROD=4
THREADS_LIST="1,2,4,8,16,32,64,96,128"
DURATION=5
RING_POW2=16
DPF=64
ALIGN=64
BLOB_MB=1024
OP="xor"
IMM=255
OUT="logs/pnic_agg_sweep.csv"
PIN_FIRST=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --nproducers) NPROD="$2"; shift 2;;
    --threads-list) THREADS_LIST="$2"; shift 2;;
    --duration) DURATION="$2"; shift 2;;
    --ring-pow2) RING_POW2="$2"; shift 2;;
    --dpf) DPF="$2"; shift 2;;
    --align) ALIGN="$2"; shift 2;;
    --blob-mb) BLOB_MB="$2"; shift 2;;
    --op) OP="$2"; shift 2;;
    --imm) IMM="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    --pin-first) PIN_FIRST="$2"; shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

mkdir -p logs
: >"$OUT"
echo "threads,bytes_mb,secs,avg_mb_s" >>"$OUT"

# Sanitize in case caller passed 'threads=...' into THREADS_LIST via Just
THREADS_LIST=${THREADS_LIST#threads=}
THREADS_LIST=${THREADS_LIST#threads_list=}

run_one() {
  local T="$1"
  local paths=""
  # clean old endpoints for this thread count
  rm -f /dev/shm/pnic_sweep_${T}_*
  for ((i=1;i<=NPROD;i++)); do
    local idx;
    idx=$(printf "%03d" "$i")
    local p="/dev/shm/pnic_sweep_${T}_${idx}"
    staging/pnic/pnic_tx_shm --path "$p" --ring-pow2 "$RING_POW2" --dpf "$DPF" --align "$ALIGN" --duration "$DURATION" --blob-mb "$BLOB_MB" >/dev/null 2>&1 &
    if [[ -z "$paths" ]]; then paths="$p"; else paths="$paths,$p"; fi
  done
  sleep 0.2
  local tmp
  tmp=$(mktemp)
  # aggregator pinned starting at PIN_FIRST
  staging/pnic/pnic_agg --endpoints "$paths" --threads "$T" --pin-first "$PIN_FIRST" --duration "$DURATION" --blob-mb "$BLOB_MB" --op "$OP" --imm "$IMM" | tee "$tmp"
  # parse DONE line
  local MB SECS AVG
  MB=""; SECS=""; AVG=""
  # shellcheck disable=SC2016
  read -r MB SECS AVG < <(awk '/\[pnic_agg DONE\]/{mb="";s="";a=""; for(i=1;i<=NF;i++){ if($i ~ /^bytes=/){x=$i; sub(/^bytes=/,"",x); sub(/MB$/,"",x); mb=x} if($i ~ /^secs=/){y=$i; sub(/^secs=/,"",y); s=y} if($i ~ /^avg=/){z=$i; sub(/^avg=/,"",z); sub(/MB\/s$/,"",z); a=z} } } END{ if(mb!=""){ printf "%s %s %s", mb, s, a }}' "$tmp") || true
  if [[ -z "${MB:-}" ]] || [[ -z "${SECS:-}" ]] || [[ -z "${AVG:-}" ]]; then
    echo "warn: could not parse aggregator output for threads=$T" >&2
  else
    echo "$T,$MB,$SECS,$AVG" >>"$OUT"
  fi
  rm -f "$tmp"
  # cleanup endpoints
  rm -f /dev/shm/pnic_sweep_${T}_*
}

IFS=',' read -r -a TL_ARR <<<"$THREADS_LIST"
for T in "${TL_ARR[@]}"; do
  # bound by system CPUs
  if [[ "$T" -gt "$(getconf _NPROCESSORS_ONLN)" ]]; then
    echo "skip threads=$T > nproc" >&2
    continue
  fi
  echo "=== threads=$T ===" >&2
  run_one "$T"
done
