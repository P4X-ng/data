#!/usr/bin/env python3
# Sweep pCPU bench across threads, batch, reps; write CSV

from __future__ import annotations
import itertools
import subprocess
import sys
import csv
import os

VENV_PY = "/home/punk/.venv/bin/python"
SCRIPT = "dev/working/tools/pcpu_bench.py"
ENV = os.environ.copy()
ENV["PYTHONPATH"] = "src:realsrc"

PARAMS = {
    "duration": [3.0],
    "threads": [1, 2, 4, 8, 16],
    "batch": [4096, 8192, 16384],
    "reps": [4, 8, 16, 32],
}

OUT = "logs/pcpu_sweep.csv"


def run_one(duration: float, threads: int, batch: int, reps: int) -> dict:
    args = [VENV_PY, SCRIPT,
            "--duration", str(duration),
            "--threads", str(threads),
            "--batch", str(batch),
            "--reps", str(reps)]
    p = subprocess.run(args, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = p.stdout
    # Parse from printed lines
    row = {
        "duration": duration,
        "threads": threads,
        "batch": batch,
        "reps": reps,
        "throughput_tasks_per_sec": None,
        "avg_queue_wait_us": None,
        "completed_tasks": None,
    }
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("throughput_tasks_per_sec:"):
            row["throughput_tasks_per_sec"] = float(line.split()[-1])
        elif line.startswith("avg_queue_wait_us:"):
            row["avg_queue_wait_us"] = float(line.split()[-1])
        elif line.startswith("completed_tasks:"):
            row["completed_tasks"] = int(line.split()[-1])
    return row


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    combos = list(itertools.product(PARAMS["duration"], PARAMS["threads"], PARAMS["batch"], PARAMS["reps"]))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["duration", "threads", "batch", "reps", "throughput_tasks_per_sec", "avg_queue_wait_us", "completed_tasks"])\

        w.writeheader()
        for d, t, b, r in combos:
            row = run_one(d, t, b, r)
            w.writerow(row)
            print(row)
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    sys.exit(main())

