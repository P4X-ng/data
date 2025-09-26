#!/usr/bin/env python3
# DEMO: Synthetic large JSON generator (do NOT use in production runs)
# Writes a line-delimited JSON file of approximately --size-mb MiB
# Optimized to exercise ASCII/numeric banks for the Orchard planner.

import argparse
import json
import os
import random
import string
from typing import Iterator

ALPHABET = string.ascii_letters + string.digits + "     "


def gen_obj(i: int) -> dict:
    return {
        "id": i,
        "user": f"user_{i%1000}",
        "ts": f"2025-09-23T{i%24:02d}:{i%60:02d}:{(i//60)%60:02d}Z",
        "msg": "".join(random.choice(ALPHABET) for _ in range(120)),
        "tags": [f"t{(i+j)%50}" for j in range(5)],
        "value": (i * 1315423911) & 0xFFFFFFFF,
    }


def gen_lines(target_bytes: int) -> Iterator[str]:
    i = 0
    size = 0
    while size < target_bytes:
        line = json.dumps(gen_obj(i), separators=(",", ":")) + "\n"
        yield line
        size += len(line)
        i += 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="/tmp/synth.json", help="Output path (default: /tmp/synth.json)")
    p.add_argument("--size-mb", type=int, default=100, help="Approx size in MiB (default: 100)")
    args = p.parse_args()

    target = args.size_mb * (1 << 20)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    written = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for line in gen_lines(target):
            f.write(line)
            written += len(line)

    print(f"Wrote {args.out} bytes={written}")


if __name__ == "__main__":
    main()
