#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import socket
import tempfile
import threading
import time
from typing import List, Dict, Any

from packetfs.network.packetfs_file_transfer import PacketFSFileTransfer, PFS_PORT
from packetfs.filesystem.virtual_blob import VirtualBlob


def start_server(host: str, port: int) -> PacketFSFileTransfer:
    pfs = PacketFSFileTransfer(host, port)
    def run():
        try:
            pfs.start_server()
        except Exception:
            pass
    th = threading.Thread(target=run, daemon=True)
    th.start()
    deadline = time.time() + 3.0
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    return pfs


def run_case(server: PacketFSFileTransfer,
             host: str, blob_name: str, blob_size_mb: int, seed: int,
             size_mb: int, pcpu: int, seg_len: int, mode: str,
             threads: int, batch: int, hugehint: bool, numa: str,
             ops_per_byte: float,
             coalesce: bool,
             measure_cpu: bool,
             ):  # returns dict
    vb = VirtualBlob(blob_name, blob_size_mb * (1 << 20), seed)
    vb.create_or_attach(create=True)
    vb.ensure_filled()
    try:
        vb.close()
    except Exception:
        pass

    stride = seg_len if mode == "contig" else (8191 if seg_len != 65536 else 65537)
    file_size = size_mb * (1 << 20)
    count = min(pcpu, (file_size + seg_len - 1) // seg_len)

    blueprint = {
        "mode": "formula",
        "blob": {"name": blob_name, "size": blob_size_mb * (1 << 20), "seed": seed},
        "segments": {"count": int(count), "seg_len": seg_len, "start_offset": 0, "stride": int(stride), "delta": 0},
        "file_size": int(file_size),
    }

    client = PacketFSFileTransfer()
    fd, placeholder = tempfile.mkstemp(prefix="pfs_bp_maxwin_", suffix=".placeholder")
    os.close(fd)
    pre_sent = server.stats.get("bytes_sent", 0)
    pre_recv = server.stats.get("bytes_received", 0)
    ok = client.request_blueprint(host, blueprint, placeholder)
    try:
        os.remove(placeholder)
    except Exception:
        pass
    if not ok:
        return {"ok": False}

    # Native reconstruct
    out_fd, out_path = tempfile.mkstemp(prefix="pfs_bp_out_", suffix=".bin")
    os.close(out_fd)
    bin_path = os.path.abspath("dev/wip/native/blueprint_reconstruct")
    args = [
        bin_path,
        "--blob-name", blob_name,
        "--blob-size", str(blob_size_mb * (1 << 20)),
        "--out", out_path,
        "--file-size", str(file_size),
        "--count", str(count),
        "--seg-len", str(seg_len),
        "--start-offset", "0",
        "--stride", str(stride),
        "--delta", "0",
        "--threads", str(threads),
        "--batch", str(batch),
        "--numa", numa,
        "--affinity", "1",
        "--madvise", "1",
        "--coalesce", "1" if coalesce else "0",
    ]
    if hugehint:
        args += ["--hugehint", "1"]

    import subprocess
    t0 = time.perf_counter()
    cpu_info = {}
    if measure_cpu:
        rc = subprocess.run(["/usr/bin/time","-v"]+args, check=False, text=True, capture_output=True)
        t1 = time.perf_counter()
        stderr = rc.stderr or ""
        for line in stderr.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip(); v = v.strip()
            if k == "User time (seconds)":
                try: cpu_info["cpu_user_s"] = float(v)
                except: pass
            elif k == "System time (seconds)":
                try: cpu_info["cpu_sys_s"] = float(v)
                except: pass
            elif k == "Percent of CPU this job got":
                try: cpu_info["cpu_percent"] = float(v.strip("% "))
                except: pass
            elif k == "Maximum resident set size (kbytes)":
                try: cpu_info["max_rss_kb"] = int(v)
                except: pass
            elif k == "Voluntary context switches":
                try: cpu_info["ctx_voluntary"] = int(v)
                except: pass
            elif k == "Involuntary context switches":
                try: cpu_info["ctx_involuntary"] = int(v)
                except: pass
    else:
        rc = subprocess.run(args, check=False)
        t1 = time.perf_counter()
    post_sent = server.stats.get("bytes_sent", 0)
    post_recv = server.stats.get("bytes_received", 0)

    try:
        os.remove(out_path)
    except Exception:
        pass

    if rc.returncode != 0:
        return {"ok": False}

    elapsed = t1 - t0
    mbps = (size_mb / elapsed) if elapsed > 0 else float("inf")
    eff_ops = mbps * (1 << 20) * ops_per_byte
    wire_bytes = (post_sent + post_recv) - (pre_sent + pre_recv)
    r = {
        "ok": True,
        "mode": mode,
        "seg_len": seg_len,
        "pcpu": pcpu,
        "threads": threads,
        "batch": batch,
        "elapsed": elapsed,
        "mbps": mbps,
        "pcpu_units_per_s": count / elapsed if elapsed > 0 else float("inf"),
        "eff_ops_per_s": eff_ops,
        "wire_bytes": wire_bytes,
        "wire_ratio": (wire_bytes / float(file_size)) if file_size > 0 else 0.0,
    }
    r.update(cpu_info)
    return r


def run_cpu_baseline(size_mb: int, threads: int, dumb: bool) -> float:
    import subprocess, re
    binp = os.path.abspath("dev/wip/native/cpu_baseline")
    args = [binp, "--size-mb", str(size_mb)]
    if dumb:
        args += ["--dumb"]
    else:
        args += ["--threads", str(threads)]
    out = subprocess.check_output(args, text=True)
    m = re.search(r"Throughput:\s+([0-9.]+) MB/s", out)
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser(description="Max-win blueprint parameter search")
    ap.add_argument("--size-mb", type=int, default=400)
    ap.add_argument("--blob-size-mb", type=int, default=100)
    ap.add_argument("--blob-name", default="pfs_vblob_test")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--pcpu", default="200000,400000,800000,1300000,2600000")
    ap.add_argument("--seg", default="80,256,4096")
    ap.add_argument("--threads", default="8,16,32")
    ap.add_argument("--batch", default="8,16,32")
    ap.add_argument("--modes", default="contig,scatter")
    ap.add_argument("--hugehint", action="store_true")
    ap.add_argument("--numa", default="auto")
    ap.add_argument("--ops-per-byte", type=float, default=1.0)
    ap.add_argument("--cpu-baseline", action="store_true")
    ap.add_argument("--cpu-dumb", action="store_true", help="Use single-thread dumb CPU baseline")
    ap.add_argument("--coalesce", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--measure-cpu", action="store_true")
    ap.add_argument("--out", default="logs/bp_maxwin.csv")
    args = ap.parse_args()

    host = "127.0.0.1"; port = PFS_PORT
    server = start_server(host, port)
    print(f"[maxwin] Starting sweep; will write CSV to: {os.path.abspath(args.out)} (cwd={os.getcwd()})")

    cpu_mbps = None
    if args.cpu_baseline:
        cpu_mbps = run_cpu_baseline(size_mb=args.size_mb, threads=int(args.threads.split(",")[0]), dumb=args.cpu_dumb)

    pcpu_list = [int(x) for x in args.pcpu.split(",") if x.strip()]
    seg_list = [int(x) for x in args.seg.split(",") if x.strip()]
    th_list = [int(x) for x in args.threads.split(",") if x.strip()]
    ba_list = [int(x) for x in args.batch.split(",") if x.strip()]
    modes = [s.strip() for s in args.modes.split(",") if s.strip()]

    results: List[Dict[str, Any]] = []
    best_ratio = None
    best_mbps = None

    try:
        for mode in modes:
            for seg in seg_list:
                for pcpu in pcpu_list:
                    for th in th_list:
                        for ba in ba_list:
                            r = run_case(server, host, args.blob_name, args.blob_size_mb, args.seed,
                                         args.size_mb, pcpu, seg, mode, th, ba,
                                         args.hugehint, args.numa, args.ops_per_byte,
                                         args.coalesce,
                                         args.measure_cpu)
                            if not r.get("ok", False):
                                continue
                            if cpu_mbps is not None:
                                cpu_ops = cpu_mbps * (1 << 20) * args.ops_per_byte
                                r["ops_ratio"] = (r["eff_ops_per_s"] / cpu_ops) if cpu_ops > 0 else 0.0
                            results.append(r)
                            if best_ratio is None or (cpu_mbps is not None and r.get("ops_ratio", 0) > best_ratio.get("ops_ratio", 0)):
                                best_ratio = r
                            if best_mbps is None or r["mbps"] > best_mbps["mbps"]:
                                best_mbps = r
    finally:
        server.stop()

    try:
        out_dir = os.path.dirname(args.out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w") as f:
            hdr = "mode,seg_len,pcpu,threads,batch,elapsed_s,MBps,pcpu_units_per_s,eff_ops_per_s,wire_bytes,wire_ratio"
            if args.measure_cpu:
                hdr += ",cpu_user_s,cpu_sys_s,cpu_percent,max_rss_kb,ctx_voluntary,ctx_involuntary"
            if cpu_mbps is not None:
                hdr += ",cpu_MBps,ops_ratio"
            f.write(hdr + "\n")
            for r in results:
                line = f"{r['mode']},{r['seg_len']},{r['pcpu']},{r['threads']},{r['batch']},{r['elapsed']:.3f},{r['mbps']:.2f},{r['pcpu_units_per_s']:.0f},{r['eff_ops_per_s']:.0f},{r.get('wire_bytes',0)},{r.get('wire_ratio',0):.6f}"
                if args.measure_cpu:
                    line += f",{r.get('cpu_user_s','')},{r.get('cpu_sys_s','')},{r.get('cpu_percent','')},{r.get('max_rss_kb','')},{r.get('ctx_voluntary','')},{r.get('ctx_involuntary','')}"
                if cpu_mbps is not None:
                    line += f",{cpu_mbps:.2f},{r.get('ops_ratio',0):.3f}"
                f.write(line + "\n")
        print(f"[maxwin] Wrote {len(results)} rows to {os.path.abspath(args.out)}")
    except Exception as e:
        print(f"[maxwin] ERROR writing CSV to {args.out}: {e}")

    print("Max-win summary:")
    if best_ratio:
        print("Best ops_ratio:", best_ratio)
    if best_mbps:
        print("Best MBps:", best_mbps)


if __name__ == "__main__":
    main()
