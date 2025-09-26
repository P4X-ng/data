#!/usr/bin/env bash
# Stop and remove the registry container
set -euo pipefail
podman rm -f pfs-registry >/dev/null 2>&1 || true
echo "[registry] down"
