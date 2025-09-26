#!/usr/bin/env python3
import csv
import sys

# cpupwn_summarize.py --pnic logs/pnic_agg_sweep.csv --cpu logs/cpu_baseline_sweep.csv --out logs/cpupwn_summary.csv
# pNIC CSV:  threads,bytes_mb,secs,avg_mb_s
# CPU  CSV:  threads,agg_mb_s

def read_pnic(path):
    out = {}
    with open(path, newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                t = int(row['threads'])
                mbps = float(row['avg_mb_s'])
                out[t] = mbps
            except Exception:
                continue
    return out

def read_cpu(path):
    out = {}
    with open(path, newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                t = int(row['threads'])
                mbps = float(row['agg_mb_s'])
                out[t] = mbps
            except Exception:
                continue
    return out

def main(argv):
    pnic_path = None
    cpu_path = None
    out_path = None
    i = 0
    while i < len(argv):
        if argv[i] == '--pnic' and i+1 < len(argv):
            pnic_path = argv[i+1]; i += 2
        elif argv[i] == '--cpu' and i+1 < len(argv):
            cpu_path = argv[i+1]; i += 2
        elif argv[i] == '--out' and i+1 < len(argv):
            out_path = argv[i+1]; i += 2
        else:
            i += 1
    if not pnic_path or not cpu_path or not out_path:
        print('Usage: cpupwn_summarize.py --pnic PNIC_CSV --cpu CPU_CSV --out OUT_CSV', file=sys.stderr)
        sys.exit(2)

    pnic = read_pnic(pnic_path)
    cpu = read_cpu(cpu_path)
    threads = sorted(set(pnic.keys()) & set(cpu.keys()))
    with open(out_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['threads', 'pnic_mb_s', 'cpu_mb_s', 'cpupwn'])
        for t in threads:
            p = pnic[t]
            c = cpu[t]
            cp = p / c if c > 0 else 0.0
            w.writerow([t, f'{p:.3f}', f'{c:.3f}', f'{cp:.3f}'])
    print(f'Wrote {out_path} with {len(threads)} rows')

if __name__ == '__main__':
    main(sys.argv[1:])
