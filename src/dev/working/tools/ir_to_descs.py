#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from typing import List, Tuple

# Minimal IR scanner leveraging the same regex semantics as IRExecutor
ADD_RE = re.compile(r"^\s*%([A-Za-z0-9_\.]+)\s*=\s*add\b.*?\bi32\s+([^,]+),\s+([^\s]+)")
SUB_RE = re.compile(r"^\s*%([A-Za-z0-9_\.]+)\s*=\s*sub\b.*?\bi32\s+([^,]+),\s+([^\s]+)")
MUL_RE = re.compile(r"^\s*%([A-Za-z0-9_\.]+)\s*=\s*mul\b.*?\bi32\s+([^,]+),\s+([^\s]+)")


def parse_ops(ll_path: str) -> int:
    ops = 0
    with open(ll_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            if ADD_RE.match(line) or SUB_RE.match(line) or MUL_RE.match(line):
                ops += 1
    return ops


def generate_descs(ll_path: str, out_path: str, blob_size: int, seg_len: int, align: int, stride: int) -> Tuple[int, int]:
    """
    Generate a CSV descriptor list (offset,len) derived from LLVM IR ops.
    One descriptor per recognized arithmetic op, walking offsets with stride and alignment,
    wrapping around blob_size as needed.
    Returns (desc_count, total_bytes).
    """
    ops = []
    with open(ll_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            if ADD_RE.match(line) or SUB_RE.match(line) or MUL_RE.match(line):
                ops.append(1)
    if not ops:
        raise RuntimeError("No arithmetic ops (add/sub/mul) found in IR")

    # Walk offsets deterministically
    off = 0
    total = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for _ in ops:
            if align:
                off &= ~((align - 1))
            if off + seg_len > blob_size:
                off = 0
                if align:
                    off &= ~((align - 1))
            out.write(f"{off},{seg_len}\n")
            total += seg_len
            off += stride if stride > 0 else seg_len
            if off >= blob_size:
                off %= blob_size
    return (len(ops), total)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate PFS descriptors from LLVM IR")
    ap.add_argument("--ll", required=True, help="Path to textual LLVM IR (.ll)")
    ap.add_argument("--out", required=True, help="Output CSV path (offset,len per line)")
    ap.add_argument("--blob-bytes", type=int, required=True, help="Blob size in bytes")
    ap.add_argument("--seg-len", type=int, default=64)
    ap.add_argument("--align", type=int, default=64)
    ap.add_argument("--stride", type=int, default=8191)
    args = ap.parse_args()

    ll = os.path.abspath(args.ll)
    if not os.path.exists(ll):
        raise SystemExit(f"IR file not found: {ll}")

    desc_count, total = generate_descs(ll, args.out, args.blob_bytes, args.seg_len, args.align, args.stride)
    print(f"Generated {desc_count} descriptors, total_bytes={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

