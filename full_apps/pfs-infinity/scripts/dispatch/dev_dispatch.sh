#!/usr/bin/env bash
# Dispatcher for `just dev <cmd>` commands
set -euo pipefail

CMD="${1:-help}"

case "$CMD" in
  up) just dev-up ;;
  install) just dev-install ;;
  test|tests) just dev-test ;;
  clean) just dev-clean ;;
  spider-assets) just dev-spider-assets ;;
  vpcpu-init) just dev-vpcpu-init ;;
  vpcpu-add) just dev-vpcpu-add ;;
  vpcpu-list) just dev-vpcpu-list ;;
  vpcpu-compute) just dev-vpcpu-compute ;;
  vcpu-service-up) just dev-vcpu-service-up ;;
  vcpu-service-down) just dev-vcpu-service-down ;;
  vcpu-smoke) just dev-vcpu-smoke ;;
  data-blob) just dev-data-blob ;;
  bench-local) just dev-bench-local ;;
  bench-edge) just dev-bench-edge ;;
  gh-build-manifests) just dev-gh-build-manifests ;;
  gh-fetch-index) just dev-gh-fetch-index ;;
  gh-eval) just dev-gh-eval ;;
  gh-export-repo) just dev-gh-export-repo ;;
  pktop) just dev-pktop ;;
  gpu-smoke) just dev-gpu-smoke ;;
  gpu-program-smoke) just dev-gpu-program-smoke ;;
  gpu-coordinator) just dev-gpu-coordinator ;;
  milkshake) just dev-milkshake ;;
  milkshake-aws-setup) just dev-milkshake-aws-setup ;;
  milkshake-aws-query) just dev-milkshake-aws-query ;;
  milkshake-aws-word) just dev-milkshake-aws-word ;;
  *) echo "dev commands: up|install|test|clean|spider-assets|vpcpu-init|vpcpu-add|vpcpu-list|vpcpu-compute|vcpu-service-up|vcpu-service-down|vcpu-smoke|data-blob|bench-local|bench-edge|gh-build-manifests|gh-fetch-index|gh-eval|gh-export-repo|pktop|gpu-smoke|gpu-program-smoke|gpu-coordinator|milkshake|milkshake-aws-setup|milkshake-aws-query|milkshake-aws-word"; exit 2 ;;
esac
