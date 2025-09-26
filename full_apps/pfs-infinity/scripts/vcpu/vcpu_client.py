#!/usr/bin/env python3
# vcpu_client.py — minimal client to talk to pfs_vcpu_service

import argparse
import json
import socket
import sys
import time


def send(sock, obj):
    data = (json.dumps(obj) + "\n").encode("utf-8")
    sock.sendall(data)


def recv(sock):
    buf = b""
    while True:
        ch = sock.recv(1)
        if not ch:
            return None
        buf += ch
        if ch == b"\n":
            try:
                return json.loads(buf.decode("utf-8", errors="ignore"))
            except Exception:
                return {}


def main():
    ap = argparse.ArgumentParser(description="vcpu client")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9855)
    ap.add_argument("--blob-bytes", type=int, default=1<<20, help="total bytes across windows (default 1MiB)")
    ap.add_argument("--win", type=int, default=4096, help="window size")
    ap.add_argument("--op", default="counteq")
    ap.add_argument("--imm", type=int, default=0)
    ap.add_argument("--align", type=int, default=64)
    args = ap.parse_args()

    windows = []
    total = 0
    off = 0
    while total < args.blob_bytes:
        windows.append({"offset": off, "len": args.win})
        off += args.win
        total += args.win

    program = [{"op": args.op, "imm": args.imm}]

    s = socket.create_connection((args.host, args.port))
    send(s, {"type": "HELLO", "vcpu_id": "dev", "program": program, "align": args.align})
    _ = recv(s)

    send(s, {"type": "SUBMIT", "batch_id": "test1", "windows": windows, "program": program, "align": args.align})
    out = recv(s)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
