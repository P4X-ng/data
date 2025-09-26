#!/usr/bin/env bash
# Show registry status and local catalog
# Usage: status.sh PORT
set -euo pipefail
PORT="${1:-5000}"
podman ps --filter name=pfs-registry || true
echo "[registry] catalog:"
curl -fsS "http://127.0.0.1:${PORT}/v2/_catalog" || true
