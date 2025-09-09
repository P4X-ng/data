#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, socket, struct, time
from typing import List, Tuple

ETH_P_PFS = 0x1337
HDR_FMT = "<IHHQHH"   # magic, version, flags, seq, desc_count, reserved  (16 bytes)
DESC_FMT = "<QII"     # offset, len, flags (16 bytes)
MAGIC = 0x50565358


def mac_bytes(ifname: str) -> bytes:
    path = f"/sys/class/net/{ifname}/address"
    with open(path, "r", encoding="utf-8") as f:
        s = f.read().strip()
    return bytes(int(x, 16) for x in s.split(":"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Native PFS L2 TX (AF_PACKET)")
    ap.add_argument("--ifname", required=True)
    ap.add_argument("--desc-file", required=True, help="CSV: offset,len per line")
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--frames", type=int, default=0, help="Send exactly N frames; overrides duration when > 0")
    ap.add_argument("--desc-per-frame", type=int, default=1)
    ap.add_argument("--align", type=int, default=64)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    # Load descriptors
    descs: List[Tuple[int, int]] = []
    with open(args.desc_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            off_s, len_s = line.split(",")
            descs.append((int(off_s), int(len_s)))
    if not descs:
        print("No descriptors loaded", flush=True)
        return 1

    # AF_PACKET socket
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_PFS))
    s.bind((args.ifname, 0))
    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)

    # Ethernet header: broadcast dest, source from ifname
    dst = b"\xff\xff\xff\xff\xff\xff"
    src = mac_bytes(args.ifname)
    if len(src) != 6:
        # fallback
        src = b"\x00\x00\x00\x00\x00\x01"
    eth_hdr = dst + src + struct.pack("!H", ETH_P_PFS)

    seq = 0
    frames = 0
    eff_bytes = 0
    dpf = max(1, args.desc_per_frame)

    desc_idx = 0
    t0 = time.perf_counter()
    tlast = t0

    while True:
        now = time.perf_counter()
        if args.frames > 0:
            if frames >= args.frames:
                break
        else:
            if args.duration > 0 and (now - t0) >= args.duration:
                break
        # build payload
        payload = bytearray(struct.pack(HDR_FMT, MAGIC, 1, 0, seq, dpf, 0))
        seq += 1
        eff_this = 0
        for _ in range(dpf):
            if desc_idx >= len(descs):
                desc_idx = 0
            off, ln = descs[desc_idx]
            desc_idx += 1
            payload += struct.pack(DESC_FMT, off, ln, 0)
            eff_this += ln
        frame = eth_hdr + payload
        try:
            s.send(frame)
            frames += 1
            eff_bytes += eff_this
        except OSError:
            continue
        if args.verbose:
            if (now - tlast) >= 0.5:
                mb = eff_bytes / 1e6
                mbps = mb / (now - t0) if (now - t0) > 0 else 0.0
                print(f"[L2 TX] eff={mb:.1f} MB avg={mbps:.1f} MB/s frames={frames}", flush=True)
                tlast = now

    t1 = time.perf_counter()
    mb = eff_bytes / 1e6
    mbps = mb / (t1 - t0) if (t1 - t0) > 0 else 0.0
    print(f"[L2 TX DONE] eff_bytes={eff_bytes} ({mb:.1f} MB) elapsed={t1 - t0:.3f} s avg={mbps:.1f} MB/s frames={frames}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

