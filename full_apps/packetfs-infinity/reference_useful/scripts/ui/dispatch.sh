#!/usr/bin/env bash
# Dispatcher for `just ui <cmd>` commands
set -euo pipefail

CMD="${1:-help}"

case "$CMD" in
  setup) just ui-setup ;;
  test|tests) just ui-test ;;
  rebuild|build) just ui-rebuild ;;
  open-browse) just ui-open-browse ;;
  open-twin) just ui-open-twin ;;
  *) echo "ui commands: setup|test|rebuild|open-browse|open-twin"; exit 2 ;;
esac
