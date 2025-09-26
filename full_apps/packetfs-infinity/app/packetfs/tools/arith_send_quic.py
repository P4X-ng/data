#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import time
from typing import Dict

from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration

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

# Binary controls for QUIC
CTRL_BIN_WIN = 0xA1
CTRL_BIN_END = 0xA2

def build_ctrl_bin_win(idx: int) -> bytes:
    data = bytes([CTRL_BIN_WIN]) + int(idx).to_bytes(4, 'big')
    return build_frames_from_data(data, window_size=len(data), flags=FLAG_CTRL)


def build_ctrl_bin_end(idx: int, hash16: bytes | None = None) -> bytes:
    h = (hash16 or b'\x00' * 16)[:16]
    data = bytes([CTRL_BIN_END]) + int(idx).to_bytes(4, 'big') + h
    return build_frames_from_data(data, window_size=len(data), flags=FLAG_CTRL)


async def send_iprog_quic(iprog: Dict, host: str, port: int) -> bool:
    cfg = QuicConfiguration(is_client=True, alpn_protocols=["pfs-arith"], verify_mode=False)
    async with connect(host, port, configuration=cfg) as client:
        quic = client._quic  # type: ignore
        stream_id = quic.get_next_available_stream_id()
        # Preface
        sha = str(iprog.get("sha256", ""))
        tid = hashlib.sha256((sha + host).encode()).hexdigest()[:16]
        blob = iprog.get("blob", {})
        blob_fp = f"{blob.get('name','')}:{blob.get('size','')}:{blob.get('seed','')}"
        preface = build_preface(tid, channels=1, channel_id=0, blob_fingerprint=blob_fp, object_sha256=sha)
        quic.send_stream_data(stream_id, preface, end_stream=False)
        # Frames
        frames = bytearray()
        windows = iprog.get("windows", [])
        for w in windows:
            idx = int(w.get("idx", 0))
            frames += build_ctrl_bin_win(idx)
            pvrt_b64 = w.get("pvrt")
            if pvrt_b64:
                pvrt = base64.b64decode(pvrt_b64)
            else:
                # Build BREF-only PVRT if not present
                from packetfs.filesystem.pvrt_container import build_container
                bref = w.get("bref") or []
                pvrt = build_container(proto=None, bref_chunks=[(int(o), int(l), int(f)) for (o,l,f) in bref])
            frames += build_frames_from_data(pvrt, window_size=1024)
            # use binary END with hash16 if available
            hhex = w.get("hash16", "")
            h = bytes.fromhex(hhex) if isinstance(hhex, str) and len(hhex) == 32 else None
            frames += build_ctrl_bin_end(idx, h)
        frames += build_ctrl_json_frame("DONE", {"sha": sha, "tw": len(windows), "ws": int(iprog.get("window_size", 65536))})
        quic.send_stream_data(stream_id, bytes(frames), end_stream=True)
        await client._network_changed()  # type: ignore
        # Best-effort wait for ack
        try:
            await asyncio.sleep(0.2)
        except Exception:
            pass
        return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Send an IPROG plan (.iprog.json) over QUIC to receiver")
    p.add_argument("--iprog", required=True)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8533)
    args = p.parse_args(argv)
    with open(args.iprog, "r", encoding="utf-8") as f:
        iprog = json.load(f)
    t0 = time.time()
    ok = asyncio.get_event_loop().run_until_complete(send_iprog_quic(iprog, args.host, args.port))
    dt = time.time() - t0
    metrics = iprog.get("metrics", {})
    print(f"send_iprog_quic ok={ok} elapsed_s={dt:.3f} pvrt_total={metrics.get('pvrt_total')} tx_ratio={metrics.get('tx_ratio')}")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())