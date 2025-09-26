#!/usr/bin/env bash
# Install the dev CA from the running container into the host trust store (Ubuntu/Debian)
# Usage: scripts/tls/install_dev_ca.sh [container_name]
set -euo pipefail

NAME="${1:-pfs-infinity}"
HOST_CA_DIR="${HOST_CA_DIR:-/usr/local/share/ca-certificates}"
TMP_DIR="${TMP_DIR:-./var/tls}"
WAIT_SECS="${TLS_WAIT_SECS:-30}"
CA_IN_CONTAINER="/app/certs/dev_ca.crt"
CA_OUT_HOST="${TMP_DIR}/pfs-infinity-dev-ca.crt"

mkdir -p "$TMP_DIR"

# Ensure container is running
if ! podman inspect -f '{{.State.Running}}' "$NAME" >/dev/null 2>&1; then
  echo "[tls] Container '$NAME' not found or not running. Start it first (e.g., just prod image-up)." >&2
  exit 125
fi

# Wait for the container to generate the dev CA (start-backend does this on boot)
tries=0
step=0.5
max_tries=$(( (WAIT_SECS*10) ))
while ! podman exec "$NAME" test -f "$CA_IN_CONTAINER" 2>/dev/null; do
  tries=$((tries+1))
  if [ "$tries" -ge "$max_tries" ]; then
    echo "[tls] Timed out waiting for $CA_IN_CONTAINER to appear in container '$NAME' after ${WAIT_SECS}s" >&2
    echo "[tls] Recent logs:" >&2
    podman logs --tail 100 "$NAME" || true
    exit 125
  fi
  sleep "$step"
  # Kick hypercorn/boot once more if process crashed (no-op if fine)
  :
done

# Extract the dev CA certificate from container
podman cp "${NAME}:${CA_IN_CONTAINER}" "$CA_OUT_HOST"

# Install into system trust (requires sudo)
if [ ! -w "$HOST_CA_DIR" ]; then
  echo "[tls] Elevating to install CA into $HOST_CA_DIR" >&2
  sudo cp "$CA_OUT_HOST" "$HOST_CA_DIR/pfs-infinity-dev-ca.crt"
  sudo update-ca-certificates
else
  cp "$CA_OUT_HOST" "$HOST_CA_DIR/pfs-infinity-dev-ca.crt"
  update-ca-certificates
fi

echo "[tls] Installed dev CA to system trust. Restart browsers to pick it up."
echo "[tls] For Firefox, enable enterprise roots: about:config -> security.enterprise_roots.enabled=true"
