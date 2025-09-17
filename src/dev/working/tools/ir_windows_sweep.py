#!/usr/bin/env python3
# Sweep IR quicksort windows over different window sizes; write CSV

from __future__ import annotations
import subprocess
import csv
import os
import sys

VENV_PY = "/home/punk/.venv/bin/python"
SCRIPT = "dev/working/tools/ir_exec.py"
LL = "dev/working/samples/llvm/compute/quicksort.ll"
ENV = os.environ.copy()
ENV["PYTHONPATH"] = "realsrc"

WINDOWS = [12, 14, 16, 18]
OUT = "logs/ir_quicksort_windows.csv"


def run_one(pow2: int) -> dict:
    args = [VENV_PY, SCRIPT, LL, "--mode", "analyze", "--windows", "--window-pow2", str(pow2)]
    p = subprocess.run(args, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = p.stdout
    row = {"window_pow2": pow2, "windows_emitted": None, "total_ops_estimate": None, "elapsed_s": None}
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("windows_emitted:"):
            row["windows_emitted"] = int(s.split()[-1])
        elif s.startswith("total_ops_est:"):
            row["total_ops_estimate"] = int(s.split()[-1])
        elif s.startswith("elapsed (s):"):
            row["elapsed_s"] = float(s.split()[-1])
    return row


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    for w in WINDOWS:
        rows.append(run_one(w))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["window_pow2", "windows_emitted", "total_ops_estimate", "elapsed_s"]) 
        w.writeheader()
        for r in rows:
            w.writerow(r)
            print(r)
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    sys.exit(main())

