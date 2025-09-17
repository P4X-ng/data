#!/usr/bin/env bash
set -euo pipefail
# SHM ring bench wrapper (flags-based, human-friendly)
# Prints variables, estimates memory, then runs pfs_shm_ring_bench with explicit flags.
#
# Usage example:
#   bash scripts/benchmarks/shm_run.sh \
#     --blob-mb 1024 --dpf 32 --ring-pow2 20 --align 64 \
#     --duration 5 --threads 2 --arith 0 --vstream 0 \
#     --ports 1 --queues 2 --mode scatter --seg-len 256 \
#     --pcpu 0 --pcpu-op fnv --imm 0 --payload-max 2048

# Defaults (safe, fixed-descriptor path)
BLOB_MB=${BLOB_MB:-1024}
DPF=${DPF:-32}
RING_POW2=${RING_POW2:-20}
ALIGN=${ALIGN:-64}
DURATION=${DURATION:-5}
THREADS=${THREADS:-2}
ARITH=${ARITH:-0}
VSTREAM=${VSTREAM:-0}
PORTS=${PORTS:-1}
QUEUES=${QUEUES:-2}
MODE=${MODE:-scatter}
SEG_LEN=${SEG_LEN:-256}
REUSE_FRAMES=${REUSE_FRAMES:-0}
PCPU=${PCPU:-0}
PCPU_OP=${PCPU_OP:-fnv}
IMM=${IMM:-0}
PAYLOAD_MAX=${PAYLOAD_MAX:-2048}
PCPU_THREADS=${PCPU_THREADS:-1}

# Parse long flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --blob-mb) BLOB_MB="$2"; shift 2;;
    --dpf) DPF="$2"; shift 2;;
    --ring-pow2) RING_POW2="$2"; shift 2;;
    --align) ALIGN="$2"; shift 2;;
    --duration) DURATION="$2"; shift 2;;
    --threads) THREADS="$2"; shift 2;;
    --arith) ARITH="$2"; shift 2;;
    --vstream) VSTREAM="$2"; shift 2;;
    --ports) PORTS="$2"; shift 2;;
    --queues) QUEUES="$2"; shift 2;;
    --mode) MODE="$2"; shift 2;;
    --seg-len) SEG_LEN="$2"; shift 2;;
    --reuse-frames) REUSE_FRAMES="$2"; shift 2;;
    --pcpu) PCPU="$2"; shift 2;;
    --pcpu-op) PCPU_OP="$2"; shift 2;;
    --imm) IMM="$2"; shift 2;;
    --payload-max) PAYLOAD_MAX="$2"; shift 2;;
    --pcpu-threads) PCPU_THREADS="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 [--blob-mb N] [--dpf N] [--ring-pow2 P] [--align A] [--duration S] [--threads N] \";
      echo "             [--arith 0|1] [--vstream 0|1] [--ports N] [--queues N] [--mode scatter|contig] \";
      echo "             [--seg-len BYTES] [--reuse-frames 0|1] [--pcpu 0|1] [--pcpu-op op] [--imm N] [--payload-max BYTES]";
      exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

BLOB_BYTES=$(( BLOB_MB * 1024 * 1024 ))
RING_SZ=$(( 1 << RING_POW2 ))
RINGS_N=$(( PORTS * QUEUES ))
# Memory estimates (rough)
# desc size ~16 bytes (offset u64, len u32, flags u32)
DESC_BYTES_PER=16
FRAMES_TOTAL=$(( RINGS_N * RING_SZ * DPF ))
DESC_BYTES=$(( FRAMES_TOTAL * DESC_BYTES_PER ))
FRAME_EFF_BYTES=$(( RINGS_N * RING_SZ * 8 ))
SLOTS_BYTES=$(( RINGS_N * RING_SZ * 4 ))
PROD_IDX_BYTES=$(( RINGS_N * 4 ))
CONTIG_OFF_BYTES=$(( RINGS_N * 8 ))
PAYLOAD_BYTES=0
PAYLEN_BYTES=0
if [[ "$ARITH" == "1" && "$VSTREAM" == "1" ]]; then
  PAYLOAD_BYTES=$(( RINGS_N * RING_SZ * PAYLOAD_MAX ))
  # assume size_t=8
  PAYLEN_BYTES=$(( RINGS_N * RING_SZ * 8 ))
fi
TOTAL_BYTES=$(( DESC_BYTES + FRAME_EFF_BYTES + SLOTS_BYTES + PROD_IDX_BYTES + CONTIG_OFF_BYTES + PAYLOAD_BYTES + PAYLEN_BYTES ))
# Add ~10% overhead
TOTAL_BYTES=$(( TOTAL_BYTES + TOTAL_BYTES / 10 ))

# MemAvailable (kB) → bytes (best effort)
AVAIL_KB=$(awk '/MemAvailable:/ {print $2; exit}' /proc/meminfo 2>/dev/null || echo 0)
AVAIL_BYTES=$(( AVAIL_KB * 1024 ))

# Print config
cat <<CFG
[shm-run config]
 blob_mb       = $BLOB_MB
 dpf           = $DPF
 ring_pow2     = $RING_POW2 (ring_sz=$RING_SZ)
 ports         = $PORTS
 queues        = $QUEUES (rings_n=$RINGS_N)
 align         = $ALIGN
 duration_s    = $DURATION
 threads       = $THREADS (producer+consumer today)
 pcpu_threads  = $PCPU_THREADS
 arith         = $ARITH
 vstream       = $VSTREAM
 payload_max   = $PAYLOAD_MAX
 pcpu          = $PCPU
 pcpu_op       = $PCPU_OP
 imm           = $IMM
 mode          = $MODE
 seg_len       = $SEG_LEN
 reuse_frames  = $REUSE_FRAMES

[memory estimate]
 frames_total  = rings_n * ring_sz * dpf = $FRAMES_TOTAL
 desc_bytes    ≈ $(printf "%.2f" "$((DESC_BYTES))") bytes
 payload_bytes ≈ $(printf "%.2f" "$((PAYLOAD_BYTES))") bytes
 total_bytes   ≈ $TOTAL_BYTES bytes (~$(awk -v b=$TOTAL_BYTES 'BEGIN{printf "%.2f", b/1024/1024/1024}')) GiB
 mem_available ≈ $AVAIL_BYTES bytes (~$(awk -v b=$AVAIL_BYTES 'BEGIN{printf "%.2f", (b/1024/1024/1024)}')) GiB
CFG

if [[ "$ARITH" == "1" && "$VSTREAM" == "1" ]]; then
  echo "[warn] varint streaming enabled (arith=1 & vstream=1): large payload buffers per slot" >&2
fi

if (( AVAIL_BYTES > 0 && TOTAL_BYTES > AVAIL_BYTES )); then
  echo "[warn] requested buffers exceed MemAvailable; consider reducing ring_pow2/queues/dpf or turning off vstream" >&2
fi

# Run
exec dev/wip/native/pfs_shm_ring_bench \
  --blob-size "$BLOB_BYTES" \
  --dpf "$DPF" \
  --ring-pow2 "$RING_POW2" \
  --align "$ALIGN" \
  --duration "$DURATION" \
  --threads "$THREADS" \
  --pcpu-threads "$PCPU_THREADS" \
  --arith "$ARITH" \
  --vstream "$VSTREAM" \
  --payload "$PAYLOAD_MAX" \
  --ports "$PORTS" \
  --queues "$QUEUES" \
  --pcpu "$PCPU" \
  --pcpu-op "$PCPU_OP" \
  --imm "$IMM" \
  --mode "$MODE" \
  --seg-len "$SEG_LEN" \
  --reuse-frames "$REUSE_FRAMES"
