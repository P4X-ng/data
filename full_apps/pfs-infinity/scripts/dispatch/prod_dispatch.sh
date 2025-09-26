#!/usr/bin/env bash
# Dispatch prod subcommands to specific Just recipes.
# Usage: scripts/dispatch/prod_dispatch.sh <cmd>
set -euo pipefail
cd "$(dirname "$0")/../.."

cmd="${1:-help}"
case "$cmd" in
  image-build|build)          just prod-image-build ;;
  run)                        just prod-run ;;
  run-huge1g)                 just prod-run-huge1g ;;
  rebuild)                    just prod-rebuild ;;
  image-up)                   just prod-image-up ;;
  image-up-sans)              just prod-image-up-sans ;;
  up)                         just prod-up ;;
  up-rebuild)                 just prod-up-rebuild ;;
  up-sans)                    just prod-up-sans ;;
  down)                       just prod-down ;;
  tls-trust)                  just prod-tls-trust ;;
  tls-untrust)                just prod-tls-untrust ;;
  tls-bootstrap)              just prod-tls-bootstrap ;;
  *)
    echo "prod commands: image-build|run|run-huge1g|rebuild|image-up|image-up-sans|up|up-rebuild|up-sans|down|tls-trust|tls-untrust|tls-bootstrap" >&2
    exit 2 ;;
esac
