# Minimal PVRT container helpers for PacketFS
# Matches the simple container used by app/services/pvrt_ops.py

from __future__ import annotations
from typing import Dict, Iterable, Tuple, Optional

MAGIC = b"POX1"
SEC_RAW = 0x01
SEC_PROTO = 0x02
SEC_BREF = 0x03


def build_container(*, proto: Optional[bytes] = None,
                    raw: Optional[bytes] = None,
                    bref_chunks: Optional[Iterable[Tuple[int, int, int]]] = None) -> bytes:
    sections = []
    if raw is not None and len(raw) > 0:
        sections.append((SEC_RAW, bytes(raw)))
    if proto is not None and len(proto) > 0:
        sections.append((SEC_PROTO, bytes(proto)))
    if bref_chunks:
        b = bytearray()
        chunks = list(bref_chunks)
        b += (len(chunks) & 0xFFFF).to_bytes(2, 'big')
        for off, ln, fl in chunks:
            b += int(off).to_bytes(8, 'big')
            b += int(ln).to_bytes(4, 'big')
            b += int(fl & 0xFF).to_bytes(1, 'big')
        sections.append((SEC_BREF, bytes(b)))
    # Emit
    buf = bytearray()
    buf += MAGIC
    buf.append(len(sections) & 0xFF)
    for tp, data in sections:
        buf.append(tp & 0xFF)
        buf += len(data).to_bytes(4, 'big')
        buf += data
    return bytes(buf)


def parse_container(buf: bytes) -> Dict[int, bytes]:
    out: Dict[int, bytes] = {}
    try:
        if len(buf) < 5 or buf[:4] != MAGIC:
            return out
        i = 4
        nsec = buf[i]
        i += 1
        for _ in range(nsec):
            if i + 5 > len(buf):
                break
            tp = buf[i]
            ln = int.from_bytes(buf[i+1:i+5], 'big')
            i += 5
            if i + ln > len(buf):
                break
            out[tp] = bytes(buf[i:i+ln])
            i += ln
    except Exception:
        pass
    return out
