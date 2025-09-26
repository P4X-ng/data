#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
PacketFS Infinity
-----------------
Core commands:
  just up-front            # Backend (HTTP) + Caddy TLS/H2/H3 front (recommended)
  just down                # Stop backend container
  just logs                # Tail backend logs
  just status              # Show backend status
  just build               # Build backend image
  just dev-rebuild         # Full rebuild (no cache)
  just clean               # Clean artifacts

Data:
  just xfer-upload file=... host=127.0.0.1 port=8811  # Upload a file
  just list-objects host=127.0.0.1 port=8811         # List uploaded objects

Env overrides (common):
  PORT=8811                # Backend port
  PFS_BLOB_SIZE_BYTES=134217728  # VirtualBlob size (bytes)
  PFS_SHM_SIZE=512m        # Container --shm-size (>= blob size)
  PFS_QUIC_ENABLE=0|1      # QUIC server toggle (0 recommended with Caddy)
  PFS_ENABLE_TERMINAL=1    # Enable experimental terminal WebSocket (default disabled)
  PFS_SIMPLE_XFER=1        # Root '/' serves simple upload/download page (xfer-simple.html)

Usage:
  PORT=8811 PFS_BLOB_SIZE_BYTES=134217728 PFS_SHM_SIZE=512m just up-front
  Open https://localhost:8811/static/transfer-v2.html
EOF
