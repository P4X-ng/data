#!/usr/bin/env python3
import argparse
import pickle
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# General k-gram index over a blob snapshot file (default k=4).
# Stores a dict: hash -> list[offsets], truncated fanout per hash.

FNV64_OFF = 0xcbf29ce484222325
FNV64_PRIME = 0x100000001b3

def h_fnv64(b: bytes) -> int:
    h = FNV64_OFF
    for by in b:
        h ^= by
        h = (h * FNV64_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


def h_u32(b: bytes) -> int:
    x = struct.unpack('<I', b)[0]
    x ^= (x >> 13)
    x = (x * 0x9E3779B1) & 0xFFFFFFFF
    return x


def build_index(path: Path, k: int = 4, step: int = 1, fanout: int = 8) -> dict[int, list[int]]:
    data = path.read_bytes()
    n = len(data)
    idx: dict[int, list[int]] = {}
    if k <= 4:
        for i in range(0, n - k + 1, step):
            h = h_u32(data[i:i+k].ljust(4, b'\x00'))
            lst = idx.get(h)
            if lst is None:
                idx[h] = [i]
            else:
                if len(lst) < fanout:
                    lst.append(i)
    else:
        for i in range(0, n - k + 1, step):
            h = h_fnv64(data[i:i+k])
            lst = idx.get(h)
            if lst is None:
                idx[h] = [i]
            else:
                if len(lst) < fanout:
                    lst.append(i)
    return idx


def main() -> int:
    ap = argparse.ArgumentParser(description="Build k-gram index for a blob snapshot")
    ap.add_argument("--snapshot", required=True, help="Path to blob snapshot file")
    ap.add_argument("--out", default="", help="Output index path (.pkl)")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--step", type=int, default=0, help="Step size; default 1 for k<=4, else 8")
    ap.add_argument("--fanout", type=int, default=8)
    args = ap.parse_args()

    snap = Path(args.snapshot)
    k = args.k
    step = args.step if args.step > 0 else (1 if k <= 4 else 8)
    out = Path(args.out) if args.out else snap.with_suffix(f'.kg{k}.pkl')

    idx = build_index(snap, k=k, step=step, fanout=args.fanout)
    with out.open('wb') as f:
        pickle.dump(idx, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"index: {out} entries={len(idx)} k={k} step={step}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
