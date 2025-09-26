#!/usr/bin/env bash
# Bootstrap backend quadlet on a remote host
# Usage: bootstrap_remote_backend.sh HOST [REGISTRY_PORT] [BACKEND_PORT]
set -euo pipefail
HOST="$1"
REG_PORT="${2:-5000}"
BE_PORT="${3:-8811}"
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SRC_UNIT="$ROOT_DIR/scripts/backend/systemd/pfs-infinity.container"
SRC_INSTALL="$ROOT_DIR/scripts/backend/install_backend_quadlet.sh"

# Stage files
scp -q "$SRC_UNIT" "$SRC_INSTALL" "${HOST}:/tmp/" || { echo "[backend] scp failed to $HOST" >&2; exit 1; }

# Install
ssh "$HOST" "bash /tmp/install_backend_quadlet.sh '$REG_PORT' '$BE_PORT' /tmp/pfs-infinity.container && rm -f /tmp/install_backend_quadlet.sh /tmp/pfs-infinity.container" || {
  echo "[backend] remote install failed on $HOST" >&2
  exit 1
}

echo "[backend] installed and started backend on $HOST (port $BE_PORT)"
