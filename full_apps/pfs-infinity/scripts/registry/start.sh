#!/usr/bin/env bash
# Start an insecure local Podman registry on given port, with data dir mounted
# Usage: start.sh PORT DATA_DIR
set -euo pipefail
PORT="${1:-5000}"
DATA_DIR="${2:-/srv/pfs-registry/data}"

echo "[registry] starting on 0.0.0.0:${PORT} (insecure, dev only)"
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  sudo mkdir -p "${DATA_DIR}"
else
  mkdir -p "${DATA_DIR}"
fi

podman rm -f pfs-registry >/dev/null 2>&1 || true
exec podman run -d --name pfs-registry --net=host \
  -v "${DATA_DIR}":"/var/lib/registry":Z \
  -e REGISTRY_HTTP_ADDR="0.0.0.0:${PORT}" \
  registry:2
