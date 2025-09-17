from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

from packetfs.protocol import ProtocolEncoder, SyncConfig  # type: ignore


@dataclass
class BlobFingerprint:
    name: str
    size: int
    seed: int


def window_hashes(data: bytes, window_size: int = 65536, digest_bytes: int = 16) -> List[bytes]:
    hs: List[bytes] = []
    for i in range(0, len(data), window_size):
        hs.append(hashlib.sha256(data[i:i+window_size]).digest()[:digest_bytes])
    return hs


def build_iprog_for_file_bytes(data: bytes, path: str, blob: BlobFingerprint, segs: List[Tuple[int,int]], window_size: int = 65536, include_pvrt: bool = False) -> Dict:
    """
    Build IPROG JSON for 'data' where each window is mapped to a contiguous slice in 'segs'.
    If a window straddles segment boundaries (wrap), emit two BREF entries.
    PROTO is built from the window bytes via ProtocolEncoder pack_refs + maybe_sync.
    If include_pvrt=True, embed a PVRT container per window (PROTO+BREF) and compute pvrt_total/tx_ratio.
    """
    size = len(data)
    sha256 = hashlib.sha256(data).hexdigest()
    hashes = window_hashes(data, window_size=window_size, digest_bytes=16)
    enc = ProtocolEncoder(SyncConfig(window_crc16=True, window_pow2=16))
    pvrt_total = 0

    # Build a flat list of (start_off, length) per window derived from segs
    # We assume segs collectively cover the file bytes in order.
    windows = []
    pos = 0
    seg_idx = 0
    seg_off, seg_len = segs[seg_idx] if segs else (0, 0)
    seg_consumed = 0
    for w in range(0, (size + window_size - 1) // window_size):
        w_start = w * window_size
        w_end = min(w_start + window_size, size)
        need = w_end - w_start
        bref_list: List[Tuple[int,int,int]] = []
        # Consume from segs to cover this window
        while need > 0:
            if seg_idx >= len(segs):
                raise RuntimeError("insufficient segments to cover data")
            # current segment residual
            seg_rem = seg_len - seg_consumed
            take = min(seg_rem, need)
            bref_list.append((seg_off + seg_consumed, take, 0))
            seg_consumed += take
            need -= take
            if seg_consumed >= seg_len:
                seg_idx += 1
                if seg_idx < len(segs):
                    seg_off, seg_len = segs[seg_idx]
                    seg_consumed = 0
        win_bytes = data[w_start:w_end]
        out = bytearray()
        enc.pack_refs(out, 0, win_bytes, 8)
        sync = enc.maybe_sync()
        if sync:
            out.extend(sync)
        win_entry = {
            "idx": w,
            "bref": [(int(o), int(l), int(f)) for (o,l,f) in bref_list],
            "proto": base64.b64encode(bytes(out)).decode("ascii"),
            "hash16": hashes[w].hex(),
            "len": len(win_bytes),
        }
        if include_pvrt:
            from .pvrt_container import build_container
            # Emit BREF-only PVRT to minimize transmission size (receiver reconstructs from blob)
            pvrt_bytes = build_container(proto=None, bref_chunks=bref_list)
            pvrt_total += len(pvrt_bytes)
            win_entry["pvrt"] = base64.b64encode(pvrt_bytes).decode("ascii")
        windows.append(win_entry)

    metrics = {}
    if include_pvrt and size > 0:
        metrics = {"pvrt_total": int(pvrt_total), "tx_ratio": float(pvrt_total) / float(size)}
    iprog = {
        "type": "iprog",
        "version": 1,
        "file": os.path.basename(path),
        "size": size,
        "sha256": sha256,
        "window_size": window_size,
        "blob": {"name": blob.name, "size": blob.size, "seed": blob.seed},
        "windows": windows,
        "done": {"sha256": sha256, "total_windows": len(windows)},
        "metrics": metrics,
    }
    return iprog
