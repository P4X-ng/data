#!/usr/bin/env bash
# Bootstrap registry quadlet on a remote host via ssh
# Usage: bootstrap_remote_registry.sh HOST [PORT]
set -euo pipefail
HOST="$1"
PORT="${2:-5000}"
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SRC_UNIT="$ROOT_DIR/scripts/registry/systemd/pfs-registry.container"
SRC_INSTALL="$ROOT_DIR/scripts/registry/install_quadlet.sh"

# Stage files on remote
IDENT_OPTS=""
if [ -n "${SSH_IDENTITY:-}" ]; then
  IDENT_OPTS="-i ${SSH_IDENTITY}"
fi

scp -q $IDENT_OPTS "$SRC_UNIT" "$SRC_INSTALL" "${HOST}:/tmp/" || { echo "[quadlet] scp failed to $HOST" >&2; exit 1; }

# Run installer (root recommended). Accept host key automatically.
ssh $IDENT_OPTS -o StrictHostKeyChecking=accept-new "$HOST" "bash /tmp/install_quadlet.sh '$PORT' /tmp/pfs-registry.container && rm -f /tmp/install_quadlet.sh /tmp/pfs-registry.container" || {
  echo "[quadlet] remote install failed on $HOST" >&2
  exit 1
}

echo "[quadlet] installed and started registry on $HOST (port $PORT)"
