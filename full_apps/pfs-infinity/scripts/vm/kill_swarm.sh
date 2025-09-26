#!/usr/bin/env bash
set -euo pipefail

PIDS_FILE=".vm/swarm.pids"
if [[ ! -f "$PIDS_FILE" ]]; then
  echo "No swarm PIDs file at $PIDS_FILE"
  exit 0
fi

# Try graceful, then force
mapfile -t PIDS < "$PIDS_FILE" || true
if [[ ${#PIDS[@]} -eq 0 ]]; then
  echo "No PIDs to kill"
  exit 0
fi

echo "Stopping ${#PIDS[@]} VMs"
for pid in "${PIDS[@]}"; do
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
  fi
done
sleep 2
for pid in "${PIDS[@]}"; do
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" || true
  fi
done

: > "$PIDS_FILE"
echo "Swarm down"