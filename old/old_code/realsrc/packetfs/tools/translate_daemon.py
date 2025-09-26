#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Optional

from packetfs.filesystem.virtual_blob import VirtualBlob  # type: ignore
from packetfs.filesystem.blob_fs import BlobFS, BlobConfig
from packetfs.filesystem.iprog import build_iprog_for_file_bytes, BlobFingerprint


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def process_one(fs: BlobFS, fp: BlobFingerprint, path: str, out_dir: str, window_size: int = 65536, remove_src: bool = False) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            data = f.read()
        obj_sha = hashlib.sha256(data).hexdigest()
        object_id = f"sha256:{obj_sha}"
        segs = fs.write_bytes(data)
        fs.record_object(object_id, len(data), obj_sha, window_size, segs)
        iprog = build_iprog_for_file_bytes(data, path, fp, segs, window_size=window_size)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, os.path.basename(path) + ".iprog.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(iprog, f, separators=(",", ":"))
            f.write("\n")
        if remove_src:
            try:
                os.remove(path)
            except Exception:
                pass
        return out_path
    except Exception as e:
        print(f"[ERR] failed to process {path}: {e}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PacketFS translation daemon: watch a directory, ingest files into the blob, emit IPROG blueprints")
    p.add_argument("--watch-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--blob-name", required=True)
    p.add_argument("--blob-size", type=int, default=1<<30)
    p.add_argument("--blob-seed", type=int, default=1337)
    p.add_argument("--meta-dir", default="./pfsmeta")
    p.add_argument("--window", type=int, default=65536)
    p.add_argument("--interval", type=float, default=0.5)
    p.add_argument("--remove-src", action="store_true")
    args = p.parse_args(argv)

    cfg = BlobConfig(name=args.blob_name, size_bytes=int(args.blob_size), seed=int(args.blob_seed), meta_dir=args.meta_dir)
    fs = BlobFS(cfg)
    fp = BlobFingerprint(name=cfg.name, size=cfg.size_bytes, seed=cfg.seed)

    print(f"[pfs-translate] watching {args.watch_dir} -> {args.out_dir} (blob={cfg.name} size={cfg.size_bytes} seed={cfg.seed})")

    seen: set[str] = set()
    try:
        while True:
            try:
                for entry in os.scandir(args.watch_dir):
                    if not entry.is_file():
                        continue
                    # skip temporary/partial
                    if entry.name.endswith(".part") or entry.name.endswith(".tmp"):
                        continue
                    path = entry.path
                    if path in seen:
                        continue
                    # basic stability check: mtime older than interval
                    stat = entry.stat()
                    if (time.time() - stat.st_mtime) < args.interval:
                        continue
                    outp = process_one(fs, fp, path, args.out_dir, window_size=args.window, remove_src=args.remove_src)
                    if outp:
                        print(f"[pfs-translate] {path} -> {outp}")
                        seen.add(path)
            except Exception as e:
                print(f"[loop-err] {e}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        fs.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())