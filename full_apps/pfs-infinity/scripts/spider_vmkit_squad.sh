#!/usr/bin/env bash
set -euo pipefail

# spider_vmkit_squad.sh: Launch a squad of microVMs via VMKit and run spider agents inside.
# Requires VMKit to be installed or discoverable (like scripts/run_vmkit.sh).
# Usage:
#   scripts/spider_vmkit_squad.sh up --img pfs-infinity.qcow2 --replicas 4 --coord http://host:8811 [--cpu 2 --mem 4096 --lease-n 25 --ua pfs-spider --ignore-robots 0]
#   scripts/spider_vmkit_squad.sh down

CMD=${1:-}
shift || true

IMG="pfs-infinity.qcow2"
REPLICAS=2
CPU=2
MEM=4096
COORD="http://127.0.0.1:8811"
LEASE_N=25
UA="pfs-spider"
IGNORE_ROBOTS=0
MODE="linux-container" # or "osv"

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --img) IMG="$2"; shift 2 ;;
    --replicas) REPLICAS="$2"; shift 2 ;;
    --coord) COORD="$2"; shift 2 ;;
    --cpu) CPU="$2"; shift 2 ;;
    --mem) MEM="$2"; shift 2 ;;
    --lease-n) LEASE_N="$2"; shift 2 ;;
    --ua) UA="$2"; shift 2 ;;
    --ignore-robots) IGNORE_ROBOTS="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Locate VMKit like run_vmkit.sh does
VMKIT_BIN=${VMKIT_BIN:-vmkit}
if ! command -v "$VMKIT_BIN" >/dev/null 2>&1; then
  for cand in \
    "/home/punk/Projects/HGWS/VMKit/vmkit" \
    "/home/punk/Projects/HGWS/VMKit/vmkit.sh" \
    "/home/punk/Projects/HGWS/VMKit/bin/vmkit" \
    "/home/punk/Projects/HGWS/VMKit/VMKit"; do
    if [ -x "$cand" ]; then VMKIT_BIN="$cand"; break; fi
  done
fi
if ! command -v "$VMKIT_BIN" >/dev/null 2>&1; then
  echo "VMKit not found; set VMKIT_BIN or install it" >&2
  exit 1
fi

STATE_DIR=".vmkit-squad"
mkdir -p "$STATE_DIR"

case "$CMD" in
  up)
    echo "Launching $REPLICAS microVMs (img=$IMG, cpu=$CPU, mem=${MEM}Mi, mode=$MODE)"
    for i in $(seq 1 "$REPLICAS"); do
      NAME="pfs-swarm-$i"
      if [ "$MODE" = "osv" ]; then
        # Boot OSv image that already autostarts the agent inside guest
        "$VMKIT_BIN" run \
          --name "$NAME" \
          --cpu "$CPU" --mem "$MEM" --disk "$IMG" \
          --port "0.0.0.0:0" \
          >/dev/null 2>&1 &
      else
        # Use VMKit to boot linux VM image and run a containerized worker via podman in-guest
        "$VMKIT_BIN" run \
          --name "$NAME" \
          --cpu "$CPU" --mem "$MEM" --disk "$IMG" \
          --virtiofs "share=/srv/pfs-share:/share" \
          --port "0.0.0.0:0" \
          -- \
          /bin/bash -lc "systemctl start podman || true; \
            if [ -f /share/pfs-infinity-image.tar ]; then podman load -i /share/pfs-infinity-image.tar || true; fi; \
            COORD_URL='$COORD' SPIDER_UA='$UA' SPIDER_LEASE_N='$LEASE_N' SPIDER_IGNORE_ROBOTS='$IGNORE_ROBOTS' REDIS_URL='redis://127.0.0.1:6389/0' \
            podman run --rm --name spider-agent-$i --net=host -v /share:/share packetfs/pfs-infinity:latest python -m app.agents.worker" \
          >/dev/null 2>&1 &
      fi
      echo "$!" > "$STATE_DIR/$NAME.pid"
    done
    echo "Swarm started. Use 'just swarm-down' to stop."
    ;;
  down)
    echo "Stopping swarm..."
    if compgen -G "$STATE_DIR/*.pid" > /dev/null; then
      for f in $STATE_DIR/*.pid; do
        PID=$(cat "$f" || true)
        if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
          kill "$PID" 2>/dev/null || true
        fi
        rm -f "$f"
      done
    fi
    # Best-effort: kill any vmkit processes with our name
    pgrep -f "pfs-swarm-" >/dev/null 2>&1 && pkill -f "pfs-swarm-" || true
    echo "Swarm stopped."
    ;;
  *)
    echo "Usage: $0 {up|down} [--img IMG --replicas N --coord URL --cpu C --mem M --lease-n N --ua UA --ignore-robots 0|1]" >&2
    exit 2
    ;;
 esac
