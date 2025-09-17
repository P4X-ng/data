#!/usr/bin/env python3
"""
PacketFS LLVM IR Executor (production CLI)

Real, testable LLVM IR execution front-end using realsrc PacketFS components.
- Parses a subset of textual LLVM IR
- Executes arithmetic chains via native lib (fallback to micro_executor for add)
- Optionally encodes operation stream into PacketFS windows for analysis
- Emits measurable, realistic timings (no simulated speeds)

Usage:
  PYTHONPATH=realsrc python dev/working/tools/ir_exec.py <file.ll> [--mode both] [--windows] [--json]

Prereqs:
  - For sub/mul support, build the in-process library:
      just build-exec-lib
  - For add-only chains, no extra build is needed (falls back to micro_executor)

"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, Any

# Import production modules from realsrc
try:
    from packetfs.exec.ir_frontend import IRExecutor, _NATIVE
    from packetfs.exec.scheduler import WindowedScheduler
except Exception as e:
    print("Error: failed to import PacketFS execution modules.\n"
          "Hint: run with PYTHONPATH=realsrc", file=sys.stderr)
    raise


def analyze_ir_counts(ll_path: str) -> Dict[str, int]:
    """Lightweight instruction counting using IRExecutor regex patterns."""
    ex = IRExecutor()
    counts = {"add": 0, "sub": 0, "mul": 0, "load_volatile_i32": 0, "ret": 0}
    with open(ll_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            if ex.ADD_RE.match(line):
                counts["add"] += 1
            elif ex.SUB_RE.match(line):
                counts["sub"] += 1
            elif ex.MUL_RE.match(line):
                counts["mul"] += 1
            elif ex.LOAD_VOL_RE.match(line):
                counts["load_volatile_i32"] += 1
            elif ex.RET_VAR_RE.match(line) or ex.RET_CONST_RE.match(line):
                counts["ret"] += 1
    return counts


def run_executor(ll_path: str) -> Dict[str, Any]:
    ex = IRExecutor()
    t0 = time.perf_counter()
    result = ex.execute_file(ll_path)
    t1 = time.perf_counter()
    return {
        "result": int(result) & 0xFFFFFFFF,
        "elapsed_s": t1 - t0,
        "native_available": _NATIVE is not None,
    }


essential_notes = (
    "SUB/MUL require libpfs_exec.so. Build with: just build-exec-lib"
)


def run_scheduler_windows(ll_path: str, ops_only: bool = False, window_pow2: int = 16) -> Dict[str, Any]:
    sched = WindowedScheduler(window_pow2=window_pow2)
    t0 = time.perf_counter()
    result_check = None
    if ops_only:
        op_count, windows = sched.encode_ops_only(ll_path)
    else:
        result_check, windows = sched.run(ll_path)
    t1 = time.perf_counter()
    # Summarize window syncs
    sync_summary = {
        "windows_emitted": len(windows),
        "last_window": windows[-1].window_id if windows else None,
        "total_ops_estimate": sum(w.op_count for w in windows) if windows else 0,
    }
    out = {
        "elapsed_s": t1 - t0,
        "sync_summary": sync_summary,
    }
    if result_check is not None:
        out["result_check"] = int(result_check) & 0xFFFFFFFF
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="PacketFS LLVM IR executor")
    ap.add_argument("ll_file", help="Path to textual LLVM IR (.ll)")
    ap.add_argument("--mode", choices=["analyze", "execute", "both"], default="both",
                    help="Which actions to perform (default: both)")
    ap.add_argument("--windows", action="store_true",
                    help="Also encode operation stream into PacketFS windows and report sync summary")
    ap.add_argument("--window-pow2", type=int, default=16,
                    help="Window size as power-of-two (default: 16 => 65536)")
    ap.add_argument("--json", action="store_true",
                    help="Emit JSON summary instead of human-readable text")
    args = ap.parse_args(argv)

    ll_file = os.path.abspath(args.ll_file)
    if not os.path.exists(ll_file):
        print(f"Error: LLVM IR file not found: {ll_file}", file=sys.stderr)
        return 2

    out: Dict[str, Any] = {"file": ll_file}

    if args.mode in ("analyze", "both"):
        counts = analyze_ir_counts(ll_file)
        out["analysis"] = counts

    if args.mode in ("execute", "both"):
        try:
            exec_res = run_executor(ll_file)
            out["execute"] = exec_res
        except RuntimeError as e:
            msg = str(e)
            out["execute_error"] = msg
            if "requires native lib" in msg:
                out["hint"] = essential_notes

    if args.windows:
        try:
            win_res = run_scheduler_windows(ll_file, ops_only=(args.mode == "analyze"), window_pow2=args.window_pow2)
            out["windows"] = win_res
        except RuntimeError as e:
            out["windows_error"] = str(e)

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"IR file: {out['file']}")
        if "analysis" in out:
            a = out["analysis"]
            print("Instruction counts:")
            for k in ["add", "sub", "mul", "load_volatile_i32", "ret"]:
                print(f"  {k:18s}: {a.get(k, 0)}")
        if "execute" in out:
            e = out["execute"]
            print("\nExecution:")
            print(f"  result:        {e['result']}")
            print(f"  elapsed (s):   {e['elapsed_s']:.6f}")
            print(f"  native lib:    {'yes' if e['native_available'] else 'no (add-only fallback)'}")
        if "execute_error" in out:
            print("\nExecution error:")
            print(f"  {out['execute_error']}")
            if "hint" in out:
                print(f"  Hint: {out['hint']}")
        if "windows" in out:
            w = out["windows"]
            print("\nWindows (PacketFS sync):")
            if "result_check" in w:
                print(f"  result(check): {w['result_check']}")
            print(f"  elapsed (s):   {w['elapsed_s']:.6f}")
            ss = w["sync_summary"]
            print(f"  windows_emitted: {ss['windows_emitted']}")
            print(f"  last_window:     {ss['last_window']}")
            print(f"  total_ops_est:   {ss['total_ops_estimate']}")
            print(f"  window_pow2:     {args.window_pow2}")
        if "windows_error" in out:
            print("\nWindows error:")
            print(f"  {out['windows_error']}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

