#!/usr/bin/env python3
import os
import re
import csv
import time
import shlex
import subprocess as sp
from datetime import datetime

VENV_PY = os.environ.get("VENV_PY", "/home/punk/.venv/bin/python")
LOG_DIR = os.path.join(os.getcwd(), "logs")
RUN = os.path.join(os.getcwd(), "dev/wip/native/pfs_shm_ring_bench")

RE_DONE = re.compile(r"\[SHM DONE\].*eff_bytes=(\d+).*elapsed=([0-9.]+).*avg=([0-9.]+) MB/s.*frames_prod=(\d+).*frames_cons=(\d+)")


def run_once(args, log_path):
    cmd = f"{RUN} {args}"
    with open(log_path, "wb") as f:
        p = sp.Popen(shlex.split(cmd), stdout=f, stderr=sp.STDOUT)
        rc = p.wait()
    return rc


def parse_done(log_path):
    eff_bytes = elapsed = avg = frames_prod = frames_cons = None
    with open(log_path, "rt", errors="ignore") as f:
        for line in f:
            m = RE_DONE.search(line)
            if m:
                eff_bytes = int(m.group(1))
                elapsed = float(m.group(2))
                avg = float(m.group(3))
                frames_prod = int(m.group(4))
                frames_cons = int(m.group(5))
    return eff_bytes, elapsed, avg, frames_prod, frames_cons


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(LOG_DIR, f"shm_pcpu_sweep_{ts}.csv")

    # Grid (arithmetic varint mode)
    ops = [
        ("fnv", [0]),
        ("crc32c", [0]),
        ("counteq", [0]),
        ("xor", [0x5A]),
        ("add", [0x05]),
    ]
    aligns = [64, 256]
    dpfs = [64, 128]
    queues_list = [1, 2]
    ports = 1
    ring_pow2 = 16
    duration = 3
    threads = 2
    arith = 1
    vstream = 1
    huge_dir = "/mnt/huge1G"

    fields = [
        "op", "imm", "align", "dpf", "ports", "queues", "ring_pow2", "duration_s", "threads",
        "arith", "vstream", "eff_MB", "avg_MBps", "frames_prod", "frames_cons",
        "cpu_avg_MBps", "CPUpwn",
    ]

    rows = []
    for op, imm_list in ops:
        for imm in imm_list:
            for align in aligns:
                for dpf in dpfs:
                    for queues in queues_list:
                        label = f"op{op}_imm{imm}_a{align}_d{dpf}_q{queues}"
                        logf = os.path.join(LOG_DIR, f"shm_sweep_{label}_{ts}.log")
                        args = (
                            f"--blob-size 2147483648 --dpf {dpf} --ring-pow2 {ring_pow2} --align {align} "
                            f"--duration {duration} --threads {threads} --arith {arith} --vstream {vstream} "
                            f"--huge-dir {huge_dir} --ports {ports} --queues {queues} --pcpu 1 --pcpu-op {op} --imm {imm}"
                        )
                        rc = run_once(args, logf)
                        eff_bytes, elapsed, avg, fp, fc = parse_done(logf)
                        eff_mb = (eff_bytes or 0) / 1e6 if eff_bytes else 0.0
                        # Baseline pass: pcpu disabled (still touches data via hash)
                        logf_cpu = os.path.join(LOG_DIR, f"shm_sweep_cpu_{label}_{ts}.log")
                        args_cpu = (
                            f"--blob-size 2147483648 --dpf {dpf} --ring-pow2 {ring_pow2} --align {align} "
                            f"--duration {duration} --threads {threads} --arith {arith} --vstream {vstream} "
                            f"--huge-dir {huge_dir} --ports {ports} --queues {queues} --pcpu 0"
                        )
                        rc2 = run_once(args_cpu, logf_cpu)
                        _, _, avg_cpu, _, _ = parse_done(logf_cpu)
                        cpupwn = (avg or 0.0) / (avg_cpu or 1e-9)
                        rows.append({
                            "op": op, "imm": imm, "align": align, "dpf": dpf,
                            "ports": ports, "queues": queues, "ring_pow2": ring_pow2,
                            "duration_s": duration, "threads": threads, "arith": arith, "vstream": vstream,
                            "eff_MB": eff_mb, "avg_MBps": avg or 0.0, "frames_prod": fp or 0, "frames_cons": fc or 0,
                            "cpu_avg_MBps": avg_cpu or 0.0, "CPUpwn": cpupwn,
                        })

    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # Summary
    def top_key(r):
        return (r.get("avg_MBps") or 0.0, r.get("eff_MB") or 0.0)
    tops = sorted(rows, key=top_key, reverse=True)[:10]
    print(f"Wrote {out_csv}")
    print("Top 10 by avg_MBps:")
    for r in tops:
        print(
            f"op={r['op']:<8} imm={r['imm']:<3} align={r['align']:<4} dpf={r['dpf']:<3} queues={r['queues']:<2} "
            f"avg_MBps={r['avg_MBps']:>7.1f} eff_MB={r['eff_MB']:>7.1f} cpu_MBps={r['cpu_avg_MBps']:>7.1f} CPUpwn={r['CPUpwn']:>6.2f}"
        )


if __name__ == "__main__":
    main()

