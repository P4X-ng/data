#!/usr/bin/env bash
set -euo pipefail
# push_osv_scanner.sh — build osv-scanner image and push to local registry
# Usage:
#   REGISTRY=127.0.0.1:5000 ./scripts/registry/push_osv_scanner.sh --osv ./osv.img
# Notes:
# - Set REGISTRY to your registry host:port (from the VM perspective if pushing from host into VM or vice versa).

REGISTRY=${REGISTRY:-127.0.0.1:5000}
OSV_IMG=""
TAG=${TAG:-osv-scanner:latest}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --osv) OSV_IMG="$2"; shift 2;;
    -h|--help)
      echo "Usage: REGISTRY=HOST:PORT $0 --osv /path/to/osv.img"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

[[ -n "$OSV_IMG" ]] || { echo "--osv required" >&2; exit 2; }
[[ -f "$OSV_IMG" ]] || { echo "OSv image not found: $OSV_IMG" >&2; exit 2; }

IMAGE_LOCAL="$TAG"
IMAGE_REGISTRY="$REGISTRY/$TAG"

# Build
podman build -t "$IMAGE_LOCAL" \
  --build-arg OSV_IMAGE="$OSV_IMG" \
  -f containers/osv-scanner/Containerfile .

# Tag and push
podman tag "$IMAGE_LOCAL" "$IMAGE_REGISTRY"
podman push "$IMAGE_REGISTRY"

echo "[ok] pushed $IMAGE_REGISTRY"
