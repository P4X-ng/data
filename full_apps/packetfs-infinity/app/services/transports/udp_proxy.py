from __future__ import annotations
import asyncio
import os
import struct
from typing import Dict

from app.services.pvrt_framing import build_ctrl_json_frame  # not used but reserved

MAGIC = b"PVU1"
T_PREFACE = 0x01
T_WIN = 0x10
T_PVRT = 0x11
T_END = 0x12
T_DONE = 0x13
T_ACK = 0xE0


def _pack_preface(transfer_id: str, blob_fp: str, sha: str, anchor: int, window_size: int, total_windows: int) -> bytes:
    tid_b = transfer_id.encode("utf-8")
    bfp_b = blob_fp.encode("utf-8")
    sha_b = sha.encode("utf-8")
    return b"".join([
        MAGIC,
        bytes([T_PREFACE & 0xFF]),
        bytes([len(tid_b) & 0xFF]), tid_b,
        bytes([len(bfp_b) & 0xFF]), bfp_b,
        bytes([len(sha_b) & 0xFF]), sha_b,
        anchor.to_bytes(8, 'big', signed=False),
        window_size.to_bytes(4, 'big'),
        total_windows.to_bytes(4, 'big'),
    ])


def _pack_win(idx: int) -> bytes:
    return b"".join([MAGIC, bytes([T_WIN & 0xFF]), int(idx).to_bytes(4, 'big')])


def _pack_pvrt(idx: int, pvrt: bytes) -> bytes:
    return b"".join([MAGIC, bytes([T_PVRT & 0xFF]), int(idx).to_bytes(4, 'big'), pvrt])


def _pack_end(idx: int, hash16: bytes) -> bytes:
    h = (hash16 or b"\x00" * 16)[:16]
    return b"".join([MAGIC, bytes([T_END & 0xFF]), int(idx).to_bytes(4, 'big'), h])


def _pack_done(sha: str, total_windows: int, window_size: int) -> bytes:
    sha_b = sha.encode("utf-8")
    return b"".join([
        MAGIC, bytes([T_DONE & 0xFF]),
        bytes([len(sha_b) & 0xFF]), sha_b,
        total_windows.to_bytes(4, 'big'),
        window_size.to_bytes(4, 'big'),
    ])


async def send_iprog_udp(host: str, port: int, iprog: Dict, transfer_id: str, timeout_s: float = 3.0) -> bool:
    """Send only PVRT BREF (offsets) per window over plain UDP datagrams.
    Server reconstructs from the current blob. Small and firewall-friendly.
    """
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(lambda: asyncio.DatagramProtocol(), remote_addr=(host, port))
    try:
        blob = iprog.get("blob", {}) if isinstance(iprog, dict) else {}
        blob_name = blob.get('name','')
        blob_size = int(blob.get('size','0') or 0)
        blob_seed = int(blob.get('seed','0') or 0)
        blob_fp = f"{blob_name}:{blob_size}:{blob_seed}"
        sha = str(iprog.get("sha256", ""))
        window_size = int(iprog.get("window_size", 65536))
        windows = iprog.get("windows", [])
        anchor = blob_size // 2 if blob_size > 0 else 0
        # Preface
        transport.sendto(_pack_preface(transfer_id, blob_fp, sha, anchor, window_size, len(windows)))
        # Windows
        from packetfs.filesystem.pvrt_container import build_container  # type: ignore
        for w in windows:
            idx = int(w.get("idx", 0))
            bref = w.get("bref") or []
            if not bref:
                continue
            # Always relative bref for arithmetic
            rel_chunks = []
            for (o,l,f) in bref:
                delta = int(o) - anchor
                rel_chunks.append((int(delta) & ((1<<64)-1), int(l), int(f) | 0x01))
            pvrt = build_container(proto=None, bref_chunks=rel_chunks)
            transport.sendto(_pack_win(idx))
            transport.sendto(_pack_pvrt(idx, pvrt))
            try:
                h16 = bytes.fromhex(w.get("hash16", "")) if w.get("hash16") else b"\x00"*16
            except Exception:
                h16 = b"\x00"*16
            transport.sendto(_pack_end(idx, h16))
        # Done
        transport.sendto(_pack_done(sha, len(windows), window_size))
        # Wait for ack
        fut = loop.create_future()
        class AckProto(asyncio.DatagramProtocol):
            def datagram_received(self, data: bytes, addr):  # type: ignore[override]
                if data.startswith(MAGIC) and len(data) >= 6 and data[4] == T_ACK:
                    fut.set_result(True)
        # Switch to a receiving protocol
        transport.close()
        transport2, proto = await loop.create_datagram_endpoint(lambda: AckProto(), local_addr=("0.0.0.0", 0))
        try:
            # Re-send DONE from new port to prompt ack back to this socket
            transport2.sendto(_pack_done(sha, len(windows), window_size), (host, port))
            try:
                await asyncio.wait_for(fut, timeout=timeout_s)
                return True
            except asyncio.TimeoutError:
                return False
        finally:
            transport2.close()
    finally:
        try:
            transport.close()
        except Exception:
            pass