#!/usr/bin/env bash
# yeet swarm: spawn one-to-one pinned receiver/sender pairs on local host
# Purpose: emulate per-core unikernels with decoupled producers/consumers
# Logs to logs/yeet/
#
# Env (or CLI) vars:
#   PAIRS         - number of pairs (default 8)
#   START_CPU     - first CPU index to use (default 0)
#   HOST          - destination IPv4 for senders (default 127.0.0.1)
#   BASE_PORT     - starting UDP port (default 9000)
#   LEN           - payload bytes (default 1024)
#   DURATION      - seconds to run (default 10)
#   PPS           - packets per second per sender (0 = unthrottled; default 0)
#   REPORT_MS     - listener report interval ms (default 500)
#   QUIET         - listener quiet (0/1, default 0)
#
set -euo pipefail

PAIRS=${PAIRS:-8}
START_CPU=${START_CPU:-0}
HOST=${HOST:-127.0.0.1}
BASE_PORT=${BASE_PORT:-9000}
LEN=${LEN:-1024}
DURATION=${DURATION:-10}
PPS=${PPS:-0}
REPORT_MS=${REPORT_MS:-500}
QUIET=${QUIET:-0}
# Socket buffers (bytes)
RBUF_BYTES=${RBUF_BYTES:-16777216}
SBUF_BYTES=${SBUF_BYTES:-16777216}

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
APP_DIR="$ROOT/full_apps/osv-yeet"
BIN_DIR="$APP_DIR/bin"
LOG_DIR="$ROOT/logs/yeet"
mkdir -p "$LOG_DIR"

# Build if missing
if [[ ! -x "$BIN_DIR/yeet_listener" || ! -x "$BIN_DIR/yeet_sender" ]]; then
  echo "[build] yeet sender/listener"
  make -C "$APP_DIR" all -j
fi

pids=()

cleanup() {
  trap - INT TERM
  echo "\n[yeet-swarm] stopping..."
  for pid in "${pids[@]:-}"; do kill "${pid}" 2>/dev/null || true; done
}
trap cleanup INT TERM

# Spawn listeners pinned to odd CPUs, senders to even CPUs (or vice versa)
# Mapping: pair i -> CPUs (START_CPU+2*i) and (START_CPU+2*i+1)
for ((i=0;i<PAIRS;i++)); do
  port=$(( BASE_PORT + i ))
  cpu_rx=$(( START_CPU + 2*i ))
  cpu_tx=$(( START_CPU + 2*i + 1 ))
  rx_log="$LOG_DIR/listener_${i}_cpu${cpu_rx}_port${port}.log"
  tx_log="$LOG_DIR/sender_${i}_cpu${cpu_tx}_port${port}.log"

  echo "[pair $i] RX cpu=$cpu_rx port=$port | TX cpu=$cpu_tx host=$HOST:$port len=$LEN pps=$PPS dur=$DURATION"

  # Listener (increase recvbuf)
  ADDR=0.0.0.0 PORT=$port DURATION=$DURATION REPORT_MS=$REPORT_MS QUIET=$QUIET RECVBUF=$RBUF_BYTES \
    taskset -c "$cpu_rx" nice -n -20 "$BIN_DIR/yeet_listener" >"$rx_log" 2>&1 &
  pids+=("$!")

  # Small stagger so port is bound
  sleep 0.1

  # Sender (increase sendbuf)
  HOST=$HOST PORT=$port LEN=$LEN DURATION=$DURATION PPS=$PPS SENDBUF=$SBUF_BYTES \
    taskset -c "$cpu_tx" nice -n -20 "$BIN_DIR/yeet_sender" >"$tx_log" 2>&1 &
  pids+=("$!")

  # Per-pair stagger to avoid burst collisions
  sleep 0.05
done

# Wait for duration + small guard, then collect results
sleep "$DURATION"
# Give listeners a moment to print last report
sleep 0.5
cleanup || true

# Summarize
printf "pair,cpu_rx,cpu_tx,port,mbps,pkts,drops\n"
for ((i=0;i<PAIRS;i++)); do
  port=$(( BASE_PORT + i ))
  cpu_rx=$(( START_CPU + 2*i ))
  cpu_tx=$(( START_CPU + 2*i + 1 ))
  rx_log="$LOG_DIR/listener_${i}_cpu${cpu_rx}_port${port}.log"
  # Parse last stats line from listener
  # Find the last stats line with a rate reported
  line=$(grep -a -F '[yeet-listen]' "$rx_log" | grep -a -E 'rate=[0-9]+' | grep -a -v 'rate=0.000' | tail -n1 || true)
  # [yeet-listen] pkts=... bytes=... drops=... elapsed=... s rate=... GiB/s, ... Mpps
  if [[ -z "$line" ]]; then
    # fallback to last line
    line=$(grep -a -F '[yeet-listen]' "$rx_log" | tail -n1 || true)
  fi
  if [[ -n "$line" ]]; then
    pkts=$(sed -n 's/.*pkts=\([0-9][0-9]*\).*/\1/p' <<< "$line")
    bytes=$(sed -n 's/.*bytes=\([0-9][0-9]*\).*/\1/p' <<< "$line")
    drops=$(sed -n 's/.*drops=\([0-9][0-9]*\).*/\1/p' <<< "$line")
    gib_s=$(sed -n 's/.*rate=\([0-9.][0-9.]*\) GiB\/s.*/\1/p' <<< "$line")
    if [[ -n "$gib_s" ]]; then
      mbps=$(python3 - <<PY 2>/dev/null || echo "NA"
try:
  import sys
  v=float(sys.stdin.read().strip())
  print(f"{v*1024.0:.2f}")
except Exception:
  print("NA")
PY
<<<"$gib_s")
    else
      mbps=NA
    fi
    printf "%d,%d,%d,%d,%s,%s,%s\n" "$i" "$cpu_rx" "$cpu_tx" "$port" "$mbps" "${pkts:-NA}" "${drops:-NA}"
  else
    printf "%d,%d,%d,%d,NA,NA,NA\n" "$i" "$cpu_rx" "$cpu_tx" "$port"
  fi

done
