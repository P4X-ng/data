from __future__ import annotations

import hashlib
from typing import List, Tuple
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.state import BLUEPRINTS

router = APIRouter()

TILE = 256
PALETTE_START = 32  # matches VirtualBlob header_len
PALETTE_SIZE = 256 * 1024
PALETTE_END = PALETTE_START + PALETTE_SIZE


def _build_palette_index(vb) -> dict[bytes, int]:
    """Build a mapping of 256B tile -> blob offset within palette region."""
    idx: dict[bytes, int] = {}
    off = PALETTE_START
    while off + TILE <= min(PALETTE_END, vb.size):
        b = vb.read(off, TILE)
        idx.setdefault(b, off)
        off += TILE
    return idx


def _collect_constant_tiles(idx: dict[bytes, int]) -> list[tuple[int, int]]:
    """Return list of (offset, const_val) for palette tiles that are constant bytes."""
    out: list[tuple[int, int]] = []
    for tile, off in idx.items():
        if len(tile) == TILE and tile.count(tile[:1]) == TILE:
            out.append((off, tile[0]))
    # Prefer having value 0 offset near front if present
    out.sort(key=lambda t: t[1])
    return out


def _encode_flag(op: int, imm5: int) -> int:
    """Pack op and imm into 1 byte flag.
    Layout (LSB->MSB):
      bit0: reserved (transport arithmetic relative)
      bits1-2: op (00=id, 01=xor, 10=add, 11=reserved)
      bits3-7: imm (0..31)
    """
    op2 = (op & 0x3) << 1
    imm = (imm5 & 0x1F) << 3
    return (op2 | imm) & 0xFF


def _compile_palette_bref(data: bytes, vb) -> List[Tuple[int, int, int]]:
    """Compile data into a list of (offset, length, flags) referencing the palette only.
    Order of attempts per 256B tile:
      1) Identity match in palette
      2) Transform using constant tiles with XOR imm5
      3) Transform using constant tiles with ADD imm5
    If no match, fail (no RAW fallback permitted).
    """
    idx = _build_palette_index(vb)
    const_tiles = _collect_constant_tiles(idx)
    out: List[Tuple[int, int, int]] = []
    pos = 0
    n = len(data)
    while pos < n:
        ln = min(TILE, n - pos)
        tile = data[pos:pos + ln]
        # 1) Identity (full tile or prefix for final partial tile)
        match_off = None
        if ln == TILE:
            match_off = idx.get(tile)
        else:
            for full_tile, off in idx.items():
                if full_tile.startswith(tile):
                    match_off = off
                    break
        if match_off is not None:
            out.append((int(match_off), int(ln), 0))
            pos += ln
            continue
        # 2) Constant tile with XOR imm5: choose palette constant base such that imm<=31
        #    Works if 'tile' bytes are all equal (constant segment). For partial tiles also allowed.
        if tile.count(tile[:1]) == ln and const_tiles:
            target_val = tile[0]
            chosen = None
            chosen_fl = None
            for base_off, base_val in const_tiles:
                imm = (target_val ^ base_val) & 0xFF
                if imm <= 31:
                    chosen = base_off
                    chosen_fl = _encode_flag(1, imm)  # op=1 => XOR imm5
                    break
            if chosen is None:
                # 3) Constant tile with ADD imm5
                for base_off, base_val in const_tiles:
                    imm = (target_val - base_val) & 0xFF
                    if imm <= 31:
                        chosen = base_off
                        chosen_fl = _encode_flag(2, imm)  # op=2 => ADD imm5
                        break
            if chosen is not None and chosen_fl is not None:
                out.append((int(chosen), int(ln), int(chosen_fl)))
                pos += ln
                continue
        # No match found → strict failure
        raise HTTPException(status_code=422, detail=f"Palette compilation failed at byte {pos}: no tile/transform match")
    # Coalesce adjacent segments (must keep identical flags)
    coalesced: List[Tuple[int, int, int]] = []
    for off, ln, fl in out:
        if coalesced and (coalesced[-1][0] + coalesced[-1][1] == off) and (coalesced[-1][2] == fl):
            prev_off, prev_ln, prev_fl = coalesced[-1]
            coalesced[-1] = (prev_off, prev_ln + ln, prev_fl)
        else:
            coalesced.append((off, ln, fl))
    return coalesced


@router.post("/objects/from-palette")
async def objects_from_palette(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    sha256 = hashlib.sha256(data).hexdigest()
    obj_id = f"sha256:{sha256}"

    # Attach current VirtualBlob (1 GiB expected) and compile
    try:
        from packetfs.filesystem.virtual_blob import VirtualBlob  # type: ignore
        from packetfs.filesystem.iprog import build_iprog_for_file_bytes, BlobFingerprint  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PacketFS modules unavailable: {e}")

    # Resolve server blob parameters
    try:
        from app.core.state import CURRENT_BLOB  # type: ignore
        blob_name = str(CURRENT_BLOB.get("name"))
        blob_size = int(CURRENT_BLOB.get("size"))
        blob_seed = int(CURRENT_BLOB.get("seed"))
    except Exception:
        raise HTTPException(status_code=503, detail="Server blob not initialized")

    # Build palette-only segments
    vb = VirtualBlob(name=blob_name, size_bytes=blob_size, seed=blob_seed)
    vb.create_or_attach(create=False)
    vb.ensure_filled()
    try:
        segs = _compile_palette_bref(data, vb)
    finally:
        vb.close()

    # Build IPROG with BREF-only PVRT per window (with flags); no RAW, strict only
    window_size = 65536
    size = len(data)
    import hashlib as _hash
    def _win_hash16(start:int,end:int) -> str:
        return _hash.sha256(data[start:end]).digest()[:16].hex()

    windows = []
    pvrt_total = 0
    # Split segs across windows
    seg_idx = 0
    seg_off, seg_len, seg_fl = segs[seg_idx]
    seg_used = 0
    total_windows = (size + window_size - 1) // window_size
    for w in range(total_windows):
        w_start = w * window_size
        w_end = min(w_start + window_size, size)
        need = w_end - w_start
        w_bref: list[tuple[int,int,int]] = []
        while need > 0:
            if seg_idx >= len(segs):
                raise HTTPException(status_code=500, detail="internal: insufficient segments for windows")
            remain = seg_len - seg_used
            take = remain if remain < need else need
            w_bref.append((int(seg_off + seg_used), int(take), int(seg_fl)))
            seg_used += take
            need -= take
            if seg_used >= seg_len:
                seg_idx += 1
                if seg_idx < len(segs):
                    seg_off, seg_len, seg_fl = segs[seg_idx]
                    seg_used = 0
        # PVRT container: BREF-only
        from packetfs.filesystem.pvrt_container import build_container  # type: ignore
        pvrt = build_container(proto=None, raw=None, bref_chunks=w_bref)
        pvrt_total += len(pvrt)
        windows.append({
            "idx": w,
            "bref": [(int(o), int(l), int(f)) for (o,l,f) in w_bref],
            "hash16": _win_hash16(w_start, w_end),
            "len": (w_end - w_start),
            "pvrt": __import__('base64').b64encode(pvrt).decode('ascii'),
        })

    iprog = {
        "type": "iprog",
        "version": 1,
        "file": file.filename or obj_id,
        "size": size,
        "sha256": sha256,
        "window_size": window_size,
        "blob": {"name": blob_name, "size": blob_size, "seed": blob_seed},
        "windows": windows,
        "done": {"sha256": sha256, "total_windows": len(windows)},
        "metrics": {"pvrt_total": int(pvrt_total), "tx_ratio": (pvrt_total/size) if size>0 else 1.0},
    }

    BLUEPRINTS[obj_id] = {
        "version": 1,
        "size": size,
        "sha256": sha256,
        "iprog": iprog,
        "filename": file.filename or "unknown",
    }

    return {
        "object_id": obj_id,
        "size": size,
        "sha256": sha256,
        "compressed_size": int(pvrt_total),
        "tx_ratio": (pvrt_total/size) if size>0 else 1.0,
        "policy": "palette-only",
    }
