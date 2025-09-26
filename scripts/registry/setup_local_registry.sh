#!/usr/bin/env bash
set -euo pipefail
# setup_local_registry.sh — start a local Podman registry (dev-friendly)
# Default: port 5000, data under ./logs/registry
# TLS: if REGISTRY_TLS_CERT and REGISTRY_TLS_KEY are provided, they will be mounted and used.

PORT=${PORT:-5000}
DATA_DIR=${DATA_DIR:-$(pwd)/logs/registry}
CERT=${REGISTRY_TLS_CERT:-}
KEY=${REGISTRY_TLS_KEY:-}
NAME=${NAME:-pfs-registry}

mkdir -p "$DATA_DIR"

OPTS=(
  --name "$NAME"
  --pull=never
  -p "$PORT:5000"
  -v "$DATA_DIR:/var/lib/registry:Z"
)
if [[ -n "$CERT" && -n "$KEY" ]]; then
  echo "[registry] Using TLS cert/key"
  OPTS+=(
    -v "$CERT:/certs/domain.crt:Z,ro"
    -v "$KEY:/certs/domain.key:Z,ro"
    -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/domain.crt
    -e REGISTRY_HTTP_TLS_KEY=/certs/domain.key
  )
else
  echo "[registry] Starting without TLS (DEV ONLY). For TLS, set REGISTRY_TLS_CERT/KEY."
fi

# Run registry
exec podman run -d --replace "${OPTS[@]}" docker.io/library/registry:2
