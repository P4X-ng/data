#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import os
import json

# Directly register assets via registry API

def main() -> int:
    # Ensure local package import works
    sys.path.insert(0, os.path.abspath('.'))
    try:
        from app.tools.vpcpu.registry import add_asset, Asset
    except Exception as e:
        print(f"cannot import registry: {e}", file=sys.stderr)
        return 2

    ap = argparse.ArgumentParser()
    ap.add_argument("--start-port", type=int, required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--kind", default="vm_http")
    ap.add_argument("--name-prefix", default="pfs-vm")
    ap.add_argument("--attrs", default='{"concurrency":1,"pinned":true}')
    args = ap.parse_args()

    attrs = json.loads(args.attrs)

    ok = 0
    for i in range(args.count):
        port = args.start_port + i
        name = f"{args.name_prefix}-{i:03d}"
        endpoint = f"http://{args.host}:{port}"
        try:
            aid = add_asset(Asset(name=name, kind=args.kind, endpoint=endpoint, attrs=attrs))
            ok += 1
        except Exception as e:
            print(f"failed to register {name} -> {endpoint}: {e}", file=sys.stderr)
    print(f"registered {ok}/{args.count} assets")
    return 0 if ok == args.count else 1


if __name__ == "__main__":
    raise SystemExit(main())
