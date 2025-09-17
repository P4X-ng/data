#!/usr/bin/env bash
set -euo pipefail
# PacketFS userspace DPDK TX (arithmetic-mode varint streaming) helper
# Usage: scripts/pfs_dpdk_tx_arith.sh --pci 0000:82:00.0 --lcore 2 --blob 2147483648 --align 64 --streams 8 --duration 10

PCI=""
LCORE=2
BLOB=2147483648
ALIGN=64
STREAMS=8
DUR=10
DPF=64

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pci) PCI=${2:-}; shift 2;;
    --lcore) LCORE=${2:-2}; shift 2;;
    --blob) BLOB=${2:-2147483648}; shift 2;;
    --align) ALIGN=${2:-64}; shift 2;;
    --streams) STREAMS=${2:-8}; shift 2;;
    --duration) DUR=${2:-10}; shift 2;;
    --dpf) DPF=${2:-64}; shift 2;;
    *) echo "[ERR] Unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "$PCI" ]]; then echo "Usage: $0 --pci 0000:82:00.0 [--lcore 2] [--blob 2147483648] [--align 64] [--streams 8] [--duration 10] [--dpf 64]" >&2; exit 2; fi

DPDK_MAIN="/home/punk/Projects/packetfs/dpdk-main"
export RTE_EAL_PMD_PATH="$DPDK_MAIN/build/drivers"
export LD_LIBRARY_PATH="$DPDK_MAIN/build/lib:${LD_LIBRARY_PATH:-}"

exec timeout "$DUR" dev/wip/native/pfs_stream_dpdk_tx \
  --ports 0 --pcis "$PCI" --tx-queues 1 \
  --eal "-l $LCORE -n 4 -a $PCI" \
  --blob-size "$BLOB" --align "$ALIGN" --arith 1 --vstream 1 --desc-per-frame "$DPF" --duration "$DUR" --streams "$STREAMS"

