#!/usr/bin/env bash
# Tail logs for pfs-infinity container
# Usage: logs.sh [LINES]
set -euo pipefail
LINES="${1:-200}"
podman logs --tail "$LINES" pfs-infinity || true
