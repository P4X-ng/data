from __future__ import annotations

import asyncio
import hashlib
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

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
                    agg = {"channels": ch, "received": {}, "lock": asyncio.Lock()}
                    TRANSFER_WS_AGG[tid] = agg
            lock: asyncio.Lock = agg["lock"]  # type: ignore[assignment]
            async with lock:
                rec: Dict[int, bytes] = agg["received"]  # type: ignore[assignment]
                rec[cid] = data
                await ws.send_text("ok")
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
                        secs = extract_sections(bytes(buf))
                        raw = secs.get(SEC_RAW)
                        proto = secs.get(SEC_PROTO)
                        win_bytes = bytes(raw or b"")

                        try:
                            if proto is not None and CURRENT_BLOB:
                                vb_meta = {
                                    "name": CURRENT_BLOB.get("name"),
                                    "size": CURRENT_BLOB.get("size"),
                                    "seed": CURRENT_BLOB.get("seed"),
                                }
                                recon = execute_proto_window(bytes(buf), vb_meta)
                                if recon is not None and len(recon) > 0:
                                    win_bytes = recon
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
                                if CURRENT_BLOB and proto is not None:
                                    blob_meta = {k: CURRENT_BLOB.get(k) for k in ("name", "size", "seed", "id")}
                                    outb = execute_proto_window(proto, blob_meta)
                                    if outb is not None:
                                        win_bytes = bytes(outb)
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
                    }
                    try:
                        for (_s, fl, pl) in frames[::-1]:
                            if is_ctrl(fl):
                                ctrl = _json.loads(pl.decode("utf-8"))
                                if ctrl.get("type") == "DONE":
                                    expect_sha = str(ctrl.get("sha", ""))
                                    BLUEPRINTS[f"done:{tid}"] = {
                                        "expect": expect_sha,
                                        "got": BLUEPRINTS[key]["sha256"],
                                        "ok": expect_sha == BLUEPRINTS[key]["sha256"],
                                    }
                                    break
                        await ws.send_text("done")
                    except Exception:
                        try:
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
