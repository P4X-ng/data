#!/usr/bin/env bash
set -euo pipefail
# Sweep queue count and measure MB/s, Max RSS, and CPU usage.
# Also compute CPUpwn = (pCPU MB/s) / (CPU-only MB/s) per queues value.
# Requires: scripts/benchmarks/shm_run.sh and dev/wip/native/pfs_shm_ring_bench
#
# Defaults
BLOB_MB=${BLOB_MB:-1024}
DPF=${DPF:-32}
RING_POW2=${RING_POW2:-19}
ALIGN=${ALIGN:-64}
DURATION=${DURATION:-5}
THREADS=${THREADS:-2}
PORTS=${PORTS:-1}
QUEUES_LIST=${QUEUES_LIST:-"1,2,4,8"}
MODE=${MODE:-scatter}
SEG_LEN=${SEG_LEN:-256}
PCPU_OP=${PCPU_OP:-xor}
IMM=${IMM:-255}
# Fixed-descriptor path by default
ARITH=0
VSTREAM=0
PAYLOAD_MAX=2048

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --blob-mb) BLOB_MB="$2"; shift 2;;
    --dpf) DPF="$2"; shift 2;;
    --ring-pow2) RING_POW2="$2"; shift 2;;
    --align) ALIGN="$2"; shift 2;;
    --duration) DURATION="$2"; shift 2;;
    --threads) THREADS="$2"; shift 2;;
    --ports) PORTS="$2"; shift 2;;
    --queues) QUEUES_LIST="$2"; shift 2;;
    --mode) MODE="$2"; shift 2;;
    --seg-len) SEG_LEN="$2"; shift 2;;
    --pcpu-op) PCPU_OP="$2"; shift 2;;
    --imm) IMM="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 [--blob-mb N] [--dpf N] [--ring-pow2 P] [--align A] [--duration S] [--threads N] ";
      echo "          [--ports N] [--queues \"1,2,4,8\"] [--mode scatter|contig] [--seg-len BYTES] [--pcpu-op op] [--imm N]";
      exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

BIN=dev/wip/native/pfs_shm_ring_bench
if [[ ! -x "$BIN" ]]; then
  echo "[build] $BIN"
  just build-shm-ring >/dev/null
fi

mkdir -p logs/reports
OUT=logs/reports/shm_queues_sweep.csv
TMP_OUT=$(mktemp)
TMP_ERR=$(mktemp)

# CSV header
printf "queues,mbps_cpu,mbps_pcpu,cpupwn,max_rss_kb_cpu,max_rss_kb_pcpu,cpu_pct_cpu,cpu_pct_pcpu\n" > "$OUT"

IFS=',' read -r -a Qs <<< "$QUEUES_LIST"
for q in "${Qs[@]}"; do
  echo "=== sweep queues=$q ==="
  # CPU-only run (pcpu=0)
  : > "$TMP_OUT"; : > "$TMP_ERR"
  (/usr/bin/time -v taskset -c 0-1 bash scripts/benchmarks/shm_run.sh \
    --blob-mb "$BLOB_MB" --dpf "$DPF" --ring-pow2 "$RING_POW2" --align "$ALIGN" \
    --duration "$DURATION" --threads "$THREADS" --arith "$ARITH" --vstream "$VSTREAM" \
    --ports "$PORTS" --queues "$q" --mode "$MODE" --seg-len "$SEG_LEN" --pcpu 0 \
    --pcpu-op fnv --imm 0 --payload-max 2048 >"$TMP_OUT") 2>"$TMP_ERR" || true
  MBPS_CPU=$(grep -E "\[SHM DONE\]" "$TMP_OUT" | tail -1 | sed -E 's/.* avg=([0-9.]+) MB\/s.*/\1/')
  RSS_CPU=$(grep -E "Maximum resident set size|Maximum resident set size \(kbytes\):" "$TMP_ERR" | awk '{print $NF}' | tail -1)
  CPU_PCT_CPU=$(grep -E "Percent of CPU this job got|Percent of CPU this job got:" "$TMP_ERR" | awk -F: '{print $2}' | tr -dc '0-9.' | tail -1)

  # pCPU run (pcpu=1, selected op)
  : > "$TMP_OUT"; : > "$TMP_ERR"
  (/usr/bin/time -v taskset -c 0-1 bash scripts/benchmarks/shm_run.sh \
    --blob-mb "$BLOB_MB" --dpf "$DPF" --ring-pow2 "$RING_POW2" --align "$ALIGN" \
    --duration "$DURATION" --threads "$THREADS" --arith "$ARITH" --vstream "$VSTREAM" \
    --ports "$PORTS" --queues "$q" --mode "$MODE" --seg-len "$SEG_LEN" --pcpu 1 \
    --pcpu-op "$PCPU_OP" --imm "$IMM" --payload-max 2048 >"$TMP_OUT") 2>"$TMP_ERR" || true
  MBPS_PCPU=$(grep -E "\[SHM DONE\]" "$TMP_OUT" | tail -1 | sed -E 's/.* avg=([0-9.]+) MB\/s.*/\1/')
  RSS_PCPU=$(grep -E "Maximum resident set size|Maximum resident set size \(kbytes\):" "$TMP_ERR" | awk '{print $NF}' | tail -1)
  CPU_PCT_PCPU=$(grep -E "Percent of CPU this job got|Percent of CPU this job got:" "$TMP_ERR" | awk -F: '{print $2}' | tr -dc '0-9.' | tail -1)

  CPUPWN="NA"
  if [[ -n "${MBPS_CPU:-}" && -n "${MBPS_PCPU:-}" ]]; then
    CPUPWN=$(awk -v a="$MBPS_PCPU" -v b="$MBPS_CPU" 'BEGIN{ if(b>0) printf "%.3f", a/b; else print "NA" }')
  fi

  printf "%s,%s,%s,%s,%s,%s,%s,%s\n" \
    "$q" "${MBPS_CPU:-NA}" "${MBPS_PCPU:-NA}" "${CPUPWN}" \
    "${RSS_CPU:-NA}" "${RSS_PCPU:-NA}" "${CPU_PCT_CPU:-NA}" "${CPU_PCT_PCPU:-NA}" | tee -a "$OUT"
done

rm -f "$TMP_OUT" "$TMP_ERR"
echo "\nWrote $OUT"