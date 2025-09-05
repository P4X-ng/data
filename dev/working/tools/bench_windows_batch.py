#!/usr/bin/env python3
"""
Batch windowed benchmark minimizing Python overhead.
- Uses native add_loop for per-window ALU
- Packs one full window of refs per ProtocolEncoder call
- Sweeps ops until time budget

Usage: bench_windows_batch.py [START_OPS] [WINDOW_POW2] [TIME_BUDGET_SEC]
Defaults: START_OPS=1048576, WINDOW_POW2=16, TIME_BUDGET_SEC=60
"""
from __future__ import annotations
import sys
import time

from packetfs.exec.native import PfsExecNative
from packetfs.protocol import ProtocolEncoder, SyncConfig, SYNC_MARK, crc16_ccitt


def run_once(ops: int, window_pow2: int) -> dict:
    exec_native = PfsExecNative()
    cfg = SyncConfig(window_pow2=window_pow2, window_crc16=True)
    enc = ProtocolEncoder(cfg)

    win_size = 1 << window_pow2
    windows = ops // win_size
    remainder = ops % win_size

    acc = 0
    # Pre-build one window of refs
    refs_win = bytes([1]) * win_size
    out = bytearray(win_size * 2)

    t0 = time.perf_counter()
    syncs = []
    for w in range(windows):
        # ALU batch
        acc = exec_native.add_loop(acc, 1, win_size)
        # Protocol pack (one call)
        enc.pack_refs(out, 0, refs_win, 8)
        s = enc.maybe_sync()
        if not s:
            # Force sync if boundary alignment is off
            # (shouldn't happen with exact window-size batches)
            raise RuntimeError("Expected sync frame at window boundary")
        win = int.from_bytes(s[1:3], "big")
        crc = int.from_bytes(s[3:5], "big") if len(s) >= 5 else 0
        syncs.append((win, crc))

    if remainder:
        # Handle tail (no sync expected unless it crosses boundary)
        acc = exec_native.add_loop(acc, 1, remainder)
        refs_tail = bytes([1]) * remainder
        enc.pack_refs(out, 0, refs_tail, 8)
        s = enc.maybe_sync()
        if s:
            win = int.from_bytes(s[1:3], "big")
            crc = int.from_bytes(s[3:5], "big") if len(s) >= 5 else 0
            syncs.append((win, crc))
    t1 = time.perf_counter()

    # Verify CRCs quickly: CRC(0x01 repeated win_size)
    expected_crc = crc16_ccitt(refs_win)
    ok = all(crc == expected_crc for (_, crc) in syncs)

    elapsed = t1 - t0
    return {
        "ops": ops,
        "windows": len(syncs),
        "elapsed": elapsed,
        "ops_per_sec": (ops / elapsed) if elapsed > 0 else float("inf"),
        "crc_ok": ok,
        "result": acc,
    }


def main():
    start_ops = int(sys.argv[1]) if len(sys.argv) > 1 else 1048576
    window_pow2 = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    budget = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0

    total = 0.0
    ops = start_ops

    print("PacketFS Windowed Batch Benchmark (min Python overhead)")
    print("======================================================")
    print(f"Window size: 2^{window_pow2} = {1<<window_pow2}")
    print(f"Time budget: {budget:.1f} s\n")
    print(f"{'ops':>12}  {'windows':>8}  {'elapsed(s)':>10}  {'ops/s':>12}  {'crc':>4}")

    while total < budget:
        r = run_once(ops, window_pow2)
        total += r["elapsed"]
        print(f"{r['ops']:12d}  {r['windows']:8d}  {r['elapsed']:10.4f}  {r['ops_per_sec']:12.0f}  {'OK' if r['crc_ok'] else 'BAD'}")
        if not r["crc_ok"]:
            print("\nCRC mismatch detected. Stopping.")
            break
        ops *= 2
    print(f"\nTotal time: {total:.2f} s")

if __name__ == "__main__":
    main()

