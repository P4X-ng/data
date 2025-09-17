#!/usr/bin/env python3
import argparse
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "logs" / "patterns" / "queue"


def enqueue(payload: dict, kind: str) -> str:
    QUEUE.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    fn = QUEUE / f"{ts}_scan_{kind}.json"
    with fn.open("w") as f:
        json.dump(payload, f)
    return str(fn)


def main() -> int:
    ap = argparse.ArgumentParser(description="Enqueue pattern scan task")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("file", help="enqueue scan-file")
    pf.add_argument("--path", required=True)
    pf.add_argument("--win", type=int, default=4096)
    pf.add_argument("--k", type=int, default=50)
    pf.add_argument("--mods", default="64,128,256,512,4096")
    pf.add_argument("--zlib", action="store_true")
    pf.add_argument("--lags", action="store_true")
    pf.add_argument("--lags-set", default="")
    pf.add_argument("--delta", action="store_true")
    pf.add_argument("--dupes", action="store_true")
    pf.add_argument("--magic", action="store_true")

    pb = sub.add_parser("blob", help="enqueue scan-blob")
    pb.add_argument("--name", default="pfs_vblob_test")
    pb.add_argument("--size-mb", type=int, default=100)
    pb.add_argument("--seed", type=int, default=1337)
    pb.add_argument("--win", type=int, default=4096)
    pb.add_argument("--k", type=int, default=50)
    pb.add_argument("--mods", default="64,128,256,512,4096")
    pb.add_argument("--keep", action="store_true")
    pb.add_argument("--zlib", action="store_true")
    pb.add_argument("--lags", action="store_true")
    pb.add_argument("--lags-set", default="")
    pb.add_argument("--delta", action="store_true")
    pb.add_argument("--dupes", action="store_true")
    pb.add_argument("--magic", action="store_true")

    args = ap.parse_args()

    if args.cmd == "file":
        payload = {
            "type": "scan-file",
            "path": args.path,
            "win": args.win,
            "k": args.k,
            "mods": args.mods,
            "zlib": bool(args.zlib),
            "lags": bool(args.lags),
            "lags_set": args.lags_set,
            "delta": bool(args.delta),
            "dupes": bool(args.dupes),
            "magic": bool(args.magic),
        }
        fn = enqueue(payload, "file")
        print(f"queued {fn}")
        return 0

    if args.cmd == "blob":
        payload = {
            "type": "scan-blob",
            "name": args.name,
            "size_mb": args.size_mb,
            "seed": args.seed,
            "win": args.win,
            "k": args.k,
            "mods": args.mods,
            "keep_snapshot": bool(args.keep),
            "zlib": bool(args.zlib),
            "lags": bool(args.lags),
            "lags_set": args.lags_set,
            "delta": bool(args.delta),
            "dupes": bool(args.dupes),
            "magic": bool(args.magic),
        }
        fn = enqueue(payload, "blob")
        print(f"queued {fn}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
