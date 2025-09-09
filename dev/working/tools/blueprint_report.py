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
            for k in [
                "elapsed_s","MBps","pcpu_units_per_s","eff_ops_per_s",
                "cpu_MBps","cpu_ops_per_s","ops_ratio",
                "cpu_user_s","cpu_sys_s","cpu_percent","max_rss_kb",
                "ctx_voluntary","ctx_involuntary",
            ]:
                if k in r and r[k] != "":
                    try:
                        r[k] = float(r[k])
                    except ValueError:
                        # Some fields may be blank in non-measured rows
                        pass
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

    # CPU efficiency summary if measured fields are present
    measured = []
    for r in rows:
        cu = r.get("cpu_user_s", 0.0) or 0.0
        cs = r.get("cpu_sys_s", 0.0) or 0.0
        cpu_total = cu + cs
        if cpu_total > 0 and "elapsed_s" in r and "MBps" in r:
            mb = r["MBps"] * r["elapsed_s"]
            mb_per_cpu_s = (mb / cpu_total) if cpu_total > 0 else 0.0
            measured.append((mb_per_cpu_s, cpu_total, r))

    if measured:
        measured.sort(key=lambda t: t[0], reverse=True)
        print("\nCPU efficiency (measured rows): mode,seg_len,pcpu,threads,batch,MBps,MB_per_CPU_s,CPU_s,elapsed_s,CPU%")
        for mb_per_cpu_s, cpu_total, r in measured[: args.top]:
            cpu_pct = r.get("cpu_percent", 0.0) or 0.0
            print(
                f"{r['mode']},{r['seg_len']},{r['pcpu']},{r['threads']},{r['batch']},{r['MBps']:.0f},{mb_per_cpu_s:.0f},{cpu_total:.2f},{r['elapsed_s']:.3f},{cpu_pct:.0f}"
            )


if __name__ == "__main__":
    main()
