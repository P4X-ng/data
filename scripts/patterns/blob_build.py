#!/usr/bin/env python3
import argparse
import json
import os
import time
from pathlib import Path

# Ensure realsrc on path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "realsrc"))

from packetfs.filesystem.virtual_blob import VirtualBlob  # type: ignore


def main() -> int:
    ap = argparse.ArgumentParser(description="Build (ensure) a VirtualBlob profile and optional snapshot")
    ap.add_argument("--name", default="pfs_vblob_test")
    ap.add_argument("--size-mb", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--profile", default="orchard")
    ap.add_argument("--snapshot", default="")
    args = ap.parse_args()

    vb = VirtualBlob(name=args.name, size_bytes=args.size_mb * (1 << 20), seed=args.seed, profile=args.profile)

    vb.create_or_attach(create=True)
    vb.ensure_filled()

    out_dir = ROOT / "logs" / "patterns" / time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": args.name,
        "size_bytes": args.size_mb * (1 << 20),
        "seed": args.seed,
        "profile": args.profile,
        "out_dir": str(out_dir),
    }
    (out_dir / "blob_manifest.json").write_text(json.dumps(manifest, indent=2))

    if args.snapshot:
        snap_path = out_dir / Path(args.snapshot).name
        # write snapshot
        with snap_path.open("wb") as f:
            remaining = args.size_mb * (1 << 20)
            ofs = 0
            chunk = 8 << 20
            while remaining > 0:
                n = min(chunk, remaining)
                f.write(vb.read(ofs, n))
                ofs += n
                remaining -= n
        print(f"snapshot: {snap_path}")
    else:
        print(f"blob_ready: {out_dir}/blob_manifest.json")

    try:
        vb.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
