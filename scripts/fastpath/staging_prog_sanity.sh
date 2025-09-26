#!/usr/bin/env bash
set -euo pipefail

# Run a short sanity test: program-bearing RX/TX using /dev/pfs_fastpath
# Environment/configurable vars with defaults
DURATION=${DURATION:-5}
BLOB_MB=${BLOB_MB:-4096}
CPU_RX=${CPU_RX:-0}
CPU_TX=${CPU_TX:-1}
RING_BYTES=${RING_BYTES:-67108864} # 64 MiB
PROG=${PROG:-xor:255}

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
rx="$root/staging/fastpath/pfs_prog_rx"
tx="$root/staging/fastpath/pfs_prog_tx"

if [[ ! -e /dev/pfs_fastpath ]]; then
  echo "/dev/pfs_fastpath not found; run scripts/kernel/reload_pfs_fastpath.sh first" >&2
  exit 1
fi

if [[ ! -x "$rx" || ! -x "$tx" ]]; then
  echo "staging tools not built; build staging/fastpath/pfs_prog_{rx,tx} first" >&2
  exit 1
fi

# TX first (sets up ring), then RX
set -m
"$tx" --duration "$DURATION" --blob-mb "$BLOB_MB" --ring-bytes "$RING_BYTES" --prog "$PROG" --cpu "$CPU_TX" > /tmp/pfs_tx_sanity.log 2>&1 &
txpid=$!
sleep 0.4
"$rx" --duration "$DURATION" --blob-mb "$BLOB_MB" --cpu "$CPU_RX" 2>&1 | tee /tmp/pfs_rx_sanity.log
wait "$txpid" || true

echo "--- TX log (tail) ---"
tail -n 50 /tmp/pfs_tx_sanity.log || true
