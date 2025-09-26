#!/usr/bin/env bash
# Dispatcher for `just pod <cmd>`
set -euo pipefail
CMD="${1:-help}"
case "$CMD" in
  up) just pod-up ;;
  down) just pod-down ;;
  rebuild) just pod-rebuild ;;
  status) just pod-status ;;
  logs) just pod-logs ;;
  *) echo "pod commands: up|down|rebuild|status|logs"; exit 2 ;;
esac
