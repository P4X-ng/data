#!/usr/bin/env bash
set -euo pipefail

# Swarm stats snapshot (ASCII only)
# - Shows number of VMs running, per-core CPU usage for VM PIDs, and top VMs by CPU
# - If nvidia-smi exists, prints basic GPU utilization and memory

PIDS_FILE=".vm/swarm.pids"
if [[ ! -f "$PIDS_FILE" ]]; then
  echo "no swarm pids at $PIDS_FILE"
  exit 0
fi

mapfile -t PIDS < "$PIDS_FILE" || true
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "[swarm-stats] $TS  vms=${#PIDS[@]}"

if [[ ${#PIDS[@]} -eq 0 ]]; then
  exit 0
fi

# ps snapshot for our pids
PSFMT="pid,psr,pcpu,pmem,etimes,comm"
ps -o "$PSFMT" -p "${PIDS[@]}" 2>/dev/null | awk 'NR==1 {print; next} {printf "%5s  %3s  %6s  %6s  %7s  %s\n", $1,$2,$3,$4,$5,$6}'

# Aggregate CPU by core
ps -o psr,pcpu -p "${PIDS[@]}" 2>/dev/null | awk 'NR>1 {a[$1]+=$2} END {for (k in a) printf("core %s  cpu=%.1f%%\n", k, a[k])}' | sort -n -k2 -r | head -20

# Basic GPU stats if available
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "GPU:"
  nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null || true
fi
