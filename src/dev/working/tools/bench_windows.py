#!/usr/bin/env python3
"""
PacketFS windowed execution benchmark.
- Generates a synthetic LLVM IR with a long add-chain of N operations
- Runs the windowed scheduler with the given window_pow2 (e.g., 16 => 64k)
- Measures total time and reports ops/sec and windows/sec

Usage: bench_windows.py [OPS] [WINDOW_POW2]
Defaults: OPS=131072, WINDOW_POW2=16
"""
from __future__ import annotations
import os
import sys
import time
import tempfile

from packetfs.exec.scheduler import WindowedScheduler


def generate_add_chain_ir(ops: int) -> str:
    lines = []
    lines.append("define dso_local i32 @main() {")
    # %1 = add nsw i32 0, 1
    if ops <= 0:
        lines.append("  ret i32 0")
        lines.append("}")
        return "\n".join(lines)
    lines.append("  %1 = add nsw i32 0, 1")
    for i in range(2, ops + 1):
        lines.append(f"  %{i} = add nsw i32 %{i-1}, 1")
    lines.append(f"  ret i32 %{ops}")
    lines.append("}")
    return "\n".join(lines)


def main():
    ops = int(sys.argv[1]) if len(sys.argv) > 1 else 131072
    window_pow2 = int(sys.argv[2]) if len(sys.argv) > 2 else 16

    ir = generate_add_chain_ir(ops)
    with tempfile.NamedTemporaryFile("w", suffix=".ll", delete=False) as tf:
        tf.write(ir)
        ll_path = tf.name

    try:
        sched = WindowedScheduler(window_pow2=window_pow2)
        t0 = time.perf_counter()
        result, syncs = sched.run(ll_path)
        t1 = time.perf_counter()
        elapsed = t1 - t0
        windows = len(syncs)
        ops_per_sec = ops / elapsed if elapsed > 0 else float("inf")
        windows_per_sec = windows / elapsed if elapsed > 0 else float("inf")

        print("PacketFS Windowed Benchmark")
        print("===========================")
        print(f"Ops:             {ops}")
        print(f"Window size:     2^{window_pow2} = {1<<window_pow2}")
        print(f"Windows formed:  {windows}")
        print(f"Elapsed:         {elapsed:.6f} s")
        print(f"Throughput:      {ops_per_sec:,.0f} ops/s | {windows_per_sec:.2f} windows/s")
        if windows > 0:
            print("\nWindow CRCs (first 5):")
            for i, ws in enumerate(syncs[:5]):
                print(f"  win={ws.window_id} crc=0x{ws.crc:04X} ops={ws.op_count}")
        # Return code (result) modulo 256 is the exit status equivalent
        print(f"Final result:    {result} (mod 256 = {result & 0xFF})")
    finally:
        try:
            os.unlink(ll_path)
        except Exception:
            pass

if __name__ == "__main__":
    main()

