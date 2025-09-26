#!/usr/bin/env python3
# pfs-pktop: a simple curses TUI showing per-interface packet/byte rates and optional PacketFS metrics
# - Reads /proc/net/dev for RX/TX bytes/packets; computes rates
# - Optionally tails JSONL metrics from logs/pfs_vcpu_stats.jsonl or logs/pfs_afpkt_rx_stats.jsonl
# - Press 'q' to quit; arrows/PageUp/PageDown to change selection; 'i' to toggle lo visibility
# No external deps beyond Python stdlib

import argparse
import curses
import json
import os
import re
import time
from collections import defaultdict
from typing import Dict, Tuple, Optional

PROC_NET_DEV = "/proc/net/dev"
DEFAULT_INTERVAL = 1.0
DEFAULT_TOP_N = 10
METRIC_CANDIDATES = [
    "logs/pfs_vcpu_stats.jsonl",
    "logs/pfs_afpkt_rx_stats.jsonl",
]


def parse_args():
    p = argparse.ArgumentParser(description="PacketFS Packet Top (pfs-pktop)")
    p.add_argument("--interval", "-i", type=float, default=DEFAULT_INTERVAL, help="Refresh interval (s)")
    p.add_argument("--top", "-n", type=int, default=DEFAULT_TOP_N, help="Show top N interfaces")
    p.add_argument("--include-lo", action="store_true", help="Include loopback interface 'lo'")
    p.add_argument("--metrics", default=None, help="Path to JSONL metrics file to tail (auto if omitted)")
    p.add_argument("--iface", default=None, help="Regex filter for interface names (optional)")
    return p.parse_args()


def read_netdev() -> Dict[str, Dict[str, int]]:
    stats = {}
    try:
        with open(PROC_NET_DEV, "r") as f:
            lines = f.read().strip().splitlines()
    except Exception:
        return stats
    # Skip headers (first 2 lines)
    for line in lines[2:]:
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        name = name.strip()
        # rx: bytes packets errs drop fifo frame compressed multicast
        # tx: bytes packets errs drop fifo colls carrier compressed
        parts = data.split()
        if len(parts) < 16:
            continue
        rx_bytes, rx_pkts, rx_errs, rx_drop = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        tx_bytes, tx_pkts, tx_errs, tx_drop = int(parts[8]), int(parts[9]), int(parts[10]), int(parts[11])
        stats[name] = {
            "rx_bytes": rx_bytes,
            "rx_pkts": rx_pkts,
            "rx_errs": rx_errs,
            "rx_drop": rx_drop,
            "tx_bytes": tx_bytes,
            "tx_pkts": tx_pkts,
            "tx_errs": tx_errs,
            "tx_drop": tx_drop,
        }
    return stats


def diff_stats(prev: Dict[str, Dict[str, int]], curr: Dict[str, Dict[str, int]], dt: float):
    rows = []
    for ifn, c in curr.items():
        p = prev.get(ifn)
        if not p:
            continue
        rb = max(0, c["rx_bytes"] - p["rx_bytes"]) / dt
        tb = max(0, c["tx_bytes"] - p["tx_bytes"]) / dt
        rp = max(0, c["rx_pkts"] - p["rx_pkts"]) / dt
        tp = max(0, c["tx_pkts"] - p["tx_pkts"]) / dt
        re = max(0, c["rx_errs"] - p["rx_errs"]) / dt
        te = max(0, c["tx_errs"] - p["tx_errs"]) / dt
        rd = max(0, c["rx_drop"] - p["rx_drop"]) / dt
        td = max(0, c["tx_drop"] - p["tx_drop"]) / dt
        rows.append((ifn, rb, tb, rp, tp, re, te, rd, td))
    # sort by combined bytes/s desc
    rows.sort(key=lambda r: r[1] + r[2], reverse=True)
    return rows


def human_rate_bytes(bps: float) -> str:
    # Show MB/s with one decimal if >= 10MB/s, else 2 decimals
    mbps = bps / 1e6
    if mbps >= 10:
        return f"{mbps:5.1f} MB/s"
    return f"{mbps:5.2f} MB/s"


def human_rate_pkts(pps: float) -> str:
    if pps >= 1e6:
        return f"{pps/1e6:5.2f} Mpps"
    if pps >= 1e3:
        return f"{pps/1e3:5.1f} kpps"
    return f"{pps:5.0f} pps"


def tail_last_json(path: str) -> Optional[dict]:
    try:
        with open(path, "rb") as f:
            try:
                f.seek(-4096, os.SEEK_END)
            except OSError:
                f.seek(0, os.SEEK_SET)
            data = f.read().splitlines()
        for line in reversed(data):
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line.decode("utf-8", errors="ignore"))
            except Exception:
                continue
    except Exception:
        return None
    return None


def find_metrics_file(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit if os.path.exists(explicit) else None
    for cand in METRIC_CANDIDATES:
        if os.path.exists(cand):
            return cand
    return None


def draw(screen, args):
    curses.curs_set(0)
    screen.nodelay(True)
    last = read_netdev()
    last_t = time.monotonic()
    hide_lo = not args.include_lo
    iface_re = re.compile(args.iface) if args.iface else None
    metrics_path = find_metrics_file(args.metrics)

    while True:
        try:
            ch = screen.getch()
            if ch in (ord("q"), ord("Q")):
                break
            elif ch in (ord("i"), ord("I")):
                hide_lo = not hide_lo
        except Exception:
            pass

        time.sleep(max(0.05, args.interval))
        now = time.monotonic()
        curr = read_netdev()
        dt = max(1e-6, now - last_t)
        rows = diff_stats(last, curr, dt)
        last, last_t = curr, now

        # Filter interfaces
        filt_rows = []
        for r in rows:
            ifn = r[0]
            if hide_lo and ifn == "lo":
                continue
            if iface_re and not iface_re.search(ifn):
                continue
            filt_rows.append(r)
        filt_rows = filt_rows[: max(1, args.top)]

        # Metrics
        metrics = None
        if metrics_path:
            metrics = tail_last_json(metrics_path)

        screen.erase()
        maxy, maxx = screen.getmaxyx()
        title = f"PacketFS Packet Top  —  interval={args.interval:.2f}s  (q: quit, i: toggle lo)"
        screen.addnstr(0, 0, title, maxx, curses.A_BOLD)
        # Header
        hdr = "IFACE           RX         TX         RXpps     TXpps     RXdrop    TXdrop"
        screen.addnstr(2, 0, hdr, maxx, curses.A_UNDERLINE)
        y = 3
        for (ifn, rb, tb, rp, tp, re, te, rd, td) in filt_rows:
            line = f"{ifn:<8}  {human_rate_bytes(rb):>10}  {human_rate_bytes(tb):>10}  {human_rate_pkts(rp):>8}  {human_rate_pkts(tp):>8}  {rd:7.1f}  {td:7.1f}"
            if y < maxy - 4:
                screen.addnstr(y, 0, line, maxx)
                y += 1

        # PacketFS metrics section
        y += 1
        screen.addnstr(y, 0, "PacketFS metrics:", maxx, curses.A_BOLD)
        y += 1
        if metrics:
            # Compute derived throughput and CPUpwn when possible
            tput = None  # MB/s
            if "bytes_eff" in metrics and "dt" in metrics:
                try:
                    tput = metrics["bytes_eff"] / max(1e-9, metrics["dt"]) / 1e6
                except Exception:
                    tput = None
            # CPUpwn preference: cpupwn | CPUpwn | ops_ratio | derived throughput / cpu_MBps
            cpupwn_val = None
            for key in ("cpupwn", "CPUpwn", "ops_ratio"):
                if key in metrics:
                    try:
                        cpupwn_val = float(metrics[key])
                        break
                    except Exception:
                        pass
            if cpupwn_val is None and tput is not None:
                # Try to derive from baseline if present
                cpu_mb = None
                for k in ("cpu_MBps", "cpu_MB/s", "cpu_mb_s"):
                    if k in metrics:
                        try:
                            cpu_mb = float(metrics[k])
                            break
                        except Exception:
                            pass
                if cpu_mb and cpu_mb > 0:
                    cpupwn_val = tput / cpu_mb

            # Show CPUpwn first if available
            shown = 0
            if cpupwn_val is not None:
                line = f"  {'cpupwn':<16}: {cpupwn_val:.3f}"
                if y < maxy - 2:
                    screen.addnstr(y, 0, line, maxx)
                    y += 1
                    shown += 1

            # Show common fields (skip ops_ratio if cpupwn already shown)
            keys = [
                ("windows", "windows"),
                ("bytes_eff", "bytes_eff"),
                ("frames", "frames"),
                ("pcpu_op", "pcpu_op"),
                ("pcpu", "pcpu"),
            ]
            for k, label in keys:
                if k in metrics:
                    val = metrics[k]
                    line = f"  {label:<16}: {val}"
                    if y < maxy - 2:
                        screen.addnstr(y, 0, line, maxx)
                        y += 1
                        shown += 1
            # Throughput last
            if tput is not None:
                line = f"  {'MB/s':<16}: {tput:.2f}"
                if y < maxy - 2:
                    screen.addnstr(y, 0, line, maxx)
                    y += 1
                    shown += 1

            if shown == 0:
                screen.addnstr(y, 0, "  (no known fields; tailing JSONL ok)", maxx)
                y += 1
            screen.addnstr(y, 0, f"  metrics: {metrics_path}", maxx)
            y += 1
        else:
            screen.addnstr(y, 0, "  (no metrics file found; looking for logs/pfs_vcpu_stats.jsonl or logs/pfs_afpkt_rx_stats.jsonl)", maxx)
            y += 1

        # Footer
        screen.addnstr(maxy - 1, 0, time.strftime("%Y-%m-%d %H:%M:%S"), maxx, curses.A_DIM)
        screen.refresh()


def main():
    args = parse_args()
    curses.wrapper(draw, args)


if __name__ == "__main__":
    main()
