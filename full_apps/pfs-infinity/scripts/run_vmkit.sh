#!/usr/bin/env bash
set -euo pipefail

# Simple VMKit runner with virtiofs shares for host integration
# Usage: scripts/run_vmkit.sh --share /srv/pfs-share:/share --huge /mnt/huge1G:/mnt/huge1G --port 8811:8811
# Environment overrides:
#   VMKIT_BIN=/path/to/vmkit (default: auto-detect; then 'vmkit' in PATH)

IMG=${IMG:-pfs-infinity.qcow2}
CPUS=${CPUS:-4}
MEM=${MEM:-8192}
PORT=${PORT:-8811:8811}
SHARE=${SHARE:-/srv/pfs-share:/share}
HUGE=${HUGE:-/mnt/huge1G:/mnt/huge1G}

# Locate VMKit: prefer explicit VMKIT_BIN, then PATH, then local repo VMKit
VMKIT_BIN=${VMKIT_BIN:-vmkit}
if ! command -v "$VMKIT_BIN" >/dev/null 2>&1; then
  ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
  for cand in \
    "$ROOT_DIR/VMKit/vmkit" \
    "$ROOT_DIR/VMKit/bin/vmkit" \
    "$ROOT_DIR/VMKit/VMKit"; do
    if [ -x "$cand" ]; then
      VMKIT_BIN="$cand"
      break
    fi
  done
fi

if ! command -v "$VMKIT_BIN" >/dev/null 2>&1; then
  echo "VMKit not found. Set VMKIT_BIN=/path/to/vmkit or ensure it's in PATH. Checked /home/punk/Projects/HGWS/VMKit/* as well." >&2
  exit 1
fi

"$VMKIT_BIN" run \
  --cpu "$CPUS" --mem "$MEM" --disk "$IMG" \
  --virtiofs "share=$SHARE" \
  --virtiofs "huge=$HUGE" \
  --port "$PORT" \
  -- \
  /bin/bash -lc "set -e; \
    mkdir -p /share /mnt/huge1G; \
    (grep -qs virtio_fs /proc/filesystems || grep -qs virtiofs /proc/filesystems || modprobe virtiofs) >/dev/null 2>&1 || true; \
    mountpoint -q /share || mount -t virtiofs share /share || true; \
    mountpoint -q /mnt/huge1G || mount -t virtiofs huge /mnt/huge1G || true; \
    systemctl start podman || true; \
    if [ -f /share/pfs-infinity-image.tar ]; then \
      podman load -i /share/pfs-infinity-image.tar || true; \
    fi; \
    if podman image exists packetfs/pfs-infinity:latest; then \
      podman run --rm -d --name pfs-infinity --net=host \
        -v /share:/share -v /mnt/huge1G:/mnt/huge1G \
        -e PFS_BLOB_DIR=/mnt/huge1G -e PFS_SHARE_DIR=/share \
        -e REDIS_URL=redis://127.0.0.1:6389/0 \
        packetfs/pfs-infinity:latest; \
    else \
      echo 'No packetfs/pfs-infinity:latest image present; skipping container start'; \
    fi"
