from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from app.services.pvrt_framing import parse_preface, parse_frames_concat, is_ctrl
from app.services.pvrt_ops import extract_sections, SEC_RAW, SEC_PROTO
from app.core.state import BLUEPRINTS, CURRENT_BLOB
import hashlib

router = APIRouter()

@router.post("/arith/offsets")
async def arith_offsets(request: Request):
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty body")
    try:
        pre = parse_preface(body)
    except Exception:
        raise HTTPException(status_code=400, detail="bad preface")
    # Find frames region by scanning for 'PF' magic
    off = 0
    while off + 2 <= len(body) and body[off:off+2] != b'PF':
        off += 1
    frames = parse_frames_concat(body[off:])
    windows = {}
    current_win = None
    for (_seq, fl, payload) in frames:
        if is_ctrl(fl):
            try:
                import json as _json
                ctrl = _json.loads(payload.decode('utf-8'))
                t = ctrl.get('type')
                if t == 'WIN':
                    current_win = int(ctrl.get('idx', 0))
                    if current_win not in windows:
                        windows[current_win] = bytearray()
                elif t == 'END':
                    pass
                elif t == 'DONE':
                    pass
            except Exception:
                continue
        else:
            if current_win is not None:
                windows.setdefault(current_win, bytearray()).extend(payload)
    # Reconstruct each window from PVRT BREF if present; else raw
    out_windows = {}
    try:
        from packetfs.filesystem.pvrt_container import parse_container, SEC_BREF  # type: ignore
        vb = CURRENT_BLOB.get('vb') if isinstance(CURRENT_BLOB, dict) else None
        anchor = int(pre.get('anchor', 0))
        for widx, buf in windows.items():
            win_bytes = b''
            if vb is not None:
                try:
                    secs = parse_container(bytes(buf))
                    bref = secs.get(SEC_BREF)
                    if bref:
                        acc = bytearray()
                        if len(bref) >= 2:
                            cnt = int.from_bytes(bref[0:2], 'big'); i2 = 2
                            for _ in range(cnt):
                                if i2 + 13 > len(bref): break
                                off_b = bref[i2:i2+8]; i2 += 8
                                ln = int.from_bytes(bref[i2:i2+4], 'big'); i2 += 4
                                fl = bref[i2]; i2 += 1
                                if ln <= 0: continue
                                if (fl & 0x01) != 0:
                                    delta = int.from_bytes(off_b, 'big', signed=True)
                                    o = (anchor + delta) % int(CURRENT_BLOB.get('size', getattr(vb,'size',0)))
                                else:
                                    o = int.from_bytes(off_b, 'big', signed=False)
                                acc += vb.read(o, ln)
                        win_bytes = bytes(acc)
                except Exception:
                    win_bytes = b''
            if not win_bytes:
                secs = extract_sections(bytes(buf))
                win_bytes = bytes(secs.get(SEC_RAW) or b'')
            out_windows[widx] = win_bytes
    except Exception:
        for widx, buf in windows.items():
            secs = extract_sections(bytes(buf))
            out_windows[widx] = bytes(secs.get(SEC_RAW) or b'')
    # Assemble
    total = len(out_windows)
    assembled = bytearray()
    for i in range(total):
        assembled.extend(out_windows.get(i, b''))
    sha = str(pre.get('object',''))
    key = f"recv:{sha}" if sha else "recv:offsets"
    BLUEPRINTS[key] = {
        'version': 1,
        'size': len(assembled),
        'sha256': hashlib.sha256(assembled).hexdigest(),
        'windows': sorted(list(out_windows.keys())),
        'bytes': bytes(assembled),
    }
    return {'ok': True}