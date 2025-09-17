#!/usr/bin/env python3
"""
High-load windowed benchmark without textual IR overhead.
- Directly executes N ALU ops via in-process native endpoints
- Feeds 1-byte ref code per op to ProtocolEncoder (windowed with CRC16)
- Verifies CRC per window from the ref byte stream
- Sweeps ops upward until time budget (default 60s) or CRC mismatch

Usage: bench_windows_core.py [START_OPS] [WINDOW_POW2] [TIME_BUDGET_SEC]
Defaults: START_OPS=1048576, WINDOW_POW2=16, TIME_BUDGET_SEC=60
"""
from __future__ import annotations
import sys
import time
from typing import List

from packetfs.exec.native import PfsExecNative
from packetfs.protocol import ProtocolEncoder, SyncConfig, SYNC_MARK, crc16_ccitt


def run_once(ops: int, window_pow2: int) -> dict:
    exec_native = PfsExecNative()
    cfg = SyncConfig(window_pow2=window_pow2, window_crc16=True)
    enc = ProtocolEncoder(cfg)
    ref_bytes: List[int] = []

    # Execute ops with accumulator
    acc = 0
    out = bytearray(2)
    t0 = time.perf_counter()
    windows = []
    for i in range(ops):
        acc = exec_native.add(acc, 1)
        ref_bytes.append(1)
        enc.pack_refs(out, 0, bytes((1,)), 8)
        s = enc.maybe_sync()
        if s:
            win = int.from_bytes(s[1:3], "big")
            crc = int.from_bytes(s[3:5], "big") if len(s) >= 5 else 0
            windows.append((win, crc))
    t1 = time.perf_counter()

    # Verify CRC per window
    win_size = 1 << window_pow2
    ok = True
    for idx, (win, crc) in enumerate(windows):
        start = idx * win_size
        end = start + win_size
        wb = bytes(ref_bytes[start:end])
        expect = crc16_ccitt(wb)
        if expect != crc:
            ok = False
            break

    return {
        "ops": ops,
        "windows": len(windows),
        "elapsed": t1 - t0,
        "ops_per_sec": (ops / (t1 - t0)) if (t1 - t0) > 0 else float("inf"),
        "crc_ok": ok,
        "result": acc,
    }


def main():
    start_ops = int(sys.argv[1]) if len(sys.argv) > 1 else 1048576
    window_pow2 = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    budget = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0

    total_time = 0.0
    ops = start_ops

    print("PacketFS Windowed Core Benchmark (no IR)")
    print("======================================")
    print(f"Window size: 2^{window_pow2} = {1<<window_pow2}")
    print(f"Time budget: {budget:.1f} s\n")
    print(f"{'ops':>12}  {'windows':>8}  {'elapsed(s)':>10}  {'ops/s':>12}  {'crc':>4}")

    while total_time < budget:
        r = run_once(ops, window_pow2)
        total_time += r["elapsed"]
        print(f"{r['ops']:12d}  {r['windows']:8d}  {r['elapsed']:10.4f}  {r['ops_per_sec']:12.0f}  {'OK' if r['crc_ok'] else 'BAD'}")
        if not r["crc_ok"]:
            print("\nCRC mismatch detected. Stopping.")
            break
        ops *= 2
    print(f"\nTotal time: {total_time:.2f} s")


if __name__ == "__main__":
    main()

