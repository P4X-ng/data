#!/usr/bin/env python3
"""
Memory Monster (production-grade)

- Creates a deterministic large test file (default 100MB)
- Starts a PacketFS file transfer server on loopback
- Requests the file via the PacketFS client implementation
- Verifies integrity (MD5), reports throughput and resource metrics

This is a real, non-demo harness using the production PacketFS stack under realsrc.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import socket
import tempfile
import threading
import time

# Import from real source tree when executed via Justfile using PYTHONPATH=realsrc
from packetfs.network.packetfs_file_transfer import PacketFSFileTransfer, PFS_PORT
from packetfs.filesystem.virtual_blob import VirtualBlob


def make_deterministic_file(path: str, size_bytes: int, block_size: int = 1 << 20) -> str:
    """Create a file of size_bytes with deterministic content efficiently.

    Content pattern: repeating 1MB block of incremental bytes (0..255).
    This avoids CPU-heavy randomness while remaining non-trivial.
    """
    pattern = bytes([i & 0xFF for i in range(block_size)])
    written = 0
    with open(path, "wb") as f:
        while written < size_bytes:
            remaining = size_bytes - written
            chunk = pattern if remaining >= block_size else pattern[:remaining]
            f.write(chunk)
            written += len(chunk)
    return path


def md5_file(path: str, bufsize: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def start_server_in_thread(host: str, port: int) -> tuple[PacketFSFileTransfer, threading.Thread]:
    server = PacketFSFileTransfer(host, port)

    def run():
        try:
            server.start_server()
        except Exception as e:
            # Allow the main thread to decide how to react
            print(f"Server thread error: {e}")

    th = threading.Thread(target=run, daemon=True)
    th.start()
    # Simple readiness wait: attempt to connect repeatedly within timeout
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.25):
                break
        except OSError:
            time.sleep(0.05)
    return server, th


def run_memory_monster(size_mb: int, host: str, port: int) -> int:
    # Prepare source temp file
    src_fd, src_path = tempfile.mkstemp(prefix="pfs_mm_src_", suffix=".bin")
    os.close(src_fd)
    dst_fd, dst_path = tempfile.mkstemp(prefix="pfs_mm_dst_", suffix=".bin")
    os.close(dst_fd)

    size_bytes = size_mb * (1 << 20)
    try:
        print(f"[MM] Creating deterministic source file: {size_mb} MB -> {src_path}")
        make_deterministic_file(src_path, size_bytes)
        src_md5 = md5_file(src_path)
        print(f"[MM] Source MD5: {src_md5}")

        # Start server on loopback
        print(f"[MM] Starting PacketFS server on {host}:{port}")
        server, th = start_server_in_thread(host, port)

        # Client transfer
        client = PacketFSFileTransfer()
        print(f"[MM] Requesting file -> {dst_path}")
        t0 = time.perf_counter()
        ok = client.request_file(host, src_path, dst_path)
        t1 = time.perf_counter()

        if not ok:
            print("[MM] Transfer failed")
            return 2

        # Verify
        dst_md5 = md5_file(dst_path)
        match = (dst_md5 == src_md5)
        elapsed = t1 - t0
        throughput_mb_s = size_mb / elapsed if elapsed > 0 else float("inf")

        print("[MM] Transfer complete")
        print(f"[MM] Elapsed: {elapsed:.3f} s")
        print(f"[MM] Throughput: {throughput_mb_s:.2f} MB/s")
        print(f"[MM] MD5 match: {match}")

        # Stop server and print stats
        server.stop()
        server.print_stats()

        return 0 if match else 3

    finally:
        # Cleanup temp files
        try:
            if os.path.exists(src_path):
                os.remove(src_path)
        except Exception:
            pass
        try:
            if os.path.exists(dst_path):
                os.remove(dst_path)
        except Exception:
            pass


def run_blueprint_monster(blob_name: str, blob_size_mb: int, seed: int, size_mb: int, host: str, port: int,
                          base_units: int, seg_len: int, stride: int, delta: int, use_native: bool = False, threads: int | None = None) -> int:
    # Ensure shared blob exists and is filled
    vb = VirtualBlob(name=blob_name, size_bytes=blob_size_mb * (1 << 20), seed=seed)
    vb.create_or_attach(create=True)
    vb.ensure_filled()
    try:
        vb.close()
    except Exception:
        pass

    # Compose a formula blueprint
    file_size = size_mb * (1 << 20)
    count = max(1, min(base_units, (file_size + seg_len - 1) // seg_len))
    blueprint = {
        "mode": "formula",
        "blob": {"name": blob_name, "size": blob_size_mb * (1 << 20), "seed": seed},
        "segments": {
            "count": count,
            "seg_len": seg_len,
            "start_offset": 0,
            "stride": stride,
            "delta": delta,
        },
        "file_size": file_size,
    }

    # Start server
    server, th = start_server_in_thread(host, port)

    # Client request
    client = PacketFSFileTransfer()
    dst_fd, dst_path = tempfile.mkstemp(prefix="pfs_mm_bp_", suffix=".bin")
    os.close(dst_fd)

    t0 = time.perf_counter()
    ok = client.request_blueprint(host, blueprint, dst_path if not use_native else dst_path + ".placeholder")
    if not ok:
        print("[MM] Blueprint transfer failed (ack)")
        server.stop()
        try:
            os.remove(dst_path)
        except Exception:
            pass
        return 2

    # If native path, call native reconstructor now
    if use_native:
        import shutil
        import subprocess
        # Remove placeholder and reconstruct into dst_path
        try:
            if os.path.exists(dst_path):
                os.remove(dst_path)
        except Exception:
            pass
        out_path = dst_path
        bin_path = os.path.abspath("bin/blueprint_reconstruct")
        if not os.path.exists(bin_path):
            alt_path = os.path.abspath("dev/wip/native/blueprint_reconstruct")
            if os.path.exists(alt_path):
                bin_path = alt_path
            else:
                print("[MM] Native reconstructor not found: bin/blueprint_reconstruct or dev/wip/native/blueprint_reconstruct")
                server.stop()
                return 3
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
        ]
        if threads and threads > 0:
            args += ["--threads", str(threads)]
        # Optional native tuning flags
        if getattr(args_ns, "native_batch", 0):
            args += ["--batch", str(getattr(args_ns, "native_batch"))]
        if getattr(args_ns, "native_hugehint", False):
            args += ["--hugehint", "1"]
        if getattr(args_ns, "native_no_affinity", False):
            args += ["--affinity", "0"]
        if getattr(args_ns, "native_no_madvise", False):
            args += ["--madvise", "0"]
        # Reconstruct natively
        rc = subprocess.run(args, check=False)
        if rc.returncode != 0:
            print(f"[MM] Native reconstructor failed with code {rc.returncode}")
            server.stop()
            return 4
        t1 = time.perf_counter()
    else:
        t1 = time.perf_counter()

    # Verify
    md5 = md5_file(dst_path)
    elapsed = t1 - t0
    throughput_mb_s = (size_mb / elapsed) if elapsed > 0 else float("inf")
    print(f"[MM] Blueprint reconstruct elapsed: {elapsed:.3f} s")
    print(f"[MM] Blueprint reconstruct throughput: {throughput_mb_s:.2f} MB/s")
    print(f"[MM] Output MD5: {md5}")

    server.stop()
    server.print_stats()

    # Cleanup
    try:
        os.remove(dst_path)
    except Exception:
        pass
    return 0


def main():
    ap = argparse.ArgumentParser(description="Memory Monster (PacketFS loopback stress)")
    ap.add_argument("--size-mb", type=int, default=100, help="Size of test file in MB (default: 100)")
    ap.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=PFS_PORT, help=f"Server port (default: {PFS_PORT})")
    ap.add_argument("--blueprint", action="store_true", help="Use blueprint-only transfer via shared VirtualBlob")
    ap.add_argument("--blob-name", default="pfs_vblob_test", help="VirtualBlob name")
    ap.add_argument("--blob-size-mb", type=int, default=100, help="VirtualBlob size in MB (default: 100)")
    ap.add_argument("--seed", type=int, default=1337, help="VirtualBlob seed")
    ap.add_argument("--base-units", type=int, default=262144, help="Number of segments (conceptual pCPU units)")
    ap.add_argument("--seg-len", type=int, default=384, help="Bytes per segment (default: 384 => ~96MiB for 262k)")
    ap.add_argument("--stride", type=int, default=8191, help="Stride in bytes across blob (prime recommended)")
    ap.add_argument("--delta", type=int, default=0, help="Additive delta per byte (0..255)")
    ap.add_argument("--native", action="store_true", help="Use native blueprint reconstructor")
    ap.add_argument("--threads", type=int, default=0, help="Threads for native reconstructor (0=auto)")
    ap.add_argument("--native-batch", type=int, default=0, help="Native reconstructor batch size (segments per inner loop)")
    ap.add_argument("--native-hugehint", action="store_true", help="Hint huge pages to native reconstructor")
    ap.add_argument("--native-no-affinity", action="store_true", help="Disable CPU affinity pinning in native reconstructor")
    ap.add_argument("--native-no-madvise", action="store_true", help="Disable madvise hints in native reconstructor")
    args = ap.parse_args()

    if args.blueprint:
        # pass argparse namespace to allow native flag passthrough
        global args_ns
        args_ns = args
        rc = run_blueprint_monster(
            blob_name=args.blob_name,
            blob_size_mb=args.blob_size_mb,
            seed=args.seed,
            size_mb=args.size_mb,
            host=args.host,
            port=args.port,
            base_units=args.base_units,
            seg_len=args.seg_len,
            stride=args.stride,
            delta=args.delta,
            use_native=args.native,
            threads=(args.threads if args.threads > 0 else None),
        )
    else:
        rc = run_memory_monster(args.size_mb, args.host, args.port)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
