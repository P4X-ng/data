#!/usr/bin/env python3
import os
import socket
import sys
from .transport import Transport, send_json, recv_json, DEFAULT_PORT

def run_merge(peer: str, port: int = DEFAULT_PORT):
    t = Transport(peer, port, server=False)
    s = t.connect()
    try:
        send_json(s, {"type":"hello", "client":"pfs-merge", "pid": os.getpid()})
        resp = recv_json(s)
        root = resp.get("root", "?")
        print(f"Connected to {peer}:{port} (root={root})")
        # TODO: mount remote and union later
        return 0
    finally:
        s.close()


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: pfs-merge <peer-ip> [port]", file=sys.stderr)
        return 2
    peer = argv[0]
    port = int(argv[1]) if len(argv) > 1 else DEFAULT_PORT
    return run_merge(peer, port)

if __name__ == "__main__":
    raise SystemExit(main())
