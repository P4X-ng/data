from __future__ import annotations

import base64
import hashlib
from typing import Dict, List, Tuple, Optional

from .virtual_blob import VirtualBlob
from .pvrt_container import parse_container, SEC_RAW, SEC_PROTO, SEC_BREF


def read_bref_from_blob(bref: bytes, vb: VirtualBlob) -> bytes:
    if len(bref) < 2:
        return b""
    cnt = int.from_bytes(bref[0:2], 'big')
    i = 2
    out = bytearray()
    for _ in range(cnt):
        if i + 13 > len(bref):
            break
        off = int.from_bytes(bref[i:i+8], 'big'); i += 8
        ln = int.from_bytes(bref[i:i+4], 'big'); i += 4
        fl = bref[i]; i += 1
        if ln > 0:
            out += vb.read(off, ln)
    return bytes(out)


def reconstruct_window_from_pvrt(pvrt_buf: bytes, vb: VirtualBlob) -> Optional[bytes]:
    secs = parse_container(pvrt_buf)
    # Prefer reconstruction from BREF
    bref = secs.get(SEC_BREF)
    if bref is not None:
        try:
            return read_bref_from_blob(bref, vb)
        except Exception:
            return None
    # Fallback to RAW section if present
    raw = secs.get(SEC_RAW)
    if raw is not None:
        return bytes(raw)
    return None


def reconstruct_window_from_iprog_entry(win: Dict, vb: VirtualBlob) -> Optional[bytes]:
    # Try 'pvrt' first if present
    pvrt_b64 = win.get("pvrt")
    if pvrt_b64:
        try:
            pvrt_buf = base64.b64decode(pvrt_b64)
            data = reconstruct_window_from_pvrt(pvrt_buf, vb)
            if data is not None:
                return data
        except Exception:
            pass
    # Try BREF list directly
    bref_list = win.get("bref") or []
    if bref_list:
        out = bytearray()
        for (off, ln, fl) in bref_list:
            out += vb.read(int(off), int(ln))
        return bytes(out)
    # Fallback: RAW cannot be present in iprog entry, return None
    return None