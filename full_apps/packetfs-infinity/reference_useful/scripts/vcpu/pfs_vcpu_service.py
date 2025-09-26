#!/usr/bin/env python3
# pfs_vcpu_service.py — minimal user-space vCPU coprocessor over TCP
# - Protocol: newline-delimited JSON (NDJSON)
#   HELLO: {"type":"HELLO","vcpu_id":"...","program":[{"op":"counteq","imm":69}],"align":64}
#   SUBMIT: {"type":"SUBMIT","batch_id":"id","windows":[{"offset":0,"len":4096},...],"program":[{"op":"counteq","imm":69}],"align":64}
# - Response for SUBMIT includes metrics and R0 accumulator
# - Writes metrics JSONL to logs/pfs_vcpu_stats.jsonl with cpupwn when baseline known
#
# Real compute: reads bytes from a real blob file and applies ops; baseline is measured on-first-use.

import argparse
import json
import os
import socket
import threading
import time
from typing import List, Dict, Any, Tuple

# Supported ops
OPS = {"fnv", "xor", "add", "counteq", "crc32c"}

try:
    import zlib  # for adler/crc as a placeholder for crc32c if no hw accel
except Exception:
    zlib = None


def apply_op(buf: bytes, op: str, imm: int, acc: Dict[str, int]) -> None:
    if op == "xor":
        # mutate not needed; just touch bytes
        b = 0
        x = imm & 0xFF
        for ch in buf:
            b ^= (ch ^ x)
        acc["R0"] ^= b
    elif op == "add":
        s = 0
        x = imm & 0xFF
        for ch in buf:
            s = (s + ((ch + x) & 0xFF)) & 0xFFFFFFFF
        acc["R0"] = (acc["R0"] + s) & 0xFFFFFFFF
    elif op in ("fnv", "fnv64"):
        # 64-bit FNV-1a
        h = 1469598103934665603
        for ch in buf:
            h ^= ch
            h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
        acc["R0"] ^= h
    elif op == "counteq":
        v = imm & 0xFF
        c = 0
        for ch in buf:
            if ch == v:
                c += 1
        acc["R0"] = (acc["R0"] + c) & 0xFFFFFFFFFFFFFFFF
    elif op == "crc32c":
        # fall back to zlib.crc32 (not crc32c but real compute)
        if zlib is not None:
            acc["R0"] = zlib.crc32(buf, acc.get("R0", 0)) & 0xFFFFFFFF
        else:
            # simple rotate-xor fallback
            r = acc.get("R0", 0)
            for ch in buf:
                r = ((r << 1) | (r >> 31)) & 0xFFFFFFFF
                r ^= ch
            acc["R0"] = r
    else:
        # No-op but touch memory
        s = 0
        for ch in buf:
            s ^= ch
        acc["R0"] ^= s


class VCPUService:
    def __init__(self, host: str, port: int, blob_path: str, metrics_path: str):
        self.host = host
        self.port = port
        self.blob_path = blob_path
        self.metrics_path = metrics_path
        self.baseline_mb_s = {}  # key: approx window len (pow2 bucket) -> MB/s
        self.lock = threading.Lock()
        self.stop_evt = threading.Event()
        self.stat_total_windows = 0
        self.stat_total_bytes = 0

    def _bucket_len(self, n: int) -> int:
        # bucket lengths by powers of two (e.g., 4k, 8k, ...)
        b = 1
        while b < n:
            b <<= 1
        return b

    def _ensure_blob(self):
        if not os.path.exists(self.blob_path):
            raise FileNotFoundError(f"Blob not found: {self.blob_path}")

    def _measure_baseline(self, fd: int, windows: List[Dict[str, int]]) -> float:
        # Measure simple read+touch throughput as baseline
        start = time.perf_counter()
        total = 0
        for w in windows:
            off = int(w["offset"])  # noqa
            ln = int(w["len"])  # noqa
            data = os.pread(fd, ln, off)
            # touch bytes
            s = 0
            for ch in data:
                s ^= ch
            total += len(data)
        dt = max(1e-9, time.perf_counter() - start)
        return (total / 1e6) / dt  # MB/s

    def _compute(self, fd: int, windows: List[Dict[str, int]], program: List[Dict[str, Any]], align: int) -> Tuple[Dict[str, int], int, float]:
        acc = {"R0": 0, "R1": 0, "R2": 0, "R3": 0}
        total = 0
        t0 = time.perf_counter()
        # Apply only first op for now; extendable
        op = program[0].get("op", "counteq") if program else "counteq"
        imm = int(program[0].get("imm", 0)) if program else 0
        for w in windows:
            off = int(w["offset"])  # noqa
            ln = int(w["len"])  # noqa
            if align > 1:
                mask = align - 1
                off &= ~mask
                ln = (ln + mask) & ~mask
            data = os.pread(fd, ln, off)
            apply_op(data, op, imm, acc)
            total += len(data)
        dt = max(1e-9, time.perf_counter() - t0)
        return acc, total, dt

    def _handle_submit(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_blob()
        windows = msg.get("windows") or []
        program = msg.get("program") or []
        align = int(msg.get("align") or 64)
        batch_id = str(msg.get("batch_id") or "")
        op = program[0].get("op", "counteq") if program else "counteq"

        fd = os.open(self.blob_path, os.O_RDONLY)
        try:
            # baseline key by typical window size
            key_len = self._bucket_len(windows[0]["len"]) if windows else 4096
            base_mb = None
            with self.lock:
                base_mb = self.baseline_mb_s.get(key_len)
            if base_mb is None:
                base_mb = self._measure_baseline(fd, windows)
                with self.lock:
                    self.baseline_mb_s[key_len] = base_mb

            acc, total, dt = self._compute(fd, windows, program, align)
            mbps = (total / 1e6) / dt
            cpupwn = mbps / base_mb if base_mb > 0 else None

            # update totals
            with self.lock:
                self.stat_total_windows += len(windows)
                self.stat_total_bytes += total

            out = {
                "ok": 1,
                "batch_id": batch_id,
                "windows": len(windows),
                "bytes_eff": total,
                "dt": dt,
                "MB/s": round(mbps, 3),
                "cpu_MBps": round(base_mb, 3),
                "cpupwn": round(cpupwn, 3) if cpupwn is not None else None,
                "pcpu_op": op,
                "R0": acc["R0"],
                "R1": acc["R1"],
                "R2": acc["R2"],
                "R3": acc["R3"],
            }
            # write metrics jsonl
            try:
                os.makedirs(os.path.dirname(self.metrics_path), exist_ok=True)
                with open(self.metrics_path, "ab", buffering=0) as f:
                    f.write((json.dumps(out) + "\n").encode("utf-8"))
            except Exception:
                pass
            return out
        finally:
            os.close(fd)

    def _handle_client(self, conn: socket.socket, addr):
        f = conn.makefile("rwb")
        try:
            while not self.stop_evt.is_set():
                line = f.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode("utf-8", errors="ignore"))
                except Exception:
                    f.write(b"{}\n")
                    f.flush()
                    continue
                typ = msg.get("type")
                if typ == "HELLO":
                    f.write(b"{\"ok\":1}\n")
                    f.flush()
                elif typ == "SUBMIT":
                    out = self._handle_submit(msg)
                    f.write((json.dumps(out) + "\n").encode("utf-8"))
                    f.flush()
                else:
                    f.write(b"{\"error\":\"unknown type\"}\n")
                    f.flush()
        finally:
            try:
                f.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    def serve(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen(64)
            print(f"[vcpu-service] listening on {self.host}:{self.port} blob={self.blob_path}")
            while not self.stop_evt.is_set():
                try:
                    conn, addr = s.accept()
                except OSError:
                    break
                t = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                t.start()


def main():
    ap = argparse.ArgumentParser(description="PacketFS vCPU Service")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9855)
    ap.add_argument("--blob", default=os.environ.get("PFS_VCPU_BLOB", "/dev/shm/pfs_blob.bin"))
    ap.add_argument("--metrics", default="logs/pfs_vcpu_stats.jsonl")
    args = ap.parse_args()

    svc = VCPUService(args.host, args.port, args.blob, args.metrics)
    svc.serve()


if __name__ == "__main__":
    main()
