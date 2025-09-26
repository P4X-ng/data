#!/usr/bin/env bash
set -euo pipefail

# Launch a swarm of microVMs pinned to host CPUs using VMKit + virtiofs.
# One or more VMs per CPU; default: total=128, vcpus_per_vm=1
# Each VM forwards host_port -> 8811 inside guest, and mounts a shared PacketFS dir.
#
# Usage:
#   scripts/vm/launch_swarm.sh \
#     --total 128 \
#     --share .vm/pfs.mnt:/share \
#     --huge /mnt/huge1G:/mnt/huge1G \
#     --base-port 9000 \
#     --img pfs-infinity.qcow2 \
#     --mem 2048 \
#     --vcpus 1 \
#     --vmkit /home/punk/Projects/HGWS/VMKit/vmkit
#
# Notes:
# - Writes PIDs to .vm/swarm.pids for teardown
# - Requires VMKit binary
# - Uses taskset to pin each VM to a single host CPU core

TOTAL=128
BATCH=0
PAUSE=0
SHARE=".vm/pfs.mnt:/share"
HUGE="/mnt/huge1G:/mnt/huge1G"
BASE_PORT=9000
IMG="pfs-infinity.qcow2"
MEM=2048
VCPUS=1
VMKIT_BIN="vmkit"
PIDS_FILE=".vm/swarm.pids"
LOG_DIR=".vm/logs"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --total) TOTAL="$2"; shift 2;;
    --share) SHARE="$2"; shift 2;;
    --huge) HUGE="$2"; shift 2;;
    --base-port) BASE_PORT="$2"; shift 2;;
    --img) IMG="$2"; shift 2;;
    --mem) MEM="$2"; shift 2;;
    --vcpus) VCPUS="$2"; shift 2;;
    --vmkit) VMKIT_BIN="$2"; shift 2;;
    --batch) BATCH="$2"; shift 2;;
    --pause) PAUSE="$2"; shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

mkdir -p .vm "$LOG_DIR"
: > "$PIDS_FILE"

CPUS=$(nproc)
if [[ "$CPUS" -lt 1 ]]; then
  echo "No CPUs detected" >&2
  exit 1
fi

echo "Launching $TOTAL VMs across $CPUS cores (taskset pinning), base port $BASE_PORT"

batch_count=0
for ((i=0; i<TOTAL; i++)); do
  cpu=$(( i % CPUS ))
  port=$(( BASE_PORT + i ))
  LOG_FILE="$LOG_DIR/vm_${i}.log"
  # Run one VM pinned to $cpu, with port forward and virtiofs shares
  IMG="$IMG" CPUS="$VCPUS" MEM="$MEM" PORT="$port:$port" SHARE="$SHARE" HUGE="$HUGE" VMKIT_BIN="$VMKIT_BIN" \
  bash -c "taskset -c $cpu scripts/run_vmkit.sh >> '$LOG_FILE' 2>&1 & echo \$!" | tee -a "$PIDS_FILE"
  # Stagger startups a tiny bit to reduce contention
  sleep 0.05
  printf '.'
  if (( (i+1) % 32 == 0 )); then echo " $((i+1))"; fi
  if (( BATCH > 0 )); then
    batch_count=$((batch_count + 1))
    if (( batch_count >= BATCH )); then
      batch_count=0
      if (( PAUSE > 0 )); then
        echo "\n[swarm] batch started: $((i+1)) VMs total; pausing $PAUSE s"
        sleep "$PAUSE"
      fi
    fi
  fi
done

echo
echo "Swarm up: $(wc -l < "$PIDS_FILE") VMs started. PID list in $PIDS_FILE"