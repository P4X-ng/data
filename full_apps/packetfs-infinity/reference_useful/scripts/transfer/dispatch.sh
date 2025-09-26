#!/usr/bin/env bash
# Dispatcher for `just transfer <cmd>` commands
set -euo pipefail

CMD="${1:-help}"
IPROG="${2:-}"
HOST="${3:-127.0.0.1}"
PORT="${4:-}"

case "$CMD" in
  send)
    if [[ -z "$IPROG" ]]; then
      echo "usage: just transfer send iprog=PATH [host=H port=P]" >&2
      exit 2
    fi
    just transfer-send-iprog iprog="$IPROG" host="$HOST" port="$PORT"
    ;;
  send-quic)
    if [[ -z "$IPROG" ]]; then
      echo "usage: just transfer send-quic iprog=PATH [host=H port=P]" >&2
      exit 2
    fi
    just transfer-send-iprog-quic iprog="$IPROG" host="$HOST" port="$PORT"
    ;;
  install-pfcp|install)
    just transfer-install-pfcp
    ;;
  *)
    echo "transfer commands: send|send-quic|install-pfcp" >&2
    exit 2
    ;;
esac
