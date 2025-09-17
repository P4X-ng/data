#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, socket, struct, time, mmap
from typing import Tuple

ETH_P_PFS = 0x1337
HDR_FMT = "<IHHQHH"   # magic, version, flags, seq, desc_count, reserved  (16 bytes)
DESC_FMT = "<QII"     # offset, len, flags (16 bytes)
HDR_SIZE = struct.calcsize(HDR_FMT)
DESC_SIZE = struct.calcsize(DESC_FMT)
MAGIC = 0x50565358  # 'PFSX'

FNV_OFF = 0xCBF29CE484222325
FNV_PRM = 0x100000001B3

def fnv1a64(h: int, b: bytes) -> int:
    for x in b:
        h ^= x
        h = (h * FNV_PRM) & 0xFFFFFFFFFFFFFFFF
    return h


def open_blob(huge_dir: str, blob_name: str, size: int):
    path = os.path.join(huge_dir, blob_name)
    fd = os.open(path, os.O_RDWR)
    mm = mmap.mmap(fd, size, mmap.MAP_SHARED, mmap.PROT_READ)
    return fd, mm


def main() -> int:
    ap = argparse.ArgumentParser(description="Native PFS L2 RX (AF_PACKET)")
    ap.add_argument("--ifname", required=True)
    ap.add_argument("--huge-dir", default="/mnt/huge1G")
    ap.add_argument("--blob-name", default="pfs_stream_blob")
    ap.add_argument("--blob-size", type=int, required=True)
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print(f"[L2 RX] if={args.ifname} blob={args.blob_size} dir={args.huge_dir} name={args.blob_name}")

    fd, blob = open_blob(args.huge_dir, args.blob_name, args.blob_size)
    try:
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_PFS))
        s.bind((args.ifname, 0))
        s.settimeout(0.2)

        eff_bytes = 0
        frames = 0
        csum = FNV_OFF
        t0 = time.perf_counter()
        tlast = t0
        while True:
            now = time.perf_counter()
            if args.duration > 0 and (now - t0) >= args.duration:
                break
            try:
                data = s.recv(4096)
            except socket.timeout:
                continue
            if len(data) < 14 + HDR_SIZE:
                continue
            payload = data[14:]
            magic, ver, flags, seq, desc_cnt, rsv = struct.unpack_from(HDR_FMT, payload, 0)
            if magic != MAGIC or ver != 1:
                continue
            need = HDR_SIZE + desc_cnt * DESC_SIZE
            if len(payload) < need:
                continue
            off = HDR_SIZE
            for _ in range(desc_cnt):
                offset, ln, fl = struct.unpack_from(DESC_FMT, payload, off)
                off += DESC_SIZE
                if offset + ln <= args.blob_size:
                    view = memoryview(blob)[offset:offset+ln]
                    csum = fnv1a64(csum, view)
                    eff_bytes += ln
            frames += 1
            if args.verbose:
                tn = time.perf_counter()
                if (tn - tlast) >= 0.5:
                    mb = eff_bytes / 1e6
                    mbps = mb / (tn - t0) if (tn - t0) > 0 else 0.0
                    print(f"[L2 RX] eff={mb:.1f} MB avg={mbps:.1f} MB/s frames={frames}")
                    tlast = tn
        t1 = time.perf_counter()
        mb = eff_bytes / 1e6
        mbps = mb / (t1 - t0) if (t1 - t0) > 0 else 0.0
        print(f"[L2 RX DONE] eff_bytes={eff_bytes} ({mb:.1f} MB) elapsed={t1 - t0:.3f} s avg={mbps:.1f} MB/s frames={frames} checksum=0x{csum:016x}")
        return 0
    finally:
        try:
            blob.close()
        except Exception:
            pass
        os.close(fd)

if __name__ == "__main__":
    raise SystemExit(main())

