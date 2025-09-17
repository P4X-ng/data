#!/usr/bin/env python3
"""
entropy_heatmap.py — Minimal, dependency-free entropy heatmap renderer.

Reads an entropy CSV produced by pattern_scan.py with columns:
  offset,entropy,normalized

Outputs a PPM (Portable Pixmap) grayscale image (P6) visualizing entropy per window.
- X axis: window index (column-wise)
- Y axis: a fixed small height (default 64 rows) repeated bands for visibility
- Intensity: normalized entropy (0.0..1.0) mapped to 0..255

Usage:
  /home/punk/.venv/bin/python dev/working/tools/entropy_heatmap.py \
      --in logs/patterns/<ts>/bash.entropy.csv \
      --out logs/patterns/<ts>/bash.entropy.ppm \
      --height 64

If ImageMagick 'convert' exists, you can convert PPM to PNG:
  convert bash.entropy.ppm bash.entropy.png
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path


def read_entropy_csv(path: Path) -> list[float]:
    vals: list[float] = []
    with path.open("r", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            if len(row) < 3:
                continue
            try:
                norm = float(row[2])
            except ValueError:
                continue
            # clamp
            if norm < 0.0:
                norm = 0.0
            if norm > 1.0:
                norm = 1.0
            vals.append(norm)
    return vals


def write_ppm_gray(values: list[float], out_path: Path, height: int = 64) -> None:
    if not values:
        raise SystemExit("No values to render")
    width = len(values)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("wb") as f:
        # P6 header
        f.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        # Build one row worth of RGB bytes
        row = bytearray()
        for v in values:
            g = int(round(v * 255))
            if g < 0:
                g = 0
            if g > 255:
                g = 255
            row.extend((g, g, g))
        # Repeat the row 'height' times
        for _ in range(height):
            f.write(row)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render entropy CSV to grayscale PPM heatmap")
    ap.add_argument("--in", dest="inp", required=True, help="Path to entropy CSV")
    ap.add_argument("--out", dest="out", required=True, help="Output PPM path")
    ap.add_argument("--height", type=int, default=64, help="Image height in pixels (default 64)")
    args = ap.parse_args()

    entropy_vals = read_entropy_csv(Path(args.inp))
    write_ppm_gray(entropy_vals, Path(args.out), height=args.height)
    print(f"Wrote PPM heatmap: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
