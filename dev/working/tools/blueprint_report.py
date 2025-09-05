#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser(description="Analyze blueprint sweep CSV and highlight wins")
    ap.add_argument("--in", dest="infile", required=True, help="Path to CSV from bench_blueprint_sweep")
    ap.add_argument("--top", type=int, default=10, help="Top-N rows by ops_ratio to print")
    args = ap.parse_args()

    rows = []
    with open(args.infile) as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Normalize numeric fields
            for k in ["seg_len","pcpu","threads","batch"]:
                if k in r and r[k] != "":
                    r[k] = int(r[k])
            for k in ["elapsed_s","MBps","pcpu_units_per_s","eff_ops_per_s","cpu_MBps","cpu_ops_per_s","ops_ratio"]:
                if k in r and r[k] != "":
                    r[k] = float(r[k])
            rows.append(r)

    # Filter rows with ops_ratio present
    winners = [r for r in rows if "ops_ratio" in r and r["ops_ratio"]]
    winners.sort(key=lambda r: r["ops_ratio"], reverse=True)

    print("Top wins by ops_ratio:")
    print("mode,seg_len,pcpu,MBps,ops_ratio")
    for r in winners[: args.top]:
        print(f"{r['mode']},{r['seg_len']},{r['pcpu']},{r['MBps']:.0f},{r['ops_ratio']:.3f}")

    # Summarize conditions for ops_ratio >= 1.0
    elite = [r for r in winners if r["ops_ratio"] >= 1.0]
    if elite:
        by_seg = defaultdict(list)
        for r in elite:
            by_seg[r["seg_len"]].append(r)
        print("\nConditions with ops_ratio >= 1.0 (winning conditions):")
        for seg, lst in sorted(by_seg.items()):
            modes = set(r["mode"] for r in lst)
            pcpu_vals = sorted(set(r["pcpu"] for r in lst))
            mbps_max = max(r["MBps"] for r in lst)
            ratio_max = max(r["ops_ratio"] for r in lst)
            print(f"seg_len={seg}: modes={sorted(modes)}, pCPU={pcpu_vals}, max_MBps={mbps_max:.0f}, max_ops_ratio={ratio_max:.3f}")
    else:
        print("\nNo ops_ratio >= 1.0 in this dataset.")


if __name__ == "__main__":
    main()
