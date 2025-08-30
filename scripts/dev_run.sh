#!/usr/bin/env bash
set -euo pipefail

# Create veth pair
if ! ip link show veth0 >/dev/null 2>&1; then
  sudo ip link add veth0 type veth peer name veth1 || true
fi
sudo ip link set veth0 up || true
sudo ip link set veth1 up || true

# Activate venv
source "$(dirname "$0")/../.venv/bin/activate"

# Start receiver in a new terminal if available, else background
if command -v x-terminal-emulator >/dev/null 2>&1; then
  x-terminal-emulator -e bash -lc "python tools/pfs_recv.py --iface veth1" &
else
  (python tools/pfs_recv.py --iface veth1 &)
fi
sleep 1

# Run sender
python tools/pfs_send.py --iface veth0

