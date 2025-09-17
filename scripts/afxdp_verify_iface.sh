#!/usr/bin/env bash
set -euo pipefail

# Verify that a network interface exists and is up.
# Usage: scripts/afxdp_verify_iface.sh IFACE

iface=${1:-}
if [[ -z "$iface" ]]; then
  echo "Usage: $0 IFACE" >&2
  exit 2
fi

if ! ip link show dev "$iface" >/dev/null 2>&1; then
  echo "Interface '$iface' not found (ip link)." >&2
  exit 2
fi

state_file="/sys/class/net/${iface}/operstate"
if [[ -f "$state_file" ]]; then
  state=$(cat "$state_file")
  if [[ "$state" != "up" ]]; then
    echo "Interface '$iface' operstate='$state'. Try: sudo ip link set dev $iface up" >&2
    exit 3
  fi
fi

echo "iface '$iface' is present and up" >&2
exit 0

