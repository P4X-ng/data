#!/bin/sh
set -eu

VENVDIR="${VIRTUAL_ENV:-/opt/venv}"
PY="$VENVDIR/bin/python"
HC="$VENVDIR/bin/hypercorn"
UV="$VENVDIR/bin/uvicorn"

export PYTHONFAULTHANDLER=1
export PYTHONUNBUFFERED=1

BIND_ADDR="${BIND:-0.0.0.0}"
PORT="${WS_PORT:-${PORT:-8811}}"
TLS="${PFS_TLS:-1}"
CERT="${PFS_TLS_CERT:-/app/certs/dev.crt}"
KEY="${PFS_TLS_KEY:-/app/certs/dev.key}"
HTTP3="${PFS_HTTP3:-${PFS_QUIC_ENABLE:-0}}"

log() { printf '[startup] %s\n' "$*" 1>&2; }

attempt_tls() {
  if [ "$TLS" != "0" ] && [ "$TLS" != "false" ] && [ "$TLS" != "FALSE" ]; then
    if [ -f "$CERT" ] && [ -f "$KEY" ]; then
      if [ "$HTTP3" = "1" ] || [ "$HTTP3" = "true" ] || [ "$HTTP3" = "TRUE" ]; then
        log "Launching hypercorn (TLS+HTTP/3) on ${BIND_ADDR}:${PORT}"
        exec "$HC" app.main:app \
          --bind "${BIND_ADDR}:${PORT}" \
          --certfile "$CERT" --keyfile "$KEY" \
          --quic-bind "${BIND_ADDR}:${PORT}" \
          --log-level info
      else
        log "Launching hypercorn (TLS) on ${BIND_ADDR}:${PORT}"
        exec "$HC" app.main:app --bind "${BIND_ADDR}:${PORT}" --certfile "$CERT" --keyfile "$KEY" --log-level info
      fi
    else
      log "TLS enabled but cert/key missing; falling back to HTTP"
    fi
  fi
}

# Try TLS first; on failure, fall back to HTTP
attempt_tls || true
log "Launching hypercorn (HTTP) on ${BIND_ADDR}:${PORT}"
exec "$HC" app.main:app --bind "${BIND_ADDR}:${PORT}" --log-level info
