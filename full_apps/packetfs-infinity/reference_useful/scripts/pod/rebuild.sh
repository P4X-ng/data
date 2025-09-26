#!/usr/bin/env bash
# Rebuild backend image then start container
# Env: IMAGE (default packetfs/pfs-infinity:latest)
set -euo pipefail
IMAGE="${IMAGE:-packetfs/pfs-infinity:latest}"
just prod-image-build
exec just pod-up
