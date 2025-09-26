#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 {up|down}" >&2
}

REDIS_PORT=${REDIS_PORT:-6389}

cmd=${1:-}
case "$cmd" in
  up)
    # If the container exists with a different port mapping, recreate it
    if podman container exists pfs-redis 2>/dev/null; then
      MAP=$(podman port pfs-redis ${REDIS_PORT}/tcp 2>/dev/null || true)
      WANT="0.0.0.0:${REDIS_PORT}"
      if [ -n "$MAP" ] && [[ "$MAP" != *":${REDIS_PORT}"* ]]; then
        podman rm -f pfs-redis >/dev/null 2>&1 || true
      fi
    fi
    if ! podman container exists pfs-redis 2>/dev/null; then
      podman run -d --name pfs-redis -p ${REDIS_PORT}:${REDIS_PORT} docker.io/library/redis:7-alpine redis-server --port ${REDIS_PORT} --save "" --appendonly "no" >/dev/null
    elif [ "$(podman inspect -f {{.State.Running}} pfs-redis 2>/dev/null || true)" != "true" ]; then
      podman start pfs-redis >/dev/null
    fi
    ;;
  down)
    podman rm -f pfs-redis 2>/dev/null || true
    ;;
  *)
    usage; exit 2 ;;
 esac
