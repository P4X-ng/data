"""BREF (Blob Reference) parsing & window reconstruction utilities.

This module centralizes logic previously embedded inside the QUIC protocol
handler so it can be unit-tested and re-used by other transports.

A BREF section encodes a sequence of (offset,length,flags) tuples.
Flags bit 0 (0x01): interpret 8-byte offset field as a *signed delta* from a provided
anchor (typically mid-point of the blob) enabling smaller absolute values after
varint / future compression layers. Currently full 8 bytes are used for simplicity.

Fallback path: if BREF parsing fails or vb (VirtualBlob) is unavailable, callers may
attempt RAW / PROTO reconstruction separately.
"""
from __future__ import annotations

from typing import Tuple, Optional


class BrefEntry(Tuple[int, int, int]):
    """(offset_or_delta, length, flags) container placeholder"""
    pass


BREF_FLAG_REL = 0x01  # relative (delta from anchor)


class BrefError(Exception):
    pass


def parse_bref_section(data: bytes) -> list[Tuple[int, int, int]]:
    """Parse a BREF binary section into a list of (off_or_delta, length, flags).

    Format:
        count: u16
        repeated count times:
            off: u64 (signed if flags & REL else unsigned)
            len: u32
            flags: u8
    """
    if len(data) < 2:
        raise BrefError("bref too short for count")
    count = int.from_bytes(data[0:2], 'big')
    pos = 2
    out: list[Tuple[int, int, int]] = []
    for _ in range(count):
        if pos + 8 + 4 + 1 > len(data):
            raise BrefError("bref truncated entry")
        off_bytes = data[pos:pos+8]
        pos += 8
        ln = int.from_bytes(data[pos:pos+4], 'big')
        pos += 4
        fl = data[pos]
        pos += 1
        if (fl & BREF_FLAG_REL) != 0:
            # interpret signed
            off = int.from_bytes(off_bytes, 'big', signed=True)
        else:
            off = int.from_bytes(off_bytes, 'big', signed=False)
        out.append((off, ln, fl))
    return out


def reconstruct_window_from_bref(
    vb,  # VirtualBlob like object: must expose read(offset, length) -> bytes
    bref_data: bytes,
    anchor: int,
    blob_size: Optional[int] = None,
) -> bytes:
    """Rebuild a window's bytes from its BREF section.

    Parameters
    ----------
    vb: object
        VirtualBlob instance (must support read(off, ln)).
    bref_data: bytes
        Encoded BREF section.
    anchor: int
        Anchor absolute offset used for relative entries.
    blob_size: Optional[int]
        Size of blob for wrap/clamp; if None tries vb.size.
    """
    try:
        entries = parse_bref_section(bref_data)
    except Exception as e:  # noqa: BLE001
        raise BrefError(f"parse failed: {e}") from e
    out = bytearray()
    size = blob_size or getattr(vb, 'size', None) or 0
    for off_or_delta, ln, fl in entries:
        if ln <= 0:
            continue
        if (fl & BREF_FLAG_REL) != 0:
            abs_off = (anchor + off_or_delta) % size if size else (anchor + off_or_delta)
        else:
            abs_off = off_or_delta
        try:
            chunk = vb.read(abs_off, ln)
        except Exception as e:  # noqa: BLE001
            raise BrefError(f"vb.read failed at {abs_off}:{ln}: {e}") from e
        if len(chunk) != ln:
            raise BrefError("short read from blob")
        out += chunk
    return bytes(out)


__all__ = [
    'parse_bref_section',
    'reconstruct_window_from_bref',
    'BrefError',
    'BREF_FLAG_REL',
]
