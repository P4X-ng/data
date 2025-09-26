#!/usr/bin/env bash
# Start Xephyr nested X server on :100 (or PFS_XEPHYR_DISPLAY)
# Usage: just pod xephyr
# Then: DISPLAY=:100 GUI_X11=1 just pod up
set -euo pipefail
DISP="${PFS_XEPHYR_DISPLAY:-:100}"
RES="${PFS_XEPHYR_RES:-1280x800}"
OPTS="${PFS_XEPHYR_OPTS:--ac -br -noreset}"
if ! command -v Xephyr >/dev/null 2>&1; then
  echo "[xephyr] Xephyr not found. Install: sudo apt-get install xserver-xephyr" >&2
  exit 127
fi
# If already running, just print info
if xset -display "$DISP" q >/dev/null 2>&1; then
  echo "[xephyr] Already running: DISPLAY=$DISP"
  echo "export DISPLAY=$DISP; GUI_X11=1 just pod up"
  exit 0
fi
nohup Xephyr "$DISP" -screen "$RES" $OPTS >/dev/null 2>&1 &
sleep 0.5
if xset -display "$DISP" q >/dev/null 2>&1; then
  echo "[xephyr] Started: DISPLAY=$DISP"
  echo "export DISPLAY=$DISP; GUI_X11=1 just pod up"
else
  echo "[xephyr] Failed to start Xephyr on $DISP" >&2
  exit 1
fi
