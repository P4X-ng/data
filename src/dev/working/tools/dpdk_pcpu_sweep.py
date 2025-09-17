#!/usr/bin/env python3
import os
import re
import sys
import csv
import time
import shlex
import signal
import subprocess as sp
from datetime import datetime

LOG_DIR = os.path.join(os.getcwd(), "logs")

RX_BIN = "dev/wip/native/pfs_stream_dpdk_rx"
TX_BIN = "dev/wip/native/pfs_stream_dpdk_tx"

# Regexes to parse stats
RE_RX_DONE = re.compile(r"\[RX-DPDK DONE\].*eff_bytes=(\d+).*elapsed=([0-9.]+).*avg=([0-9.]+) MB/s.*frames=(\d+).*desc_bytes=(\d+).*")
RE_RX_PCPU = re.compile(r"\[RX-DPDK PCPU\].*touched=([0-9.]+) MB.*desc=(\d+).*time=([0-9.]+) s.*pcpu_MBps=([0-9.]+).*")
RE_RX_STATS = re.compile(r"\[RX-DPDK STATS\].*sid_fail=(\d+).*pair_fail=(\d+).*oob=(\d+)")
RE_TX_DONE = re.compile(r"\[TX-DPDK DONE\].*eff_bytes=(\d+).*elapsed=([0-9.]+).*avg=([0-9.]+) MB/s.*frames=(\d+).*desc_bytes=(\d+).*")
RE_TX_STATS = re.compile(r"\[TX-DPDK STATS\].*alloc_fail=(\d+).*append_fail=(\d+).*tx_zero=(\d+).*encode_fail=(\d+).*tailroom_skip=(\d+)")


def run(cmd: str, stdout_path: str = None):
    """Run a command, optionally teeing to a file. Returns (returncode)."""
    if stdout_path:
        with open(stdout_path, "wb") as f:
            p = sp.Popen(shlex.split(cmd), stdout=f, stderr=sp.STDOUT)
            rc = p.wait()
            return rc
    else:
        return sp.call(shlex.split(cmd))


def parse_file(path: str):
    rx = {"eff_bytes": None, "elapsed": None, "avg_MBps": None, "frames": None, "desc_bytes": None,
          "pcpu_touched_MB": None, "pcpu_desc": None, "pcpu_time_s": None, "pcpu_MBps": None,
          "sid_fail": None, "pair_fail": None, "oob": None}
    tx = {"eff_bytes": None, "elapsed": None, "avg_MBps": None, "frames": None, "desc_bytes": None,
          "alloc_fail": None, "append_fail": None, "tx_zero": None, "encode_fail": None, "tailroom_skip": None}
    if not os.path.exists(path):
        return rx, tx
    with open(path, "rt", errors="ignore") as f:
        for line in f:
            m = RE_RX_DONE.search(line)
            if m:
                rx["eff_bytes"] = int(m.group(1))
                rx["elapsed"] = float(m.group(2))
                rx["avg_MBps"] = float(m.group(3))
                rx["frames"] = int(m.group(4))
                rx["desc_bytes"] = int(m.group(5))
                continue
            m = RE_RX_PCPU.search(line)
            if m:
                rx["pcpu_touched_MB"] = float(m.group(1))
                rx["pcpu_desc"] = int(m.group(2))
                rx["pcpu_time_s"] = float(m.group(3))
                rx["pcpu_MBps"] = float(m.group(4))
                continue
            m = RE_RX_STATS.search(line)
            if m:
                rx["sid_fail"] = int(m.group(1))
                rx["pair_fail"] = int(m.group(2))
                rx["oob"] = int(m.group(3))
                continue
            m = RE_TX_DONE.search(line)
            if m:
                tx["eff_bytes"] = int(m.group(1))
                tx["elapsed"] = float(m.group(2))
                tx["avg_MBps"] = float(m.group(3))
                tx["frames"] = int(m.group(4))
                tx["desc_bytes"] = int(m.group(5))
                continue
            m = RE_TX_STATS.search(line)
            if m:
                tx["alloc_fail"] = int(m.group(1))
                tx["append_fail"] = int(m.group(2))
                tx["tx_zero"] = int(m.group(3))
                tx["encode_fail"] = int(m.group(4))
                tx["tailroom_skip"] = int(m.group(5))
                continue
    return rx, tx


def ensure_logs():
    os.makedirs(LOG_DIR, exist_ok=True)


def veth_setup():
    # Create a fresh veth pair
    sp.call(["ip", "link", "del", "veth-pfs-rx"])  # ignore error
    sp.check_call(["ip", "link", "add", "veth-pfs-rx", "type", "veth", "peer", "name", "veth-pfs-tx"])
    sp.check_call(["ip", "link", "set", "veth-pfs-rx", "up"]) 
    sp.check_call(["ip", "link", "set", "veth-pfs-tx", "up"]) 


def veth_cleanup():
    sp.call(["ip", "link", "del", "veth-pfs-rx"])  # ignores errors


def sweep():
    ensure_logs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(LOG_DIR, f"dpdk_pcpu_sweep_{ts}.csv")

    # Parameter grid (kept modest to complete in ~1 minute)
    ops = [("fnv", 0), ("crc32c", 0), ("counteq", 0x00), ("xor", 0x5A), ("add", 0x05)]
    streams_list = [1, 4]
    dpf_list = [64]
    align_list = [64, 256]
    duration = 5

    fields = [
        "op", "imm", "streams", "dpf", "align", "duration_s",
        "rx_eff_MB", "rx_avg_MBps", "rx_frames", "rx_desc_MB",
        "pcpu_touched_MB", "pcpu_desc", "pcpu_time_s", "pcpu_MBps",
        "rx_sid_fail", "rx_pair_fail", "rx_oob",
        "tx_eff_MB", "tx_avg_MBps", "tx_frames", "tx_desc_MB",
        "tx_alloc_fail", "tx_append_fail", "tx_tx_zero", "tx_encode_fail", "tx_tailroom_skip"
    ]
    with open(out_csv, "w", newline="") as fcsv:
        w = csv.DictWriter(fcsv, fieldnames=fields)
        w.writeheader()

        for op, imm in ops:
            for streams in streams_list:
                for dpf in dpf_list:
                    for align in align_list:
                        veth_setup()
                        rx_log = os.path.join(LOG_DIR, f"sweep_rx_{op}_{imm}_{streams}_{dpf}_{align}_{ts}.log")
                        tx_log = os.path.join(LOG_DIR, f"sweep_tx_{op}_{imm}_{streams}_{dpf}_{align}_{ts}.log")

                        # RX start
                        rx_cmd = (
                            f"{RX_BIN} --ports 0 --rx-queues 1 "
                            f"--eal '-l 1 -n 4 --file-prefix=pfs_rx_v --vdev=net_af_packet0,iface=veth-pfs-rx' "
                            f"--blob-size 2147483648 --l2-skip 14 --pcpu 1 --pcpu-op {op} --imm {imm}"
                        )
                        rx_p = sp.Popen(shlex.split(rx_cmd), stdout=open(rx_log, "wb"), stderr=sp.STDOUT)
                        time.sleep(1.0)

                        # TX run
                        tx_cmd = (
                            f"{TX_BIN} --ports 0 --tx-queues 1 "
                            f"--eal '-l 0 -n 4 --file-prefix=pfs_tx_v --vdev=net_af_packet1,iface=veth-pfs-tx' "
                            f"--blob-size 2147483648 --seed 305419896 --desc-per-frame {dpf} --duration {duration} "
                            f"--align {align} --arith 1 --vstream 1 --streams {streams} --eth 1 --proto-hdr 1"
                        )
                        tx_rc = run(tx_cmd, tx_log)

                        # Stop RX
                        try:
                            rx_p.send_signal(signal.SIGINT)
                        except Exception:
                            pass
                        rx_p.wait(timeout=5)

                        # Parse logs
                        rx_stats, _ = parse_file(rx_log)
                        _, tx_stats = parse_file(tx_log)

                        row = {
                            "op": op, "imm": imm, "streams": streams, "dpf": dpf, "align": align, "duration_s": duration,
                            "rx_eff_MB": (rx_stats["eff_bytes"] or 0)/1e6,
                            "rx_avg_MBps": rx_stats["avg_MBps"],
                            "rx_frames": rx_stats["frames"],
                            "rx_desc_MB": (rx_stats["desc_bytes"] or 0)/1e6,
                            "pcpu_touched_MB": rx_stats["pcpu_touched_MB"],
                            "pcpu_desc": rx_stats["pcpu_desc"],
                            "pcpu_time_s": rx_stats["pcpu_time_s"],
                            "pcpu_MBps": rx_stats["pcpu_MBps"],
                            "rx_sid_fail": rx_stats["sid_fail"],
                            "rx_pair_fail": rx_stats["pair_fail"],
                            "rx_oob": rx_stats["oob"],
                            "tx_eff_MB": (tx_stats["eff_bytes"] or 0)/1e6,
                            "tx_avg_MBps": tx_stats["avg_MBps"],
                            "tx_frames": tx_stats["frames"],
                            "tx_desc_MB": (tx_stats["desc_bytes"] or 0)/1e6,
                            "tx_alloc_fail": tx_stats["alloc_fail"],
                            "tx_append_fail": tx_stats["append_fail"],
                            "tx_tx_zero": tx_stats["tx_zero"],
                            "tx_encode_fail": tx_stats["encode_fail"],
                            "tx_tailroom_skip": tx_stats["tailroom_skip"],
                        }
                        w.writerow(row)

                        veth_cleanup()
                        # brief pause between runs
                        time.sleep(0.5)

    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    sweep()
