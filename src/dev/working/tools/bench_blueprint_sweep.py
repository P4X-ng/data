#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import tempfile
import threading
import time
from typing import List, Dict, Any

from packetfs.network.packetfs_file_transfer import PacketFSFileTransfer, PFS_PORT
from packetfs.filesystem.virtual_blob import VirtualBlob


def start_server_in_thread(host: str, port: int) -> PacketFSFileTransfer:
    pfs = PacketFSFileTransfer(host, port)

    def run():
        try:
            pfs.start_server()
        except Exception:
            pass

    th = threading.Thread(target=run, daemon=True)
    th.start()
    # Wait until server is listening
    deadline = time.time() + 3.0
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    return pfs


def run_one(server: PacketFSFileTransfer,
            blob_name: str, blob_size_mb: int, seed: int, size_mb: int,
            base_units: int, seg_len: int, stride: int,
            threads: int, batch: int,
            hugehint: bool, numa: str, numa_interleave: bool,
            coalesce: bool,
            measure_cpu: bool,
            mlock_pages: bool,
            out_hugefs_dir: str,
            blob_file_path: str) -> Dict[str, Any]:
    # Ensure blob exists. If blob_file_path is set, we skip VirtualBlob and use hugetlbfs file mapping.
    if not blob_file_path:
        vb = VirtualBlob(blob_name, blob_size_mb * (1 << 20), seed)
        vb.create_or_attach(create=True)
        vb.ensure_filled()
        # Close our handle early; native reconstructor will attach by name
        try:
            vb.close()
        except Exception:
            pass

    file_size = size_mb * (1 << 20)
    count_limit = (file_size + seg_len - 1) // seg_len
    count = min(base_units, count_limit)
    blueprint = {
        "mode": "formula",
        "blob": {"name": blob_name, "size": blob_size_mb * (1 << 20), "seed": seed},
        "segments": {
            "count": int(count),
            "seg_len": int(seg_len),
            "start_offset": 0,
            "stride": int(stride),
            "delta": 0,
        },
        "file_size": int(file_size),
    }

    # Ack blueprint
    client = PacketFSFileTransfer()
    # Use placeholder path
    fd, placeholder = tempfile.mkstemp(prefix="pfs_bp_sweep_", suffix=".bin.placeholder")
    os.close(fd)
    # Account bytes on wire before
    pre_sent = server.stats.get("bytes_sent", 0)
    pre_recv = server.stats.get("bytes_received", 0)
    ok = client.request_blueprint("127.0.0.1", blueprint, placeholder)
    try:
        os.remove(placeholder)
    except Exception:
        pass
    if not ok:
        return {"ok": False, "error": "ack_failed"}

    # Native reconstruct
    out_fd, out_path = tempfile.mkstemp(prefix="pfs_bp_out_", suffix=".bin")
    os.close(out_fd)
    bin_path = os.path.abspath("dev/wip/native/blueprint_reconstruct")
    args = [
        bin_path,
        "--blob-name", blueprint["blob"]["name"],
        "--blob-size", str(blueprint["blob"]["size"]),
        "--out", out_path,
        "--file-size", str(blueprint["file_size"]),
        "--count", str(blueprint["segments"]["count"]),
        "--seg-len", str(blueprint["segments"]["seg_len"]),
        "--start-offset", str(blueprint["segments"]["start_offset"]),
        "--stride", str(blueprint["segments"]["stride"]),
        "--delta", str(blueprint["segments"]["delta"]),
        "--threads", str(threads),
        "--batch", str(batch),
        "--affinity", "1",
        "--madvise", "1",
        "--coalesce", "1" if coalesce else "0",
        "--numa", numa,
        "--numa-interleave", "1" if numa_interleave else "0",
    ]
    if hugehint:
        args += ["--hugehint", "1"]
    if mlock_pages:
        args += ["--mlock", "1"]
    if out_hugefs_dir:
        args += ["--out-hugefs-dir", out_hugefs_dir]
    if blob_file_path:
        args += ["--blob-file", blob_file_path]

    import subprocess, re
    t0 = time.perf_counter()
    cpu_info = {}
    if measure_cpu:
        time_args = ["/usr/bin/time", "-v"] + args
        rc = subprocess.run(time_args, check=False, text=True, capture_output=True)
        t1 = time.perf_counter()
        # Parse /usr/bin/time -v stderr
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
    # Account bytes on wire after
    post_sent = server.stats.get("bytes_sent", 0)
    post_recv = server.stats.get("bytes_received", 0)

    elapsed = t1 - t0
    try:
        os.remove(out_path)
    except Exception:
        pass

    wire_bytes = (post_sent + post_recv) - (pre_sent + pre_recv)
    r = {
        "ok": (rc.returncode == 0),
        "elapsed": elapsed,
        "mbps": (size_mb / elapsed) if elapsed > 0 else float("inf"),
        "pcpu_units": count,
        "pcpu_units_per_s": (count / elapsed) if elapsed > 0 else float("inf"),
        "seg_len": seg_len,
        "stride": stride,
        "threads": threads,
        "batch": batch,
        "wire_bytes": wire_bytes,
        "wire_ratio": (wire_bytes / float(size_mb * (1 << 20))) if size_mb > 0 else 0.0,
    }
    r.update(cpu_info)
    return r


def main():
    ap = argparse.ArgumentParser(description="Blueprint sweep benchmark")
    ap.add_argument("--size-mb", type=int, default=400)
    ap.add_argument("--blob-size-mb", type=int, default=100)
    ap.add_argument("--blob-name", default="pfs_vblob_test")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--hugehint", action="store_true")
    ap.add_argument("--numa", default="auto", help="auto|none|node:N")
    ap.add_argument("--numa-interleave", action="store_true")
    ap.add_argument("--pcpu", default="200000,800000,1300000", help="comma-separated base_units")
    ap.add_argument("--seg", default="80,256,4096", help="comma-separated seg_len bytes")
    ap.add_argument("--include-scatter", action="store_true", help="also run scattered stride")
    ap.add_argument("--out", default="", help="Optional path to write CSV output")
    # Coalescing toggle
    ap.add_argument("--coalesce", action=argparse.BooleanOptionalAction, default=True, help="Enable contiguous segment coalescing (default: on)")
    # CPU measurement
    ap.add_argument("--measure-cpu", action="store_true", help="Run native under /usr/bin/time -v and record CPU stats")
    # Memory mapping controls
    ap.add_argument("--mlock", action="store_true", help="Lock blob and output pages in RAM using mlock")
    ap.add_argument("--out-hugefs-dir", default="", help="Directory of a hugetlbfs mount for output mapping (e.g., /mnt/huge or /mnt/huge1g)")
    ap.add_argument("--blob-hugefs-dir", default="", help="Directory of a hugetlbfs mount for the blob backing file")
    # Effective ops settings
    ap.add_argument("--ops-per-byte", type=float, default=1.0, help="Ops counted per byte to compute effective ops/s")
    ap.add_argument("--cpu-baseline", action="store_true", help="Run CPU baseline to compute ops/s ratio")
    ap.add_argument("--cpu-threads", type=int, default=0, help="CPU baseline threads (default: same as --threads)")
    ap.add_argument("--cpu-size-mb", type=int, default=0, help="CPU baseline size in MB (default: same as --size-mb)")
    args = ap.parse_args()

    host = "127.0.0.1"; port = PFS_PORT
    server = start_server_in_thread(host, port)

    # Optional: prepare a hugefs-backed blob file once and reuse
    blob_file_path = ""
    if args.blob_hugefs_dir:
        import mmap
        import errno
        os.makedirs(args.blob_hugefs_dir, exist_ok=True)
        # Stable name to allow reuse
        blob_file_path = os.path.join(args.blob_hugefs_dir, f"pfs_blob_{args.blob_name}.bin")
        # Create/truncate with hugefs alignment handling
        fd = os.open(blob_file_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            size_bytes = args.blob_size_mb * (1 << 20)
            # Try exact; if EINVAL, try 2MB and then 1GB rounding
            try:
                os.ftruncate(fd, size_bytes)
                map_len = size_bytes
            except OSError as e:
                if e.errno == errno.EINVAL:
                    two_mb = 2 * 1024 * 1024
                    one_g = 1024 * 1024 * 1024
                    s2 = ((size_bytes + two_mb - 1) // two_mb) * two_mb
                    try:
                        os.ftruncate(fd, s2)
                        map_len = s2
                    except OSError:
                        s3 = ((size_bytes + one_g - 1) // one_g) * one_g
                        os.ftruncate(fd, s3)
                        map_len = s3
                else:
                    raise
            # Deterministic fill using xorshift32 block; fill via per-page mmap (required by hugetlbfs)
            def fill_block(n: int, seed: int) -> bytes:
                out = bytearray(n)
                state = (seed ^ 0x9E3779B9) & 0xFFFFFFFF
                i = 0
                while i + 4 <= n:
                    state ^= (state << 13) & 0xFFFFFFFF
                    state ^= (state >> 17) & 0xFFFFFFFF
                    state ^= (state << 5) & 0xFFFFFFFF
                    w = state
                    out[i + 0] = (w >> 0) & 0xFF
                    out[i + 1] = (w >> 8) & 0xFF
                    out[i + 2] = (w >> 16) & 0xFF
                    out[i + 3] = (w >> 24) & 0xFF
                    i += 4
                while i < n:
                    state ^= (state << 13) & 0xFFFFFFFF
                    state ^= (state >> 17) & 0xFFFFFFFF
                    state ^= (state << 5) & 0xFFFFFFFF
                    out[i] = state & 0xFF
                    i += 1
                return bytes(out)
            block = fill_block(1 << 20, args.seed)
            blen = len(block)
            # Heuristic page size choice based on dir name
            page_size = (1 << 30) if ("1g" in args.blob_hugefs_dir.lower()) else (2 << 20)
            off = 0
            while off < size_bytes:
                map_len_local = page_size
                try:
                    mm = mmap.mmap(fd, length=map_len_local, access=mmap.ACCESS_WRITE, offset=off)
                except Exception:
                    # Fallback: try mapping only the remaining bytes rounded up to 2MB when possible
                    rem = size_bytes - off
                    two_mb = 2 * 1024 * 1024
                    map_len_local = ((rem + two_mb - 1) // two_mb) * two_mb
                    mm = mmap.mmap(fd, length=map_len_local, access=mmap.ACCESS_WRITE, offset=off)
                to_write = min(page_size, size_bytes - off)
                pos = 0
                while pos < to_write:
                    n = min(blen, to_write - pos)
                    mm[pos:pos+n] = block[:n]
                    pos += n
                mm.flush(); mm.close()
                off += page_size
            os.fsync(fd)
        finally:
            os.close(fd)

    # Optional CPU baseline
    cpu_mbps = None
    if args.cpu_baseline:
        import subprocess, re
        cpu_threads = args.cpu_threads if args.cpu_threads > 0 else args.threads
        cpu_size = args.cpu_size_mb if args.cpu_size_mb > 0 else args.size_mb
        cpu_bin = os.path.abspath("dev/wip/native/cpu_baseline")
        try:
            out = subprocess.check_output([cpu_bin, "--size-mb", str(cpu_size), "--threads", str(cpu_threads), "--delta", "0"], text=True)
            m = re.search(r"Throughput:\s+([0-9.]+) MB/s", out)
            if m:
                cpu_mbps = float(m.group(1))
        except Exception:
            cpu_mbps = None

    try:
        pcpu_list = [int(x) for x in args.pcpu.split(",") if x.strip()]
        seg_list = [int(x) for x in args.seg.split(",") if x.strip()]
        results: List[Dict[str, Any]] = []
        for seg in seg_list:
            # Contiguous first
            r = run_one(server, args.blob_name, args.blob_size_mb, args.seed, args.size_mb,
                        base_units=pcpu_list[-1], seg_len=seg, stride=seg,
                        threads=args.threads, batch=args.batch,
                        hugehint=args.hugehint, numa=args.numa, numa_interleave=args.numa_interleave,
                        coalesce=args.coalesce,
                        measure_cpu=args.measure_cpu,
                        mlock_pages=args.mlock,
                        out_hugefs_dir=args.out_hugefs_dir,
                        blob_file_path=blob_file_path)
            r["mode"] = "contig"
            results.append(r)
            # Vary pCPU on contiguous
            for bu in pcpu_list:
                r = run_one(server, args.blob_name, args.blob_size_mb, args.seed, args.size_mb,
                            base_units=bu, seg_len=seg, stride=seg,
                            threads=args.threads, batch=args.batch,
                            hugehint=args.hugehint, numa=args.numa, numa_interleave=args.numa_interleave,
                            coalesce=args.coalesce,
                            measure_cpu=args.measure_cpu,
                            mlock_pages=args.mlock,
                            out_hugefs_dir=args.out_hugefs_dir,
                            blob_file_path=blob_file_path)
                r["mode"] = "contig"
                results.append(r)
            if args.include_scatter:
                stride = 8191 if seg != 65536 else 65537
                for bu in pcpu_list:
                    r = run_one(server, args.blob_name, args.blob_size_mb, args.seed, args.size_mb,
                                base_units=bu, seg_len=seg, stride=stride,
                                threads=args.threads, batch=args.batch,
                                hugehint=args.hugehint, numa=args.numa, numa_interleave=args.numa_interleave,
                                coalesce=args.coalesce,
                                measure_cpu=args.measure_cpu,
                                mlock_pages=args.mlock,
                                out_hugefs_dir=args.out_hugefs_dir,
                                blob_file_path=blob_file_path)
                    r["mode"] = "scatter"
                    results.append(r)
        # Print summary
        hdr = "mode,seg_len,pcpu,threads,batch,elapsed_s,MBps,pcpu_units_per_s,eff_ops_per_s,wire_bytes,wire_ratio"
        if args.measure_cpu:
            hdr += ",cpu_user_s,cpu_sys_s,cpu_percent,max_rss_kb,ctx_voluntary,ctx_involuntary"
        if cpu_mbps is not None:
            hdr += ",cpu_MBps,cpu_ops_per_s,ops_ratio,cpupwn_time"
        print(hdr)
        out_lines = [hdr]
        BYTES = float(1 << 20)
        for r in results:
            if not r.get("ok", False):
                continue
            eff_ops = r["mbps"] * BYTES * args.ops_per_byte
            line = f"{r['mode']},{r['seg_len']},{r['pcpu_units']},{r['threads']},{r['batch']},{r['elapsed']:.3f},{r['mbps']:.2f},{r['pcpu_units_per_s']:.0f},{eff_ops:.0f},{r.get('wire_bytes',0)},{r.get('wire_ratio',0):.6f}"
            if args.measure_cpu:
                line += f",{r.get('cpu_user_s','')},{r.get('cpu_sys_s','')},{r.get('cpu_percent','')},{r.get('max_rss_kb','')},{r.get('ctx_voluntary','')},{r.get('ctx_involuntary','')}"
            if cpu_mbps is not None:
                cpu_ops = cpu_mbps * BYTES * args.ops_per_byte
                ratio = (eff_ops / cpu_ops) if cpu_ops > 0 else 0.0
                cpupwn_time = (cpu_mbps / r['mbps']) if r['mbps'] > 0 else 0.0
                line += f",{cpu_mbps:.2f},{cpu_ops:.0f},{ratio:.3f},{cpupwn_time:.3f}"
            print(line)
            out_lines.append(line)
    finally:
        server.stop()
        if args.out:
            try:
                os.makedirs(os.path.dirname(args.out), exist_ok=True) if os.path.dirname(args.out) else None
                with open(args.out, "w") as f:
                    f.write("\n".join(out_lines) + "\n")
            except Exception as e:
                print(f"Warning: could not write out CSV to {args.out}: {e}")
        # Cleanup blob file if created
        if blob_file_path:
            try:
                os.remove(blob_file_path)
            except Exception:
                pass


if __name__ == "__main__":
    main()
