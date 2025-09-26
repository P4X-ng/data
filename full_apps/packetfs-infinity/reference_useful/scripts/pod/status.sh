#!/usr/bin/env bash
# Show podman status for pfs-infinity
set -euo pipefail
podman ps --filter name=pfs-infinity --format "{{.Names}}	{{.Image}}	{{.Status}}" || true
