#!/usr/bin/env bash
set -euo pipefail

# AF_XDP pCPU sweep runner
# - Spins up RX, runs TX across parameter combos, parses RX logs
# - Computes CPU baseline using a local helper and prints Effective CPU ratios
# - Writes CSV to logs/afxdp_sweep_${ts}.csv
#
# Environment variables (with defaults):
#   IFACE           - required (e.g., eno1 or veth-peer)
#   QUEUE           - default: 0
#   BLOB_SIZE       - default: 2147483648 (2 GiB)
#   TASKS_LIST      - comma list of descriptors (threads); default: 100000,200000,500000
#   DPF_LIST        - desc-per-frame; default: 32,64,96
#   DESC_LEN_LIST   - bytes/desc; default: 64,256,1024
#   ARITH_LIST      - 0 or 1; default: 0,1
#   OP_LIST         - checksum|xor8|add8; default: checksum
#   IMM             - default 0 (used for xor8/add8)
#   ALIGN           - default 64
#   RUNS            - repeats per combo; default 1
#   ARITH_BASE      - if set, passed to RX via --arith-base
#   TIMEOUT_RX      - seconds to wait before killing RX after TX; default 1
#
# Requirements:
#   - dev/wip/native/pfs_stream_afxdp_rx, pfs_stream_afxdp_tx (just build-net-pfs-stream-afxdp)
#   - dev/wip/native/pfs_cpu_baseline (auto-built if missing)

IFACE=${IFACE:-}
if [[ -z "$IFACE" ]]; then
  echo "Set IFACE=<iface> (e.g., eno1 or veth-peer)" >&2
  exit 1
fi

QUEUE=${QUEUE:-0}
BLOB_SIZE=${BLOB_SIZE:-2147483648}
TASKS_LIST=${TASKS_LIST:-100000,200000,500000}
DPF_LIST=${DPF_LIST:-32,64,96}
DESC_LEN_LIST=${DESC_LEN_LIST:-64,256,1024}
ARITH_LIST=${ARITH_LIST:-0,1}
OP_LIST=${OP_LIST:-checksum}
IMM=${IMM:-0}
ALIGN=${ALIGN:-64}
RUNS=${RUNS:-1}
TIMEOUT_RX=${TIMEOUT_RX:-1}

RX_BIN=dev/wip/native/pfs_stream_afxdp_rx
TX_BIN=dev/wip/native/pfs_stream_afxdp_tx
BASELINE_BIN=dev/wip/native/pfs_cpu_baseline

if [[ ! -x "$RX_BIN" ]] || [[ ! -x "$TX_BIN" ]]; then
  echo "Missing AF_XDP binaries. Run: just build-net-pfs-stream-afxdp" >&2
  exit 1
fi

if [[ ! -x "$BASELINE_BIN" ]]; then
  echo "Building CPU baseline helper..." >&2
  mkdir -p dev/wip/native
  cc -O3 -march=native -DNDEBUG -Wall -Wextra -o "$BASELINE_BIN" dev/wip/native/pfs_cpu_baseline.c || {
    echo "Failed to build $BASELINE_BIN; ensure dev/wip/native/pfs_cpu_baseline.c exists" >&2
    exit 1
  }
fi

mkdir -p logs
TS=$(date +%Y%m%d_%H%M%S)
CSV="logs/afxdp_sweep_${TS}.csv"
echo "iface,queue,blob_size,tasks,dpf,desc_len,arith,op,imm,align,bytes,rx_elapsed_s,rx_MBps,cpu_MBps,eff_cpu,frames,rx_log,tx_log" > "$CSV"

echo "Sweep starting; CSV -> $CSV" >&2

IFS=',' read -r -a tasks_arr <<< "$TASKS_LIST"
IFS=',' read -r -a dpf_arr <<< "$DPF_LIST"
IFS=',' read -r -a dlen_arr <<< "$DESC_LEN_LIST"
IFS=',' read -r -a arith_arr <<< "$ARITH_LIST"
IFS=',' read -r -a ops_arr <<< "$OP_LIST"

for op in "${ops_arr[@]}"; do
  for arith in "${arith_arr[@]}"; do
    for dpf in "${dpf_arr[@]}"; do
      for dlen in "${dlen_arr[@]}"; do
        for tasks in "${tasks_arr[@]}"; do
          for runi in $(seq 1 "$RUNS"); do
            tag="op_${op}_arith_${arith}_dpf_${dpf}_dlen_${dlen}_tasks_${tasks}_run_${runi}"
            rx_log="logs/afxdp_rx_${tag}_${TS}.log"
            tx_log="logs/afxdp_tx_${tag}_${TS}.log"
            echo "[RUN] $tag" >&2

            # Start RX
            RX_ARGS=("$RX_BIN" --ifname "$IFACE" --queue "$QUEUE" --blob-size "$BLOB_SIZE")
            RX_ARGS+=(--op "$op" --imm "$IMM")
            if [[ -n "${ARITH_BASE:-}" ]]; then RX_ARGS+=(--arith-base "$ARITH_BASE"); fi
            # Always collect baseline stats locally
            # (If you have --stats support in RX, you could add it here)

            sudo "${RX_ARGS[@]}" 2>"$rx_log" 1>&2 &
            rx_pid=$!
            echo "[RX] pid=$rx_pid" >&2
            sleep 1

            # TX args
            TX_ARGS=("$TX_BIN" --ifname "$IFACE" --queue "$QUEUE" --blob-size "$BLOB_SIZE" --desc-per-frame "$dpf" --desc-len "$dlen" --tasks "$tasks")
            if [[ "$arith" == "1" ]]; then TX_ARGS+=(--arith); fi

            sudo "${TX_ARGS[@]}" 2>"$tx_log" 1>&2 || true

            sleep "$TIMEOUT_RX"
            kill -INT "$rx_pid" >/dev/null 2>&1 || true
            sleep 0.2

            # Parse RX DONE line
            # Format: [RX DONE] eff_bytes=... (X MB) elapsed=Y s avg=Z MB/s ... frames=W
            line=$(tac "$rx_log" | grep -m1 "\[RX DONE\]") || true
            if [[ -z "$line" ]]; then
              echo "[WARN] No RX DONE line in $rx_log" >&2
              bytes=0; elapsed=0; rxmbps=0; frames=0
            else
              # Extract fields
              # bytes
              bytes=$(echo "$line" | sed -n 's/.*eff_bytes=\([0-9]\+\).*/\1/p')
              # elapsed
              elapsed=$(echo "$line" | sed -n 's/.*elapsed=\([0-9.]\+\) s.*/\1/p')
              # avg MB/s
              rxmbps=$(echo "$line" | sed -n 's/.*avg=\([0-9.]\+\) MB\/s.*/\1/p')
              # frames
              frames=$(echo "$line" | sed -n 's/.*frames=\([0-9]\+\).*/\1/p')
              bytes=${bytes:-0}; elapsed=${elapsed:-0}; rxmbps=${rxmbps:-0}; frames=${frames:-0}
            fi

            # CPU baseline over same total bytes (contiguous), same op/imm
            # If bytes==0, try to estimate: tasks * desc_len
            if [[ "$bytes" == "0" ]]; then
              bytes=$(( tasks * dlen ))
            fi

            cpu_line=$("$BASELINE_BIN" --size-bytes "$bytes" --op "$op" --imm "$IMM" 2>/dev/null || true)
            # baseline prints: CPU_BASELINE size=... ns=... MBps=...
            cpu_mbps=$(echo "$cpu_line" | sed -n 's/.*MBps=\([0-9.]\+\).*/\1/p')
            cpu_mbps=${cpu_mbps:-0}

            eff=0
            if [[ "$cpu_mbps" != "0" ]]; then
              # Effective CPU ratio = pCPU_MBps / CPU_MBps
              eff=$(python3 - << EOF
rx=${rxmbps}
cpu=${cpu_mbps}
print(f"{(rx/cpu):.6f}")
EOF
)
            fi

            echo "$IFACE,$QUEUE,$BLOB_SIZE,$tasks,$dpf,$dlen,$arith,$op,$IMM,$ALIGN,$bytes,$elapsed,$rxmbps,$cpu_mbps,$eff,$frames,$rx_log,$tx_log" >> "$CSV"
          done
        done
      done
    done
  done

done

echo "Sweep complete -> $CSV" >&2

