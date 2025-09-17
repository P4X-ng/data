#!/usr/bin/env bash
set -euo pipefail
# PacketFS userspace DPDK RX (arithmetic-mode + pCPU) helper
# Usage: scripts/pfs_dpdk_rx_arith.sh --pci 0000:82:00.0 --lcore 1 --blob 2147483648 --l2 14 --pcpu-op fnv --imm 0 --duration 12

PCI=""
LCORE=1
BLOB=2147483648
L2=14
OP=fnv
IMM=0
DUR=12

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pci) PCI=${2:-}; shift 2;;
    --lcore) LCORE=${2:-1}; shift 2;;
    --blob) BLOB=${2:-2147483648}; shift 2;;
    --l2) L2=${2:-14}; shift 2;;
    --pcpu-op) OP=${2:-fnv}; shift 2;;
    --imm) IMM=${2:-0}; shift 2;;
    --duration) DUR=${2:-12}; shift 2;;
    *) echo "[ERR] Unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "$PCI" ]]; then echo "Usage: $0 --pci 0000:82:00.0 [--lcore 1] [--blob 2147483648] [--l2 14] [--pcpu-op fnv] [--imm 0] [--duration 12]" >&2; exit 2; fi

# Use dpdk-main build for PMD plugins if needed
DPDK_MAIN="/home/punk/Projects/packetfs/dpdk-main"
export RTE_EAL_PMD_PATH="$DPDK_MAIN/build/drivers"
export LD_LIBRARY_PATH="$DPDK_MAIN/build/lib:${LD_LIBRARY_PATH:-}"

# Ensure CPU baseline is discoverable for pwnCPU
export PFS_CPU_BASELINE="dev/wip/native/pfs_cpu_baseline"

exec timeout "$DUR" dev/wip/native/pfs_stream_dpdk_rx \
  --ports 0 --pcis "$PCI" --rx-queues 1 \
  --eal "-l $LCORE -n 4 -a $PCI" \
  --blob-size "$BLOB" --l2-skip "$L2" --pcpu 1 --pcpu-op "$OP" --imm "$IMM"

