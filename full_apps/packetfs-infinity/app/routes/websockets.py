from __future__ import annotations

import asyncio
import hashlib
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import os, hmac

from app.core.state import BLUEPRINTS, TRANSFER_WS_AGG, TRANSFER_WS_LOCK, WINDOW_HASHES, CURRENT_BLOB


def register_ws_handlers(app: FastAPI) -> None:
    @app.websocket("/ws/pfs-arith")
    async def ws_pfs_arith(ws: WebSocket):  # noqa: ANN001
        from app.services.pvrt_framing import parse_preface, parse_frames_concat, is_ctrl, parse_ctrl_bin

        await ws.accept()
        try:
            preface_msg = await ws.receive()
            preface_bytes = preface_msg.get("bytes") or preface_msg.get("text", "").encode()
            pre = parse_preface(preface_bytes)
            # Optional PSK gating (set PFS_WS_PSK to enforce)
            psk_env = os.environ.get("PFS_WS_PSK")
            if psk_env:
                psk_client = str(pre.get("psk", ""))
                if not hmac.compare_digest(psk_env, psk_client):
                    await ws.close()
                    return
            tid = str(pre.get("transfer_id", ""))
            ch = int(pre.get("channels", 1))
            cid = int(pre.get("channel_id", 0))

            msg = await ws.receive()
            data = msg.get("bytes") or msg.get("text", "").encode()

            try:
                frames0 = parse_frames_concat(data)
                if cid == 0 and frames0:
                    _seq0, fl0, payload0 = frames0[0]
                    if is_ctrl(fl0):
                        import json as _json

                        mfst = _json.loads(payload0.decode("utf-8"))
                        async with TRANSFER_WS_LOCK:
                            agg0 = TRANSFER_WS_AGG.get(tid)
                            if not agg0:
                                agg0 = {"channels": ch, "received": {}, "lock": asyncio.Lock()}
                                TRANSFER_WS_AGG[tid] = agg0
                            agg0["mfst"] = mfst
                        hashes = [bytes.fromhex(h) for h in mfst.get("hashes", [])]
                        total = int(mfst.get("total_windows", len(hashes)))
                        from app.services.pvrt_framing import compute_needed_from_manifest

                        obj_id_key = f"sha256:{pre.get('object','')}" if pre.get('object') else None
                        local_hashes = WINDOW_HASHES.get(obj_id_key, []) if obj_id_key else []
                        needed_idx = compute_needed_from_manifest(local_hashes, hashes) or []
                        need = {"needed": needed_idx if needed_idx else list(range(total))}
                        await ws.send(_json.dumps(need).encode("utf-8"))
                        data = b"".join(p for (_s, _f, p) in frames0[1:])
            except Exception:
                pass

            async with TRANSFER_WS_LOCK:
                agg = TRANSFER_WS_AGG.get(tid)
                if not agg:
                    agg = {"channels": ch, "received": {}, "sockets": {}, "lock": asyncio.Lock()}
                    TRANSFER_WS_AGG[tid] = agg
            lock: asyncio.Lock = agg["lock"]  # type: ignore[assignment]
            async with lock:
                rec: Dict[int, bytes] = agg["received"]  # type: ignore[assignment]
                rec[cid] = data
                # Track socket per channel so we can target acks
                sockets: Dict[int, WebSocket] = agg.get("sockets", {})  # type: ignore[assignment]
                sockets[cid] = ws
                agg["sockets"] = sockets
                # Ack policy: non-zero channels get 'ok' immediately; channel 0 waits for final 'done'
                if cid != 0:
                    try:
                        await ws.send_text("ok")
                    except Exception:
                        pass
                # When all channels have arrived, assemble and send final 'done' to channel 0
                if len(rec) == agg["channels"]:
                    ordered = b"".join(rec[i] for i in range(agg["channels"]))  # type: ignore[index]
                    frames = parse_frames_concat(ordered)
                    current_win = None
                    windows: Dict[int, bytearray] = {}
                    import json as _json
                    from app.services.pvrt_ops import extract_sections, SEC_RAW, SEC_PROTO, execute_proto_window
                    from packetfs.protocol import ProtocolDecoder, SyncConfig, crc16_ccitt  # type: ignore

                    for (_seq, fl, payload) in frames:
                        if is_ctrl(fl):
                            parsed = parse_ctrl_bin(payload)
                            if parsed:
                                t = parsed[0]
                                if t == "WIN":
                                    current_win = int(parsed[1])
                                    if current_win not in windows:
                                        windows[current_win] = bytearray()
                                elif t == "END":
                                    win_idx = int(parsed[1])
                                    h = parsed[2] or b""
                                    if win_idx >= 0 and h:
                                        import binascii

                                        have = hashlib.sha256(bytes(windows.get(win_idx, b""))).digest()[: len(h)]
                                        BLUEPRINTS[f"ack:{tid}:{win_idx}"] = {
                                            "ok": have == h,
                                            "have": binascii.hexlify(have).decode(),
                                            "want": binascii.hexlify(h).decode(),
                                        }
                                elif t == "DONE":
                                    pass
                                continue
                            try:
                                ctrl = _json.loads(payload.decode("utf-8"))
                                t = ctrl.get("type")
                                if t == "WIN":
                                    current_win = int(ctrl.get("idx", 0))
                                    if current_win not in windows:
                                        windows[current_win] = bytearray()
                                elif t == "END":
                                    win_idx = int(ctrl.get("idx", -1))
                                    h_hex = ctrl.get("h")
                                    if win_idx >= 0 and h_hex is not None:
                                        import binascii

                                        want = bytes.fromhex(h_hex)
                                        have = hashlib.sha256(bytes(windows.get(win_idx, b""))).digest()[: len(want)]
                                        BLUEPRINTS[f"ack:{tid}:{win_idx}"] = {
                                            "ok": have == want,
                                            "have": binascii.hexlify(have).decode(),
                                            "want": h_hex,
                                        }
                            except Exception:
                                continue
                        else:
                            if current_win is not None:
                                windows.setdefault(current_win, bytearray()).extend(payload)

                    for widx, buf in list(windows.items()):
                        # Prefer OFFS decoding (offset lists) or PVRT+BREF reconstruction from VirtualBlob
                        win_bytes = b""
                        try:
                            vb = CURRENT_BLOB.get("vb") if isinstance(CURRENT_BLOB, dict) else None
                            anchor = int(pre.get("anchor", 0))
                            if vb is not None and len(buf) >= 6 and bytes(buf[:4]) == b'OFFS':
                                # OFFS format: 'OFFS' + u16 count + entries(off64,len32,fl8)*
                                cnt = int.from_bytes(bytes(buf[4:6]), 'big')
                                i2 = 6
                                out = bytearray()
                                for _ in range(cnt):
                                    if i2 + 13 > len(buf):
                                        break
                                    off_b = bytes(buf[i2:i2+8]); i2 += 8
                                    ln = int.from_bytes(bytes(buf[i2:i2+4]), 'big'); i2 += 4
                                    fl = buf[i2]; i2 += 1
                                    if ln <= 0:
                                        continue
                                    if (fl & 0x01) != 0:
                                        delta = int.from_bytes(off_b, 'big', signed=True)
                                        off = (anchor + delta) % int(CURRENT_BLOB.get("size", vb.size))
                                    else:
                                        off = int.from_bytes(off_b, 'big', signed=False)
                                    seg = bytearray(vb.read(off, ln))
                                    op = (fl >> 1) & 0x03
                                    imm = (fl >> 3) & 0x1F
                                    if op == 1:
                                        for j in range(len(seg)):
                                            seg[j] ^= imm
                                    elif op == 2:
                                        for j in range(len(seg)):
                                            seg[j] = (seg[j] + imm) & 0xFF
                                    out += seg
                                win_bytes = bytes(out)
                        except Exception:
                            win_bytes = b""
                        if not win_bytes:
                            try:
                                from packetfs.filesystem.pvrt_container import parse_container, SEC_BREF  # type: ignore
                                vb = CURRENT_BLOB.get("vb") if isinstance(CURRENT_BLOB, dict) else None
                                anchor = int(pre.get("anchor", 0))
                                if vb is not None:
                                    secs = parse_container(bytes(buf))
                                    bref = secs.get(SEC_BREF)
                                    if bref:
                                        out = bytearray()
                                        if len(bref) >= 2:
                                            cnt = int.from_bytes(bref[0:2], 'big')
                                            i2 = 2
                                            for _ in range(cnt):
                                                if i2 + 13 > len(bref):
                                                    break
                                                off_b = bref[i2:i2+8]; i2 += 8
                                                ln = int.from_bytes(bref[i2:i2+4], 'big'); i2 += 4
                                                fl = bref[i2]; i2 += 1
                                                if ln <= 0:
                                                    continue
                                                if (fl & 0x01) != 0:
                                                    # relative delta (signed 64-bit)
                                                    delta = int.from_bytes(off_b, 'big', signed=True)
                                                    off = (anchor + delta) % int(CURRENT_BLOB.get("size", vb.size))
                                                else:
                                                    off = int.from_bytes(off_b, 'big', signed=False)
                                                seg = bytearray(vb.read(off, ln))
                                                # Apply imm5 transforms: bits1-2 op, bits3-7 imm
                                                op = (fl >> 1) & 0x03
                                                imm = (fl >> 3) & 0x1F
                                                if op == 1:
                                                    for j in range(len(seg)):
                                                        seg[j] ^= imm
                                                elif op == 2:
                                                    for j in range(len(seg)):
                                                        seg[j] = (seg[j] + imm) & 0xFF
                                                out += seg
                                        win_bytes = bytes(out)
                            except Exception:
                                win_bytes = b""
                        # Fallback: legacy section decode (RAW/PROTO)
                        if not win_bytes:
                            secs = extract_sections(bytes(buf))
                            raw = secs.get(SEC_RAW)
                            proto = secs.get(SEC_PROTO)
                            win_bytes = bytes(raw or b"")
                            try:
                                if proto is not None:
                                    dec = ProtocolDecoder(SyncConfig(window_pow2=16, window_crc16=True))
                                    win_crc = dec.scan_for_sync(proto)
                                    if win_crc is not None:
                                        _win, expect_crc = win_crc
                                        got_crc = crc16_ccitt(win_bytes)
                                        BLUEPRINTS[f"crc:{tid}:{widx}"] = {
                                            "expect": int(expect_crc),
                                            "got": int(got_crc),
                                            "ok": int(expect_crc) == int(got_crc),
                                        }
                            except Exception:
                                pass

                        windows[widx] = bytearray(win_bytes)

                    mfst = agg.get("mfst", {})  # type: ignore[index]
                    total = (
                        int(mfst.get("total_windows", len(windows))) if isinstance(mfst, dict) else len(windows)
                    )
                    size = int(mfst.get("size", 0)) if isinstance(mfst, dict) else 0
                    assembled = bytearray()
                    for w in range(total):
                        chunk = windows.get(w, bytearray())
                        assembled.extend(chunk)
                    if size and len(assembled) > size:
                        assembled = assembled[:size]
                    oid_sha = str(pre.get("object", ""))
                    key = f"recv:{oid_sha}" if oid_sha else f"recv:{tid}"
                    BLUEPRINTS[key] = {
                        "version": 1,
                        "size": len(assembled),
                        "sha256": hashlib.sha256(assembled).hexdigest(),
                        "windows": sorted(list(windows.keys())),
                        "bytes": bytes(assembled),
                    }
                    try:
                        for (_s, fl, pl) in frames[::-1]:
                            if is_ctrl(fl):
                                try:
                                    ctrl = _json.loads(pl.decode("utf-8"))
                                except Exception:
                                    ctrl = None
                                if isinstance(ctrl, dict) and ctrl.get("type") == "DONE":
                                    expect_sha = str(ctrl.get("sha", ""))
                                    BLUEPRINTS[f"done:{tid}"] = {
                                        "expect": expect_sha,
                                        "got": BLUEPRINTS[key]["sha256"],
                                        "ok": expect_sha == BLUEPRINTS[key]["sha256"],
                                    }
                                    break
                        # Send final done to channel 0 if available; else to this socket
                        ch0 = sockets.get(0)
                        target_ws = ch0 or ws
                        await target_ws.send_text("done")
                    except Exception:
                        # Best-effort ok to non-zero if not already sent
                        try:
                            if cid != 0:
                                await ws.send_text("ok")
                        except Exception:
                            pass
                    async with TRANSFER_WS_LOCK:
                        TRANSFER_WS_AGG.pop(tid, None)
        except WebSocketDisconnect:
            return
        except Exception:
            try:
                await ws.close()
            except Exception:
                pass

    # --- Blob bootstrap WS: server streams blob windows (RAW) to client ---
    @app.websocket("/ws/blob-bootstrap")
    async def ws_blob_bootstrap(ws: WebSocket):  # noqa: ANN001
        from app.core.state import CURRENT_BLOB
        from app.services.pvrt_framing import (
            build_ctrl_json_frame,
            build_frames_from_data,
        )
        from app.services.pvrt_ops import encode_window_ops
        import hashlib as _hash
        await ws.accept()
        try:
            # Use current attached blob
            if not isinstance(CURRENT_BLOB, dict) or not CURRENT_BLOB.get("vb"):
                await ws.send_text("error: no blob")
                await ws.close()
                return
            vb = CURRENT_BLOB.get("vb")
            size = int(CURRENT_BLOB.get("size", getattr(vb, "size", 0)))
            name = str(CURRENT_BLOB.get("name", "pfs_vblob"))
            window_size = 65536
            total_windows = (size + window_size - 1) // window_size if size > 0 else 0
            # Send manifest first (JSON ctrl)
            manifest = {
                "type": "MFST",
                "algo": "sha256-16",
                "window_size": window_size,
                "total_windows": total_windows,
                "size": size,
                "blob": name,
                "id": CURRENT_BLOB.get("id"),
                "seed": CURRENT_BLOB.get("seed"),
            }
            await ws.send(build_ctrl_json_frame("MFST", manifest))
            # Optionally receive NEED list from client (JSON)
            try:
                need_msg = await asyncio.wait_for(ws.receive_text(), timeout=3.0)
                import json as _json
                need_obj = _json.loads(need_msg) if need_msg else {}
                needed = need_obj.get("needed") if isinstance(need_obj, dict) else None
                needed_idxs = [int(x) for x in needed] if isinstance(needed, list) else list(range(total_windows))
            except Exception:
                needed_idxs = list(range(total_windows))
            # Stream windows
            for w in needed_idxs:
                start = w * window_size
                end = min(start + window_size, size)
                if start >= size:
                    continue
                await ws.send(build_ctrl_json_frame("WIN", {"idx": w}))
                win_bytes = vb.read(start, end - start)  # type: ignore[attr-defined]
                # Encode PVRT with RAW section only (encode_window_ops adds RAW always)
                ops_payload = encode_window_ops(win_bytes, bref_chunks=None)
                await ws.send(build_frames_from_data(ops_payload, window_size=65536))
                h16 = _hash.sha256(win_bytes).digest()[:16].hex()
                await ws.send(build_ctrl_json_frame("END", {"idx": w, "h": h16}))
            await ws.send(build_ctrl_json_frame("DONE", {"sha": "", "tw": total_windows, "ws": window_size}))
            # Final ack
            await ws.send_text("done")
        except Exception:
            try:
                await ws.send_text("error")
            except Exception:
                pass
            try:
                await ws.close()
            except Exception:
                pass
