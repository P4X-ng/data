#!/usr/bin/env bash
set -euo pipefail
ver=$(pkg-config --modversion libdpdk 2>/dev/null || pkgconf --modversion libdpdk 2>/dev/null || echo "0")
echo "libdpdk version: $ver"
if command -v dpkg >/dev/null 2>&1; then
  if dpkg --compare-versions "$ver" gt "2.5.11"; then
    echo "OK: libdpdk > 2.5.11"
  else
    echo "WARN: libdpdk ("$ver") <= 2.5.11; update recommended for dpdk stream examples"
  fi
fi
