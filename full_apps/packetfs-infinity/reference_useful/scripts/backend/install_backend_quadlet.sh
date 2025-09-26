#!/usr/bin/env bash
# Install backend quadlet and start service
# Usage: install_backend_quadlet.sh [REGISTRY_PORT] [BACKEND_PORT] [UNIT_FILE]
set -euo pipefail
REG_PORT="${1:-5000}"
BE_PORT="${2:-8811}"
UNIT_FILE="${3:-}"
UNIT_SRC_DEFAULT="$(dirname "$0")/systemd/pfs-infinity.container"
UNIT_DST="/etc/containers/systemd/pfs-infinity.container"
# Use localhost registry on each host
REG_REF="127.0.0.1:${REG_PORT}/pfs-infinity:latest"

# Prepare unit
TMP=$(mktemp)
if [ -n "$UNIT_FILE" ] && [ -f "$UNIT_FILE" ]; then
  cp "$UNIT_FILE" "$TMP"
else
  if [ -f "$UNIT_SRC_DEFAULT" ]; then
    cp "$UNIT_SRC_DEFAULT" "$TMP"
  else
    echo "[backend] unit file not found: $UNIT_FILE and default $UNIT_SRC_DEFAULT" >&2
    exit 2
  fi
fi
sed -i "s|REGISTRY_REF|${REG_REF}|" "$TMP"
sed -i "s|BACKEND_PORT|${BE_PORT}|" "$TMP"

# Write unit and start
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "[backend] elevating to install unit"
  sudo mkdir -p /etc/containers/systemd
  sudo cp "$TMP" "$UNIT_DST"
  sudo systemctl daemon-reload
  sudo systemctl start pfs-infinity.service || sudo systemctl start container-pfs-infinity.service || true
  sudo systemctl enable pfs-infinity.service 2>/dev/null || true
else
  mkdir -p /etc/containers/systemd
  cp "$TMP" "$UNIT_DST"
  systemctl daemon-reload
  systemctl start pfs-infinity.service || systemctl start container-pfs-infinity.service || true
  systemctl enable pfs-infinity.service 2>/dev/null || true
fi
rm -f "$TMP"

# Show status
systemctl status --no-pager pfs-infinity.service 2>/dev/null || systemctl status --no-pager container-pfs-infinity.service 2>/dev/null || true
