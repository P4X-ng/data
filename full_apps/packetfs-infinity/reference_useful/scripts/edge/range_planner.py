#!/usr/bin/env python3
"""
Range Planner: coalesce and align instruction windows for cache-friendly fetch.
Input: JSON array of {offset, length}, plus align (default 1 MiB).
Output: JSON with planned ranges and a mapping from original windows to planned
range indices + subspans.
"""

import argparse, json
from dataclasses import dataclass
from typing import List, Tuple

ALIGN = 1024 * 1024

@dataclass
class Window:
    offset: int
    length: int

@dataclass
class Range:
    start: int
    end: int  # inclusive


def align_range(offset: int, length: int, align: int) -> Range:
    start = (offset // align) * align
    end = ((offset + length + align - 1) // align) * align - 1
    return Range(start, end)


def plan(windows: List[Window], align: int = ALIGN) -> Tuple[List[Range], List[Tuple[int, int, int]]]:
    # Align and then merge overlapping/adjacent ranges
    aligned = [align_range(w.offset, w.length, align) for w in windows]
    aligned.sort(key=lambda r: r.start)

    merged: List[Range] = []
    for r in aligned:
        if not merged:
            merged.append(r)
        else:
            m = merged[-1]
            if r.start <= m.end + 1:
                merged[-1] = Range(m.start, max(m.end, r.end))
            else:
                merged.append(r)

    # Map each window to a (range_index, sub_offset, sub_length)
    mapping: List[Tuple[int, int, int]] = []
    for w in windows:
        # find merged range that contains w
        idx = None
        for i, r in enumerate(merged):
            if w.offset >= r.start and (w.offset + w.length - 1) <= r.end:
                idx = i
                sub_off = w.offset - r.start
                mapping.append((i, sub_off, w.length))
                break
        if idx is None:
            # should not happen; fallback: map to nearest
            for i, r in enumerate(merged):
                if w.offset <= r.end and (w.offset + w.length) >= r.start:
                    sub_off = max(0, w.offset - r.start)
                    sub_len = min(w.length, r.end - w.offset + 1)
                    mapping.append((i, sub_off, sub_len))
                    break

    return merged, mapping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--align', type=int, default=ALIGN)
    ap.add_argument('--windows', help='JSON array of {offset,length}', required=True)
    args = ap.parse_args()

    wins = [Window(offset=w['offset'], length=w['length']) for w in json.loads(args.windows)]
    merged, mapping = plan(wins, align=args.align)

    out = {
        'align': args.align,
        'ranges': [{'start': r.start, 'end': r.end, 'length': r.end - r.start + 1} for r in merged],
        'map': [{'range_index': i, 'sub_offset': off, 'sub_length': ln} for (i, off, ln) in mapping]
    }
    print(json.dumps(out))

if __name__ == '__main__':
    main()