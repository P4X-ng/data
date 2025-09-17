#!/usr/bin/env bash
set -euo pipefail

# Usage: sweep_afpacket.sh IFACE FRAMES OPS IMMS DURATION CPU DST
#   IFACE   : e.g., enp130s0
#   FRAMES  : comma-separated, e.g., 1024,4096
#   OPS     : comma-separated ops: fnv,crc32c,counteq,add,xor
#   IMMS    : comma-separated immediates, e.g., 0,255
#   DURATION: seconds per run
#   CPU     : cpu id or 'auto'
#   DST     : dest MAC for TX (e.g., ff:ff:ff:ff:ff:ff)

IFACE="${1:-}"; FRAMES_CSV="${2:-}"; OPS_CSV="${3:-}"; IMMS_CSV="${4:-}"; DURATION="${5:-3}"; CPU_REQ="${6:-auto}"; DST="${7:-ff:ff:ff:ff:ff:ff}"
if [[ -z "$IFACE" ]]; then echo "IFACE is required" >&2; exit 2; fi

# Resolve CPU pin
CPU="$CPU_REQ"
if [[ "$CPU" == "auto" ]]; then
  if ! CPU=$(bash scripts/choose_cpu_for_iface.sh "$IFACE"); then
    echo "[warn] choose_cpu_for_iface.sh failed; defaulting to CPU=0" >&2
    CPU=0
  fi
fi

# Privilege wrapper
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo -n"
fi

# Check binaries exist
RX_BIN="dev/wip/native/pfs_stream_afpacket_rx"
TX_BIN="dev/wip/native/pfs_stream_afpacket_tx"
if [[ ! -x "$RX_BIN" || ! -x "$TX_BIN" ]]; then
  echo "[error] AF_PACKET binaries missing. Build first: just build-net-pfs-stream-afpacket" >&2
  exit 3
fi

mkdir -p logs
TS=$(date -u +"%Y-%m-%dT%H-%M-%SZ")

IFS="," read -r -a FRAMES <<< "$FRAMES_CSV"
IFS="," read -r -a OPS <<< "$OPS_CSV"
IFS="," read -r -a IMMS <<< "$IMMS_CSV"

printf "[sweep] IF=%s CPU=%s frames=[%s] ops=[%s] imm=[%s] dur=%ss\n" \
  "$IFACE" "$CPU" "$FRAMES_CSV" "$OPS_CSV" "$IMMS_CSV" "$DURATION"

summarize_log() {
  local tag="$1" log="$2"; local sz
  sz=$(wc -c < "$log" 2>/dev/null || echo 0)
  echo "[$tag] log=$log bytes=$sz"
  # Print only last 3 lines, truncate each to 160 chars, sanitize non-printables
  tail -n 3 "$log" 2>/dev/null | sed -e 's/[^[:print:]\t]/./g' | cut -c -160 | awk -v T="[$tag]" '{ print T " " $0 }'
}

for F in "${FRAMES[@]}"; do
  for OP in "${OPS[@]}"; do
    for IM in "${IMMS[@]}"; do
      echo
      echo "=== AF_PACKET F=$F OP=$OP IMM=$IM DUR=${DURATION}s IF=$IFACE CPU=$CPU ==="
      rx_log="logs/afpkt_${TS}_rx_f${F}_op${OP}_imm${IM}.log"
      tx_log="logs/afpkt_${TS}_tx_f${F}_op${OP}_imm${IM}.log"
      set +e
      taskset -c "$CPU" $SUDO "$RX_BIN" --ifname "$IFACE" --frame-size "$F" --duration "$DURATION" --cpu "$CPU" --pcpu-op "$OP" --imm "$IM" >"$rx_log" 2>&1 &
      rx_pid=$!
      sleep 0.3
      taskset -c "$CPU" $SUDO "$TX_BIN" --ifname "$IFACE" --dst "$DST" --frame-size "$F" --duration "$DURATION" --cpu "$CPU" --pcpu-op "$OP" --imm "$IM" >"$tx_log" 2>&1
      tx_rc=$?
      wait "$rx_pid"; rx_rc=$?
      set -e
      echo "[done] F=$F OP=$OP IMM=$IM tx_rc=$tx_rc rx_rc=$rx_rc"
      summarize_log tx "$tx_log"
      summarize_log rx "$rx_log"
    done
  done
done

echo "[sweep] logs written to logs/afpkt_${TS}_*.log"
