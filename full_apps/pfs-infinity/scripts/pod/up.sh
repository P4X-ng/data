#!/usr/bin/env bash
# Start backend container with folder sharing and dev TLS
# Env: HOST_SHARE (default ./var/pfs-share), PORT (default 8811), IMAGE (default packetfs/pfs-infinity:latest)
set -euo pipefail
HOST_SHARE="${HOST_SHARE:-$(pwd)/var/pfs-share}"
PORT="${PORT:-8811}"
IMAGE="${IMAGE:-packetfs/pfs-infinity:latest}"
NAME="pfs-infinity"

mkdir -p "$HOST_SHARE"
# Optional logs dir inside repo
mkdir -p "$(pwd)/logs"

# Remove any old container with same name
podman rm -f "$NAME" >/dev/null 2>&1 || true

# Build podman args
ARGS=(-d --name "$NAME" --net=host \
  -v "$HOST_SHARE":/srv/pfs-share:Z \
  -v /dev/shm:/dev/shm:Z \
  -e PFS_BROWSE_ROOT=/srv/pfs-share \
  -e WS_PORT="$PORT" -e BIND=0.0.0.0 \
  -e PFS_TLS=1 -e PFS_TLS_INSECURE=1)

# X11 GUI support
if [[ "${GUI_X11:-0}" = "1" ]]; then
  if [[ -z "${DISPLAY:-}" ]]; then
    echo "[pod] GUI_X11=1 but DISPLAY is not set" >&2
  else
    ARGS+=( -v /tmp/.X11-unix:/tmp/.X11-unix:rw -e DISPLAY="$DISPLAY" )
    # Xauthority if provided; mapped to container root
    if [[ -n "${XAUTHORITY:-}" && -f "${XAUTHORITY}" ]]; then
      ARGS+=( -v "${XAUTHORITY}":/root/.Xauthority:ro -e XAUTHORITY=/root/.Xauthority )
    else
      echo "[pod] XAUTHORITY not set; you may need: xhost +local:root (insecure)" >&2
    fi
  fi
fi

# Wayland GUI support
if [[ "${GUI_WAYLAND:-0}" = "1" ]]; then
  if [[ -z "${XDG_RUNTIME_DIR:-}" || -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "[pod] GUI_WAYLAND=1 but XDG_RUNTIME_DIR or WAYLAND_DISPLAY not set" >&2
  else
    ARGS+=( -v "${XDG_RUNTIME_DIR}":"${XDG_RUNTIME_DIR}":Z \
            -e XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" \
            -e WAYLAND_DISPLAY="${WAYLAND_DISPLAY}" )
  fi
fi

# DRM render nodes for HW accel (optional)
if [[ "${GUI_DRI:-0}" = "1" ]]; then
  if [[ -d /dev/dri ]]; then
    ARGS+=( --device /dev/dri -v /dev/dri:/dev/dri )
  fi
fi

# Run container
exec podman run "${ARGS[@]}" "$IMAGE"
