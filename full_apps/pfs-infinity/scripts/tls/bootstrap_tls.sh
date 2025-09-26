#!/usr/bin/env bash
# Bootstrap TLS: run image (optionally with SANs), export and trust the dev CA locally,
# and optionally push CA to remote hosts and install it.
# Usage: SANS="host1,10.0.0.10" SANS_CIDR="192.168.1.0/24" HOSTS="user@h1,h2" scripts/tls/bootstrap_tls.sh
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

SANS="${SANS:-}"
SANS_CIDR="${SANS_CIDR:-}"
HOSTS_RAW="${HOSTS:-}"
WAIT_SECS="${TLS_WAIT_SECS:-30}"

# 1) Run/reissue with SANs if provided
if [[ -n "$SANS" || -n "$SANS_CIDR" ]]; then
  echo "[tls] Starting container with SANs (reissue cert): SANS='$SANS' CIDR='$SANS_CIDR'"
  just prod-image-up-sans sans="$SANS" sans_cidr="$SANS_CIDR"
else
  echo "[tls] Starting container (TLS default)"
  just prod-image-up
fi

# 2) Trust dev CA locally (also writes var/tls/pfs-infinity-dev-ca.crt)
just prod-tls-trust || true

CA_PATH="var/tls/pfs-infinity-dev-ca.crt"
if [[ ! -f "$CA_PATH" ]]; then
  # Extract explicitly if missing with wait for container to generate
  mkdir -p "var/tls"
  # Wait for CA file to appear inside the container
  tries=0
  step=0.5
  max_tries=$(( WAIT_SECS*10 ))
  while ! podman exec pfs-infinity test -f /app/certs/dev_ca.crt 2>/dev/null; do
    tries=$((tries+1))
    if [[ "$tries" -ge "$max_tries" ]]; then
      echo "[tls] Timed out waiting for /app/certs/dev_ca.crt in container 'pfs-infinity' after ${WAIT_SECS}s" >&2
      podman logs --tail 100 pfs-infinity || true
      break
    fi
    sleep "$step"
  done
  # Attempt copy regardless; if missing, podman cp will error and surface to caller
  podman cp pfs-infinity:/app/certs/dev_ca.crt "$CA_PATH"
fi

# 3) Optionally push CA to remotes and install
if [[ -n "$HOSTS_RAW" ]]; then
  IFS=',' read -r -a HOSTS_ARR <<< "$HOSTS_RAW"
  for H in "${HOSTS_ARR[@]}"; do
    H_TRIM="${H// /}"
    [[ -z "$H_TRIM" ]] && continue
    echo "[tls] Installing dev CA on $H_TRIM (requires sudo on remote)"
    scp -q "$CA_PATH" "$H_TRIM:/tmp/pfs-infinity-dev-ca.crt" || { echo "[tls] scp failed for $H_TRIM" >&2; continue; }
    ssh -o BatchMode=yes "$H_TRIM" "sudo cp /tmp/pfs-infinity-dev-ca.crt /usr/local/share/ca-certificates/pfs-infinity-dev-ca.crt && sudo update-ca-certificates && rm -f /tmp/pfs-infinity-dev-ca.crt" || {
      echo "[tls] remote install failed for $H_TRIM (key/agent/permissions needed)" >&2
    }
  done
fi

echo "[tls] Bootstrap complete. If browsers still warn, restart them. For Firefox: security.enterprise_roots.enabled=true"
