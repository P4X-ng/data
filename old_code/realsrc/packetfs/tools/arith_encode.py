#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from typing import List

try:
    # Production encoder (requires C extension packetfs._bitpack)
    from packetfs.protocol import ProtocolEncoder, SyncConfig  # type: ignore
except Exception as e:  # pragma: no cover
    ProtocolEncoder = None  # type: ignore
    SyncConfig = None  # type: ignore
    _IMPORT_ERR = e


def compute_window_hashes(data: bytes, window_size: int = 65536, digest_bytes: int = 16) -> List[bytes]:
    hashes: List[bytes] = []
    for i in range(0, len(data), window_size):
        h = hashlib.sha256(data[i : i + window_size]).digest()[:digest_bytes]
        hashes.append(h)
    return hashes


def encode_file_to_arith(path: str, window_size: int = 65536) -> dict:
    if ProtocolEncoder is None or SyncConfig is None:
        raise SystemExit(
            "packetfs ProtocolEncoder unavailable. Build C extension first: 'just build-bitpack' in the PacketFS repo (uses /home/punk/.venv)."
        )

    with open(path, "rb") as f:
        data = f.read()
    size = len(data)
    sha256 = hashlib.sha256(data).hexdigest()

    enc = ProtocolEncoder(SyncConfig(window_pow2=16, window_crc16=True))

    windows = []
    hashes = compute_window_hashes(data, window_size=window_size, digest_bytes=16)

    for idx in range(0, (size + window_size - 1) // window_size):
        start = idx * window_size
        end = min(start + window_size, size)
        chunk = data[start:end]
        out = bytearray()
        # Pack 8-bit refs exactly from bytes
        enc.pack_refs(out, 0, chunk, 8)
        sync = enc.maybe_sync()
        if sync:
            out.extend(sync)
        windows.append(
            {
                "idx": idx,
                "proto": base64.b64encode(bytes(out)).decode("ascii"),
                "hash16": hashes[idx].hex(),
                "len": end - start,
            }
        )

    plan = {
        "type": "pfs-arith",
        "version": 1,
        "file": os.path.basename(path),
        "size": size,
        "sha256": sha256,
        "window_size": window_size,
        "windows": windows,
        "done": {"sha256": sha256, "total_windows": len(windows)},
    }
    return plan


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Encode a file into PacketFS arithmetic windows (PROTO ops per window)")
    p.add_argument("input", help="Path to input file")
    p.add_argument("--out", "-o", help="Output plan path (.pfsarith.json)")
    p.add_argument("--window", type=int, default=65536, help="Window size (bytes), default 65536")
    args = p.parse_args(argv)

    inp = args.input
    if not os.path.isfile(inp):
        print(f"Input not found: {inp}", file=sys.stderr)
        return 2
    out = args.out or (inp + ".pfsarith.json")

    plan = encode_file_to_arith(inp, window_size=args.window)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(plan, f, separators=(",", ":"))
        f.write("\n")
    print(f"Wrote arithmetic plan: {out} (windows={len(plan['windows'])}, size={plan['size']})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())