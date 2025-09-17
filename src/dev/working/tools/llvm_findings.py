#!/usr/bin/env python3
"""
llvm_findings.py — Correlate pattern_scan results with ELF sections and instruction mnemonics.

Inputs:
  --scan-dir logs/patterns/<ts>/
  --bin      path to the original binary (for section/mnemonic info)

Outputs in the same scan-dir:
  - findings.txt: summarized insights
  - sec_entropy.csv: section -> min/max/avg entropy over covered windows
  - mnem_hist.csv: mnemonic -> count (via objdump/llvm-objdump)

Dependencies (prefer llvm tools if present):
  - llvm-readelf or readelf
  - llvm-objdump or objdump

Usage:
  /home/punk/.venv/bin/python dev/working/tools/llvm_findings.py --scan-dir logs/patterns/<ts> --bin /usr/bin/bash
"""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


def pick_tool(candidates: List[str]) -> str | None:
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
    return None


def read_entropy(path: Path) -> List[Tuple[int, float]]:
    rows: List[Tuple[int, float]] = []
    with path.open("r", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            if len(row) < 3:
                continue
            try:
                ofs = int(row[0])
                ent = float(row[1])
                rows.append((ofs, ent))
            except Exception:
                continue
    return rows


def get_sections(bin_path: Path) -> List[Tuple[str, int, int]]:
    # Returns (name, start, size)
    tool = pick_tool(["llvm-readelf", "readelf"])
    if not tool:
        return []
    try:
        out = subprocess.check_output([tool, "-S", str(bin_path)], text=True, stderr=subprocess.STDOUT)
    except Exception:
        return []
    sec: List[Tuple[str, int, int]] = []
    # readelf -S prints lines with [Nr] Name Type Address Off Size ...
    # We'll parse Off and Size (hex) and Name
    for line in out.splitlines():
        m = re.search(r"\]\s+(?P<name>\S+)\s+\S+\s+\S+\s+(?P<off>[0-9a-fA-F]+)\s+(?P<size>[0-9a-fA-F]+)\s", line)
        if not m:
            continue
        name = m.group("name")
        off = int(m.group("off"), 16)
        size = int(m.group("size"), 16)
        sec.append((name, off, size))
    return sec


def get_mnemonic_hist(bin_path: Path) -> Dict[str, int]:
    tool = pick_tool(["llvm-objdump", "objdump"])
    if not tool:
        return {}
    flags = ["-d", str(bin_path)]
    try:
        out = subprocess.check_output([tool] + flags, text=True, stderr=subprocess.STDOUT)
    except Exception:
        return {}
    hist: Dict[str, int] = {}
    # Heuristic: lines like "  401000: 48 89 e5    mov %rsp,%rbp"
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # Remove address and hex bytes; capture mnemonic (first token after bytes)
        # Pattern: optional addr:, bytes, mnemonic ...
        m = re.search(r"^([0-9a-fA-F]+:)?\s*(?:[0-9a-fA-F]{2}\s+){1,}\s*(\w+)", line)
        if m:
            mnem = m.group(2).lower()
            hist[mnem] = hist.get(mnem, 0) + 1
    return hist


def correlate_sections(ent_rows: List[Tuple[int, float]], secs: List[Tuple[str, int, int]], win: int = 4096) -> List[Tuple[str, float, float, float, int]]:
    # For each section, aggregate entropy stats from windows that overlap its file offset range
    out: List[Tuple[str, float, float, float, int]] = []
    for name, off, size in secs:
        start = off
        end = off + size
        vals: List[float] = []
        for ofs, ent in ent_rows:
            wstart = ofs
            wend = ofs + win
            if wend <= start or wstart >= end:
                continue
            vals.append(ent)
        if vals:
            out.append((name, min(vals), max(vals), sum(vals) / len(vals), len(vals)))
    return out


def write_csv(path: Path, header: List[str], rows: List[Tuple]) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(row)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Correlate entropy windows with ELF sections and mnemonics")
    ap.add_argument("--scan-dir", required=True)
    ap.add_argument("--bin", required=True)
    ap.add_argument("--win", type=int, default=4096)
    args = ap.parse_args()

    scan_dir = Path(args.scan_dir)
    bin_path = Path(args.bin)
    ent_csv = next((scan_dir.glob("*.entropy.csv")), None)
    if not ent_csv:
        print("entropy CSV not found in scan-dir")
        return 2

    ent_rows = read_entropy(ent_csv)
    secs = get_sections(bin_path)
    corr = correlate_sections(ent_rows, secs, win=args.win)
    write_csv(scan_dir / "sec_entropy.csv", ["section", "min", "max", "avg", "n"], corr)

    mnem = get_mnemonic_hist(bin_path)
    mrows = sorted(((k, v) for k, v in mnem.items()), key=lambda x: x[1], reverse=True)
    write_csv(scan_dir / "mnem_hist.csv", ["mnemonic", "count"], mrows)

    # Findings summary
    findings = scan_dir / "findings.txt"
    with findings.open("w") as f:
        f.write("Pattern+LLVM findings\n")
        f.write("=====================\n\n")
        f.write(f"Binary: {bin_path}\n")
        if corr:
            f.write("\nSection entropy (min/max/avg over overlapping windows):\n")
            for name, mn, mx, av, n in corr[:20]:
                f.write(f"  {name:20s}  min={mn:.3f} max={mx:.3f} avg={av:.3f} n={n}\n")
        else:
            f.write("\n(no section correlation available)\n")
        if mrows:
            top = mrows[:20]
            f.write("\nTop mnemonics:\n")
            for k, v in top:
                f.write(f"  {k:10s} {v}\n")
        else:
            f.write("\n(no mnemonic histogram available)\n")
    print(f"Wrote findings to {findings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
