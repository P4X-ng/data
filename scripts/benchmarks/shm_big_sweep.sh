#!/usr/bin/env bash
set -euo pipefail
# SHM ring bench big sweep
# - Sweeps across selected parameters and writes a CSV report.
# - Runs CPU-only (pcpu=0) and pCPU-enabled (pcpu=1) for each combo.
#
# Defaults (tunable via flags)
BLOB_MB=${BLOB_MB:-1024}
DPF=${DPF:-32}
RING_POW2_LIST=${RING_POW2_LIST:-"18,19"}
PORTS_LIST=${PORTS_LIST:-"1"}
QUEUES_LIST=${QUEUES_LIST:-"1,3"}
PCPU_THREADS_LIST=${PCPU_THREADS_LIST:-"1,4"}
SEG_LEN_LIST=${SEG_LEN_LIST:-"80,256,4096"}
ALIGN=${ALIGN:-64}
DURATION=${DURATION:-5}
ARITH=${ARITH:-0}
VSTREAM=${VSTREAM:-0}
PCPU_OP=${PCPU_OP:-xor}
IMM=${IMM:-255}
PAYLOAD_MAX=${PAYLOAD_MAX:-2048}
MODE=${MODE:-scatter}

OUT=${OUT:-"logs/reports/shm_big_sweep.csv"}

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --blob-mb) BLOB_MB="$2"; shift 2;;
    --dpf) DPF="$2"; shift 2;;
    --ring-pow2-list) RING_POW2_LIST="$2"; shift 2;;
    --ports-list) PORTS_LIST="$2"; shift 2;;
    --queues-list) QUEUES_LIST="$2"; shift 2;;
    --pcpu-threads-list) PCPU_THREADS_LIST="$2"; shift 2;;
    --seg-len-list) SEG_LEN_LIST="$2"; shift 2;;
    --align) ALIGN="$2"; shift 2;;
    --duration) DURATION="$2"; shift 2;;
    --arith) ARITH="$2"; shift 2;;
    --vstream) VSTREAM="$2"; shift 2;;
    --pcpu-op) PCPU_OP="$2"; shift 2;;
    --imm) IMM="$2"; shift 2;;
    --payload-max) PAYLOAD_MAX="$2"; shift 2;;
    --mode) MODE="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    -h|--help)
      cat <<USAGE
Usage: $0 [--blob-mb N] [--dpf N] \
          [--ring-pow2-list "18,19"] [--ports-list "1"] [--queues-list "1,3"] \
          [--pcpu-threads-list "1,4"] [--seg-len-list "80,256,4096"] \
          [--align 64] [--duration 5] [--arith 0] [--vstream 0] \
          [--pcpu-op xor] [--imm 255] [--payload-max 2048] [--mode scatter] \
          [--out logs/reports/shm_big_sweep.csv]
USAGE
      exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

BIN=dev/wip/native/pfs_shm_ring_bench
if [[ ! -x "$BIN" ]]; then
  echo "[build] $BIN"
  just build-shm-ring >/dev/null
fi

mkdir -p "$(dirname "$OUT")"
TMP_OUT=$(mktemp)
TMP_ERR=$(mktemp)

# CSV header
printf "ring_pow2,ports,queues,pcpu_threads,dpf,seg_len,arith,vstream,pcpu_op,imm,mbps_cpu,mbps_pcpu,cpupwn,max_rss_kb_cpu,max_rss_kb_pcpu,cpu_pct_cpu,cpu_pct_pcpu,frames_prod_cpu,frames_cons_cpu,frames_prod_pcpu,frames_cons_pcpu\n" > "$OUT"

IFS=',' read -r -a RP2S <<< "$RING_POW2_LIST"
IFS=',' read -r -a PS <<< "$PORTS_LIST"
IFS=',' read -r -a QS <<< "$QUEUES_LIST"
IFS=',' read -r -a CTS <<< "$PCPU_THREADS_LIST"
IFS=',' read -r -a SLS <<< "$SEG_LEN_LIST"

get_cpu_range() {
  local threads="$1"
  local n; n=$(nproc)
  local end=$(( threads + 1 ))
  if (( end >= n )); then end=$(( n - 1 )); fi
  if (( end < 0 )); then end=0; fi
  echo "0-${end}"
}

for rp2 in "${RP2S[@]}"; do
  for p in "${PS[@]}"; do
    for q in "${QS[@]}"; do
      for ct in "${CTS[@]}"; do
        for sl in "${SLS[@]}"; do
          echo "=== rp2=$rp2 ports=$p queues=$q cthreads=$ct seg_len=$sl ==="
          cpu_range=$(get_cpu_range "$ct")
          # CPU-only run
          : > "$TMP_OUT"; : > "$TMP_ERR"
          (/usr/bin/time -v taskset -c "$cpu_range" bash scripts/benchmarks/shm_run.sh \
            --blob-mb "$BLOB_MB" --dpf "$DPF" --ring-pow2 "$rp2" --align "$ALIGN" \
            --duration "$DURATION" --threads 2 --pcpu-threads "$ct" \
            --arith "$ARITH" --vstream "$VSTREAM" \
            --ports "$p" --queues "$q" --mode "$MODE" --seg-len "$sl" \
            --pcpu 0 --pcpu-op fnv --imm 0 --payload-max "$PAYLOAD_MAX" >"$TMP_OUT") 2>"$TMP_ERR" || true
MBPS_CPU=$(awk '/\[SHM DONE\]/{if (match($0,/avg=([0-9.]+) MB\/s/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")
RSS_CPU=$(awk '/Maximum resident set size/{v=$NF} END{if (v) print v}' "$TMP_ERR")
CPU_PCT_CPU=$(awk -F: '/Percent of CPU this job got/{gsub(/[^0-9.]/, "", $2); v=$2} END{if (v) print v}' "$TMP_ERR")
FP_CPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_prod=([0-9]+)/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")
FC_CPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_cons=([0-9]+)/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")

          # pCPU run
          : > "$TMP_OUT"; : > "$TMP_ERR"
          (/usr/bin/time -v taskset -c "$cpu_range" bash scripts/benchmarks/shm_run.sh \
            --blob-mb "$BLOB_MB" --dpf "$DPF" --ring-pow2 "$rp2" --align "$ALIGN" \
            --duration "$DURATION" --threads 2 --pcpu-threads "$ct" \
            --arith "$ARITH" --vstream "$VSTREAM" \
            --ports "$p" --queues "$q" --mode "$MODE" --seg-len "$sl" \
            --pcpu 1 --pcpu-op "$PCPU_OP" --imm "$IMM" --payload-max "$PAYLOAD_MAX" >"$TMP_OUT") 2>"$TMP_ERR" || true
MBPS_PCPU=$(awk '/\[SHM DONE\]/{if (match($0,/avg=([0-9.]+) MB\/s/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")
RSS_PCPU=$(awk '/Maximum resident set size/{v=$NF} END{if (v) print v}' "$TMP_ERR")
CPU_PCT_PCPU=$(awk -F: '/Percent of CPU this job got/{gsub(/[^0-9.]/, "", $2); v=$2} END{if (v) print v}' "$TMP_ERR")
FP_PCPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_prod=([0-9]+)/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")
FC_PCPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_cons=([0-9]+)/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")

          CPUPWN="NA"
          if [[ -n "${MBPS_CPU:-}" && -n "${MBPS_PCPU:-}" ]]; then
            CPUPWN=$(awk -v a="$MBPS_PCPU" -v b="$MBPS_CPU" 'BEGIN{ if(b>0) printf "%.3f", a/b; else print "NA" }')
          fi

          printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
            "$rp2" "$p" "$q" "$ct" "$DPF" "$sl" "$ARITH" "$VSTREAM" "$PCPU_OP" "$IMM" \
            "${MBPS_CPU:-NA}" "${MBPS_PCPU:-NA}" "${CPUPWN}" \
            "${RSS_CPU:-NA}" "${RSS_PCPU:-NA}" "${CPU_PCT_CPU:-NA}" "${CPU_PCT_PCPU:-NA}" \
            "${FP_CPU:-NA}" "${FC_CPU:-NA}" "${FP_PCPU:-NA}" "${FC_PCPU:-NA}" | tee -a "$OUT"
        done
      done
    done
  done
  # Optional ports scaling skim for this ring_pow2: ports=2, queues=2, cthreads=2, seg_len=256
  p=2; q=2; ct=2; sl=256
  echo "=== skim ports=2 rp2=$rp2 queues=$q cthreads=$ct seg_len=$sl ==="
  cpu_range=$(get_cpu_range "$ct")
  : > "$TMP_OUT"; : > "$TMP_ERR"
  (/usr/bin/time -v taskset -c "$cpu_range" bash scripts/benchmarks/shm_run.sh \
    --blob-mb "$BLOB_MB" --dpf "$DPF" --ring-pow2 "$rp2" --align "$ALIGN" \
    --duration "$DURATION" --threads 2 --pcpu-threads "$ct" \
    --arith "$ARITH" --vstream "$VSTREAM" \
    --ports "$p" --queues "$q" --mode "$MODE" --seg-len "$sl" \
    --pcpu 0 --pcpu-op fnv --imm 0 --payload-max "$PAYLOAD_MAX" >"$TMP_OUT") 2>"$TMP_ERR" || true
MBPS_CPU=$(awk '/\[SHM DONE\]/{if (match($0,/avg=([0-9.]+) MB\/s/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")
RSS_CPU=$(awk '/Maximum resident set size/{v=$NF} END{if (v) print v}' "$TMP_ERR")
CPU_PCT_CPU=$(awk -F: '/Percent of CPU this job got/{gsub(/[^0-9.]/, "", $2); v=$2} END{if (v) print v}' "$TMP_ERR")
FP_CPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_prod=([0-9]+)/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")
FC_CPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_cons=([0-9]+)/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")

  : > "$TMP_OUT"; : > "$TMP_ERR"
  (/usr/bin/time -v taskset -c "$cpu_range" bash scripts/benchmarks/shm_run.sh \
    --blob-mb "$BLOB_MB" --dpf "$DPF" --ring-pow2 "$rp2" --align "$ALIGN" \
    --duration "$DURATION" --threads 2 --pcpu-threads "$ct" \
    --arith "$ARITH" --vstream "$VSTREAM" \
    --ports "$p" --queues "$q" --mode "$MODE" --seg-len "$sl" \
    --pcpu 1 --pcpu-op "$PCPU_OP" --imm "$IMM" --payload-max "$PAYLOAD_MAX" >"$TMP_OUT") 2>"$TMP_ERR" || true
MBPS_PCPU=$(awk '/\[SHM DONE\]/{if (match($0,/avg=([0-9.]+) MB\/s/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")
RSS_PCPU=$(awk '/Maximum resident set size/{v=$NF} END{if (v) print v}' "$TMP_ERR")
CPU_PCT_PCPU=$(awk -F: '/Percent of CPU this job got/{gsub(/[^0-9.]/, "", $2); v=$2} END{if (v) print v}' "$TMP_ERR")
FP_PCPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_prod=([0-9]+)/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")
FC_PCPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_cons=([0-9]+)/,m)) v=m[1]} END{if (v) print v}' "$TMP_OUT")
  CPUPWN="NA"
  if [[ -n "${MBPS_CPU:-}" && -n "${MBPS_PCPU:-}" ]]; then
    CPUPWN=$(awk -v a="$MBPS_PCPU" -v b="$MBPS_CPU" 'BEGIN{ if(b>0) printf "%.3f", a/b; else print "NA" }')
  fi
  printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
    "$rp2" "$p" "$q" "$ct" "$DPF" "$sl" "$ARITH" "$VSTREAM" "$PCPU_OP" "$IMM" \
    "${MBPS_CPU:-NA}" "${MBPS_PCPU:-NA}" "${CPUPWN}" \
    "${RSS_CPU:-NA}" "${RSS_PCPU:-NA}" "${CPU_PCT_CPU:-NA}" "${CPU_PCT_PCPU:-NA}" \
    "${FP_CPU:-NA}" "${FC_CPU:-NA}" "${FP_PCPU:-NA}" "${FC_PCPU:-NA}" | tee -a "$OUT"

done

rm -f "$TMP_OUT" "$TMP_ERR"
echo "Wrote $OUT"