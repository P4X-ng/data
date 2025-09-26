#!/usr/bin/env bash
# Tag and push packetfs/pfs-infinity:<tag> to <host>:<port>/pfs-infinity:<tag>
# Usage: push_infinity.sh HOST PORT [TAG]
set -euo pipefail
HOST="$1"
PORT="$2"
TAG="${3:-latest}"
REF="${HOST}:${PORT}/pfs-infinity:${TAG}"
echo "[registry] pushing ${REF} (tls-verify=false)"
podman tag packetfs/pfs-infinity:"${TAG}" "${REF}"
podman push --tls-verify=false "${REF}"
