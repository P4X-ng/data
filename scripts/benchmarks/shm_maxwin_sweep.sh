#!/usr/bin/env bash
set -euo pipefail
# SHM ring bench "maxwin-like" sweep
# - Favorable conditions: contig mode, small seg_len, reuse prebuilt frames
# - Varies queues and consumer threads; computes CPUpwn vs CPU-only

BLOB_MB=${BLOB_MB:-1024}
RING_POW2=${RING_POW2:-19}
DPF=${DPF:-64}
ALIGN=${ALIGN:-64}
DURATION=${DURATION:-5}
PORTS=${PORTS:-1}
QUEUES_LIST=${QUEUES_LIST:-"1,3"}
PCPU_THREADS_LIST=${PCPU_THREADS_LIST:-"1,2,4,8"}
SEG_LEN=${SEG_LEN:-80}
ARITH=${ARITH:-0}
VSTREAM=${VSTREAM:-0}
REUSE_FRAMES=${REUSE_FRAMES:-1}
PCPU_OP=${PCPU_OP:-xor}
IMM=${IMM:-255}
PAYLOAD_MAX=${PAYLOAD_MAX:-2048}
OUT=${OUT:-"logs/reports/shm_maxwin_sweep.csv"}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --blob-mb) BLOB_MB="$2"; shift 2;;
    --ring-pow2) RING_POW2="$2"; shift 2;;
    --dpf) DPF="$2"; shift 2;;
    --align) ALIGN="$2"; shift 2;;
    --duration) DURATION="$2"; shift 2;;
    --ports) PORTS="$2"; shift 2;;
    --queues-list) QUEUES_LIST="$2"; shift 2;;
    --pcpu-threads-list) PCPU_THREADS_LIST="$2"; shift 2;;
    --seg-len) SEG_LEN="$2"; shift 2;;
    --arith) ARITH="$2"; shift 2;;
    --vstream) VSTREAM="$2"; shift 2;;
    --reuse-frames) REUSE_FRAMES="$2"; shift 2;;
    --pcpu-op) PCPU_OP="$2"; shift 2;;
    --imm) IMM="$2"; shift 2;;
    --payload-max) PAYLOAD_MAX="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    -h|--help)
      cat <<USAGE
Usage: $0 [--queues-list "1,3"] [--pcpu-threads-list "1,2,4,8"] [--seg-len 80] [--ring-pow2 19] [--dpf 64] [--duration 5]
       fixed: contig mode, reuse-frames=1, arith=0, vstream=0
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

printf "ring_pow2,ports,queues,pcpu_threads,dpf,seg_len,mbps_cpu,mbps_pcpu,cpupwn,frames_prod_cpu,frames_cons_cpu,frames_prod_pcpu,frames_cons_pcpu\n" > "$OUT"

IFS=',' read -r -a Qs <<< "$QUEUES_LIST"
IFS=',' read -r -a CTs <<< "$PCPU_THREADS_LIST"

get_cpu_range() {
  local threads="$1"
  local n; n=$(nproc)
  local end=$(( threads + 1 ))
  if (( end >= n )); then end=$(( n - 1 )); fi
  if (( end < 0 )); then end=0; fi
  echo "0-${end}"
}

for q in "${Qs[@]}"; do
  for ct in "${CTs[@]}"; do
    echo "=== maxwin rp2=$RING_POW2 ports=$PORTS queues=$q cthreads=$ct seg_len=$SEG_LEN ==="
    cpu_range=$(get_cpu_range "$ct")
    # CPU baseline
    : > "$TMP_OUT"; : > "$TMP_ERR"
    (/usr/bin/time -v taskset -c "$cpu_range" bash scripts/benchmarks/shm_run.sh \
      --blob-mb "$BLOB_MB" --dpf "$DPF" --ring-pow2 "$RING_POW2" --align "$ALIGN" \
      --duration "$DURATION" --threads 2 --pcpu-threads "$ct" \
      --arith "$ARITH" --vstream "$VSTREAM" \
      --ports "$PORTS" --queues "$q" --mode contig --seg-len "$SEG_LEN" --reuse-frames "$REUSE_FRAMES" \
      --pcpu 0 --pcpu-op fnv --imm 0 --payload-max "$PAYLOAD_MAX" >"$TMP_OUT") 2>"$TMP_ERR" || true
    MBPS_CPU=$(awk '/\[SHM DONE\]/{if (match($0,/avg=([0-9.]+) MB\/s/,m)) v=m[1]} END{if (v) print v; else print "NA"}' "$TMP_ERR")
    FP_CPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_prod=([0-9]+)/,m)) v=m[1]} END{if (v) print v; else print "NA"}' "$TMP_ERR")
    FC_CPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_cons=([0-9]+)/,m)) v=m[1]} END{if (v) print v; else print "NA"}' "$TMP_ERR")

    # pCPU run
    : > "$TMP_OUT"; : > "$TMP_ERR"
    (/usr/bin/time -v taskset -c "$cpu_range" bash scripts/benchmarks/shm_run.sh \
      --blob-mb "$BLOB_MB" --dpf "$DPF" --ring-pow2 "$RING_POW2" --align "$ALIGN" \
      --duration "$DURATION" --threads 2 --pcpu-threads "$ct" \
      --arith "$ARITH" --vstream "$VSTREAM" \
      --ports "$PORTS" --queues "$q" --mode contig --seg-len "$SEG_LEN" --reuse-frames "$REUSE_FRAMES" \
      --pcpu 1 --pcpu-op "$PCPU_OP" --imm "$IMM" --payload-max "$PAYLOAD_MAX" >"$TMP_OUT") 2>"$TMP_ERR" || true
    MBPS_PCPU=$(awk '/\[SHM DONE\]/{if (match($0,/avg=([0-9.]+) MB\/s/,m)) v=m[1]} END{if (v) print v; else print "NA"}' "$TMP_ERR")
    FP_PCPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_prod=([0-9]+)/,m)) v=m[1]} END{if (v) print v; else print "NA"}' "$TMP_ERR")
    FC_PCPU=$(awk '/\[SHM DONE\]/{if (match($0,/frames_cons=([0-9]+)/,m)) v=m[1]} END{if (v) print v; else print "NA"}' "$TMP_ERR")

    CPUPWN="NA"
    if [[ "$MBPS_CPU" != "NA" && "$MBPS_PCPU" != "NA" ]]; then
      CPUPWN=$(awk -v a="$MBPS_PCPU" -v b="$MBPS_CPU" 'BEGIN{ if(b>0) printf "%.3f", a/b; else print "NA" }')
    fi

    printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
      "$RING_POW2" "$PORTS" "$q" "$ct" "$DPF" "$SEG_LEN" \
      "$MBPS_CPU" "$MBPS_PCPU" "$CPUPWN" "$FP_CPU" "$FC_CPU" "$FP_PCPU" "$FC_PCPU" | tee -a "$OUT"
  done
done

echo "Wrote $OUT"