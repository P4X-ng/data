#!/usr/bin/env bash
# Show registry logs
# Usage: logs.sh [LINES]
set -euo pipefail
LINES="${1:-200}"
podman logs --tail "${LINES}" pfs-registry || true
