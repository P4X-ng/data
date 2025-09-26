#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import socket
import time
from typing import Dict, List

try:
    import websockets  # type: ignore
except Exception as e:  # pragma: no cover
    websockets = None

MAGIC_PREFACE = b"PVRT"
MAGIC_FRAME = b"PF"
FLAG_CTRL = 0x01
FLAG_DATA = 0x00


def build_preface(transfer_id: str, channels: int, channel_id: int, blob_fingerprint: str, object_sha256: str, psk: str | None = None, flags: int = 0) -> bytes:
    import struct
    tid_b = transfer_id.encode("utf-8")
    blob_b = blob_fingerprint.encode("utf-8")
    obj_b = object_sha256.encode("utf-8")
    psk_b = (psk or "").encode("utf-8")
    hdr = [MAGIC_PREFACE, struct.pack("!BBHH", 1, flags, channels, channel_id)]
    parts = [
        b"".join(hdr),
        struct.pack("!B", len(tid_b)), tid_b,
        struct.pack("!B", len(blob_b)), blob_b,
        struct.pack("!B", len(obj_b)), obj_b,
        struct.pack("!B", len(psk_b)), psk_b,
    ]
    return b"".join(parts)


def build_frames_from_data(data: bytes, window_size: int = 1024, flags: int = FLAG_DATA, start_seq: int = 0) -> bytes:
    import struct
    out = bytearray()
    seq = start_seq
    for i in range(0, len(data), window_size):
        chunk = data[i:i+window_size]
        out += MAGIC_FRAME
        out += struct.pack("!QIB", seq, len(chunk), flags)
        out += chunk
        seq += 1
    return bytes(out)


def build_ctrl_json_frame(ctrl_type: str, obj: dict) -> bytes:
    payload = dict(obj)
    payload["type"] = ctrl_type
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return build_frames_from_data(data, window_size=len(data), flags=FLAG_CTRL)


async def send_iprog_ws(iprog: Dict, host: str, port: int) -> bool:
    if websockets is None:
        raise RuntimeError("websockets package not available. Install it and retry.")

    uri = f"ws://{host}:{port}/ws/pfs-arith"
    # Derive transfer id from sha and host
    sha = str(iprog.get("sha256", ""))
    tid = hashlib.sha256((sha + host).encode()).hexdigest()[:16]
    blob = iprog.get("blob", {})
    blob_fp = f"{blob.get('name','')}:{blob.get('size','')}:{blob.get('seed','')}"
    ws = await websockets.connect(uri, max_size=None)
    try:
        preface = build_preface(tid, channels=1, channel_id=0, blob_fingerprint=blob_fp, object_sha256=sha)
        await ws.send(preface)
        frames = bytearray()
        windows = iprog.get("windows", [])
        for w in windows:
            idx = int(w.get("idx", 0))
            frames += build_ctrl_json_frame("WIN", {"idx": idx})
            pvrt_b64 = w.get("pvrt")
            if not pvrt_b64:
                # Build PVRT from proto+bref if present
                proto_b64 = w.get("proto")
                bref = w.get("bref") or []
                if not proto_b64:
                    raise RuntimeError("iprog window missing pvrt/proto")
                from packetfs.filesystem.pvrt_container import build_container
                # Build BREF-only PVRT; omit PROTO for minimal on-wire size
                pvrt = build_container(proto=None, bref_chunks=[(int(o), int(l), int(f)) for (o,l,f) in bref])
            else:
                pvrt = base64.b64decode(pvrt_b64)
            frames += build_frames_from_data(pvrt, window_size=1024)
            frames += build_ctrl_json_frame("END", {"idx": idx, "h": w.get("hash16", "")})
        frames += build_ctrl_json_frame("DONE", {"sha": sha, "tw": len(windows), "ws": int(iprog.get("window_size", 65536))})
        await ws.send(bytes(frames))
        try:
            ack = await asyncio.wait_for(ws.recv(), timeout=10.0)
            if isinstance(ack, (bytes, bytearray)):
                try:
                    ack = ack.decode("utf-8", errors="ignore")
                except Exception:
                    ack = ""
            return isinstance(ack, str) and (ack.lower().startswith("done") or ack.lower().startswith("ok"))
        except asyncio.TimeoutError:
            return False
    finally:
        await ws.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Send an IPROG plan (.iprog.json) over WebSocket to pfs-infinity receiver")
    p.add_argument("--iprog", required=True, help="Path to .iprog.json")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8088)
    args = p.parse_args(argv)

    with open(args.iprog, "r", encoding="utf-8") as f:
        iprog = json.load(f)
    t0 = time.time()
    ok = asyncio.get_event_loop().run_until_complete(send_iprog_ws(iprog, args.host, args.port))
    dt = time.time() - t0
    metrics = iprog.get("metrics", {})
    tx_ratio = metrics.get("tx_ratio")
    pvrt_total = metrics.get("pvrt_total")
    print(f"send_iprog ok={ok} elapsed_s={dt:.3f} pvrt_total={pvrt_total} tx_ratio={tx_ratio}")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())