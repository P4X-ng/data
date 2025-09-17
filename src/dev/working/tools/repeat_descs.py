#!/usr/bin/env python3
from __future__ import annotations
import argparse


def main() -> int:
    ap = argparse.ArgumentParser(description="Repeat/expand descriptor CSV to target count")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="outp", required=True)
    ap.add_argument("--count", type=int, required=True, help="Target total descriptors")
    args = ap.parse_args()

    # Load input descriptors
    descs = []
    with open(args.inp, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            off_s, len_s = line.split(",")
            descs.append((int(off_s), int(len_s)))
    if not descs:
        print("No descriptors in input")
        return 1

    out = open(args.outp, "w", encoding="utf-8")
    try:
        idx = 0
        for _ in range(args.count):
            off, ln = descs[idx]
            out.write(f"{off},{ln}\n")
            idx += 1
            if idx >= len(descs):
                idx = 0
    finally:
        out.close()
    print(f"Wrote {args.count} descriptors to {args.outp}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

