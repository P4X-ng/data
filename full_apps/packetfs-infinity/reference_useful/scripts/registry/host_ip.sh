#!/usr/bin/env bash
# Compute source IP used to reach a remote host
# Usage: host_ip.sh REMOTE_IP_OR_HOST
set -euo pipefail
REMOTE="${1:-10.69.69.56}"
IP=$(ip -4 route get "$REMOTE" 2>/dev/null | awk '{for(i=1;i<=NF;i++){if($i=="src"){print $(i+1); exit}}}')
if [ -z "${IP:-}" ]; then
  IP=$(hostname -I | awk '{print $1}')
fi
echo "$IP"
