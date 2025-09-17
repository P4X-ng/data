#!/usr/bin/env bash
set -euo pipefail
if [[ ! -x realsrc/packetfs/network/afxdp/user/build/pfs_afxdp_rx ]] || [[ ! -x realsrc/packetfs/network/afxdp/user/build/pfs_afxdp_tx ]]; then
  echo "[ensure-afxdp] building AF_XDP components via just net-build-afxdp"
  just --justfile Justfile.network net-build-afxdp
fi
