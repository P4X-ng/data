#!/usr/bin/env bash
# Stop and remove backend container
set -euo pipefail
podman rm -f pfs-infinity >/dev/null 2>&1 || true
echo "[pod] down"
