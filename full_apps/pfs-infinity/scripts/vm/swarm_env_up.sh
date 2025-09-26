#!/usr/bin/env bash
set -euo pipefail

# Env-driven swarm up
# Env vars with defaults:
#   TOTAL (128), BASE_PORT (9000), SHARE_DIR (.vm/pfs.mnt), HUGE_DIR (/mnt/huge1G)
#   IMG (pfs-infinity.qcow2), MEM (512), VCPUS (1), VMKIT (/home/punk/Projects/HGWS/VMKit/vmkit)
#   BATCH (0), PAUSE (0)

TOTAL=${TOTAL:-128}
BASE_PORT=${BASE_PORT:-9000}
SHARE_DIR=${SHARE_DIR:-.vm/pfs.mnt}
HUGE_DIR=${HUGE_DIR:-/mnt/huge1G}
IMG=${IMG:-pfs-infinity.qcow2}
MEM=${MEM:-512}
VCPUS=${VCPUS:-1}
VMKIT=${VMKIT:-/home/punk/Projects/HGWS/VMKit/vmkit}
BATCH=${BATCH:-0}
PAUSE=${PAUSE:-0}

echo "[swarm-env] share=$SHARE_DIR huge=$HUGE_DIR total=$TOTAL base_port=$BASE_PORT mem=$MEM vcpus=$VCPUS batch=$BATCH pause=$PAUSE"

mkdir -p "$SHARE_DIR"

if /home/punk/.venv/bin/python -c "import importlib; import sys; importlib.import_module('packetfs')" >/dev/null 2>&1; then
  bash scripts/pfsfs_mount_host.sh --mnt "$SHARE_DIR" --iprog-dir ./iprog --blob-name pfs_vblob --blob-size 1073741824 --blob-seed 1337 --window 65536 --embed 1 || true
else
  echo "[swarm-env] packetfs not installed in /home/punk/.venv; skipping mount (share dir is created)"
fi

VMKIT_BIN="$VMKIT" scripts/vm/launch_swarm.sh --total "$TOTAL" --share "$SHARE_DIR:/share" --huge "$HUGE_DIR:/mnt/huge1G" --base-port "$BASE_PORT" --img "$IMG" --mem "$MEM" --vcpus "$VCPUS" --vmkit "$VMKIT" ${BATCH:+--batch "$BATCH"} ${PAUSE:+--pause "$PAUSE"}
