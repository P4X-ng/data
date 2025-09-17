#!/usr/bin/env python3
import csv
from pathlib import Path

def main() -> int:
    root = Path('logs')
    reports = root / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    latest_patterns = ''
    pat_root = root / 'patterns'
    if pat_root.exists():
        runs = sorted([p for p in pat_root.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
        latest_patterns = runs[0].name if runs else ''
    row = {'latest_patterns': latest_patterns}
    out = reports / 'INDEX.csv'
    with out.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        w.writeheader(); w.writerow(row)
    print(f"Wrote {out}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
