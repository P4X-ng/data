#!/usr/bin/env bash
# Install quadlet for Podman registry and start it (root)
# Usage: install_quadlet.sh [PORT] [UNIT_FILE]
set -euo pipefail
PORT="${1:-5000}"
UNIT_FILE="${2:-}"
UNIT_SRC_DIR="$(dirname "$0")/systemd"
UNIT_DST="/etc/containers/systemd/pfs-registry.container"

# Ensure destination dir exists
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "[quadlet] elevating to write $UNIT_DST"
  sudo mkdir -p /etc/containers/systemd
  # Copy unit
  TMP=$(mktemp)
  if [ -n "$UNIT_FILE" ] && [ -f "$UNIT_FILE" ]; then
    cp "$UNIT_FILE" "$TMP"
  else
    if [ -f "$UNIT_SRC_DIR/pfs-registry.container" ]; then
      cp "$UNIT_SRC_DIR/pfs-registry.container" "$TMP"
    else
      echo "[quadlet] no unit file provided and default not found: $UNIT_SRC_DIR/pfs-registry.container" >&2
      exit 2
    fi
  fi
  # Patch port if needed
  if [ "$PORT" != "5000" ]; then
    sed -i "s/REGISTRY_HTTP_ADDR=0.0.0.0:5000/REGISTRY_HTTP_ADDR=0.0.0.0:${PORT}/" "$TMP"
  fi
  sudo cp "$TMP" "$UNIT_DST"
  rm -f "$TMP"
  # Ensure data dir exists
  sudo mkdir -p /srv/pfs-registry/data
  sudo systemctl daemon-reload
  # Start service (enable may fail on generated units; start is sufficient)
  sudo systemctl start pfs-registry.service || \
  sudo systemctl start container-pfs-registry.service || \
  sudo systemctl start podman-pfs-registry.service
  # Try to enable for persistence, ignore failures on generated units
  sudo systemctl enable pfs-registry.service 2>/dev/null || true
  sudo systemctl enable container-pfs-registry.service 2>/dev/null || true
  sudo systemctl enable podman-pfs-registry.service 2>/dev/null || true
else
  mkdir -p /etc/containers/systemd
  TMP=$(mktemp)
  if [ -n "$UNIT_FILE" ] && [ -f "$UNIT_FILE" ]; then
    cp "$UNIT_FILE" "$TMP"
  else
    if [ -f "$UNIT_SRC_DIR/pfs-registry.container" ]; then
      cp "$UNIT_SRC_DIR/pfs-registry.container" "$TMP"
    else
      echo "[quadlet] no unit file provided and default not found: $UNIT_SRC_DIR/pfs-registry.container" >&2
      exit 2
    fi
  fi
  if [ "$PORT" != "5000" ]; then
    sed -i "s/REGISTRY_HTTP_ADDR=0.0.0.0:5000/REGISTRY_HTTP_ADDR=0.0.0.0:${PORT}/" "$TMP"
  fi
  cp "$TMP" "$UNIT_DST"
  rm -f "$TMP"
  # Ensure data dir exists
  mkdir -p /srv/pfs-registry/data
  systemctl daemon-reload
  systemctl start pfs-registry.service || \
  systemctl start container-pfs-registry.service || \
  systemctl start podman-pfs-registry.service
  systemctl enable pfs-registry.service 2>/dev/null || true
  systemctl enable container-pfs-registry.service 2>/dev/null || true
  systemctl enable podman-pfs-registry.service 2>/dev/null || true
fi

# Show resulting unit status
systemctl status pfs-registry.service 2>/dev/null || \
  systemctl status container-pfs-registry.service 2>/dev/null || \
  systemctl status podman-pfs-registry.service 2>/dev/null || true
