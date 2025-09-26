#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx


def main() -> int:
    p = argparse.ArgumentParser(description="GPU bench via /gpu/compute or /gpu/program")
    p.add_argument("--endpoint", default="http://127.0.0.1:8811", help="Base URL of pfs-infinity app")
    p.add_argument("--path", required=True, help="Path to local file or file:// URL")
    p.add_argument("--mode", default="compute", choices=["compute", "program"], help="use /gpu/compute or /gpu/program")
    p.add_argument("--program", default="", help="JSON program example: [{op:xor, imm:255}, {op:counteq, imm:0}]")
    p.add_argument("--imm", default=0, type=int, help="Byte value to count (0-255)")
    p.add_argument("--offset", default=None, type=int)
    p.add_argument("--length", default=None, type=int)
    args = p.parse_args()

    url = f"{args.endpoint.rstrip('/')}/gpu/compute" if args.mode == "compute" else f"{args.endpoint.rstrip('/')}/gpu/program"

    data_url = args.path
    if not (data_url.startswith("http://") or data_url.startswith("https://") or data_url.startswith("file://")):
        # Treat as local path
        data_url = f"file://{os.path.abspath(args.path)}"

    if args.mode == "compute":
        payload = {
            "data_url": data_url,
            "op": "counteq",
            "imm": int(args.imm),
        }
    else:
        import json as _json

        program = _json.loads(args.program) if args.program else [{"op": "counteq", "imm": int(args.imm)}]
        payload = {
            "data_url": data_url,
            "program": program,
        }
    if args.offset is not None:
        payload["offset"] = int(args.offset)
    if args.length is not None:
        payload["length"] = int(args.length)

    t0 = time.time()
    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, json=payload)
        if r.status_code != 200:
            print(f"error: {r.status_code} {r.text}", file=sys.stderr)
            return 2
        res = r.json()
    elapsed = time.time() - t0

    print(json.dumps(res, indent=2))
    print(f"elapsed_s_total={elapsed:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
