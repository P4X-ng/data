#!/usr/bin/env bash
set -euo pipefail
# IDrinkYourMILKSHAKE: nftables counter setup
# Creates a dedicated table/chain with counters for UDP dst port ${PORT}
# Usage: nft_setup.sh <PORT>

PORT=${1:-}
if [[ -z "$PORT" ]]; then
  echo "usage: $0 <PORT>" >&2
  exit 2
fi

if ! command -v nft >/dev/null 2>&1; then
  echo "nft not found; please install nftables" >&2
  exit 1
fi

TABLE="inet milkshake"
CHAIN="counter_${PORT}"

sudo nft -f - <<EOF
add table $TABLE 2>/dev/null
flush chain $TABLE $CHAIN 2>/dev/null || true
add chain $TABLE $CHAIN { type filter hook prerouting priority 0; policy accept; }
add rule $TABLE $CHAIN udp dport $PORT counter name cnt_${PORT}
EOF

echo "Created $TABLE/$CHAIN with counter cnt_${PORT} for UDP dport $PORT"