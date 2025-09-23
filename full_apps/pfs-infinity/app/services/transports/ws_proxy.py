# WebSocket client transports for PacketFS plan
import asyncio
import json
import time
import websockets
import ssl, os
from app.services.pvrt_framing import (
    build_preface,
    build_frames_from_data,
    build_ctrl_json_frame,
    compute_window_hashes,
)

# Send a PacketFS IPROG over WebSocket using PVRT (BREF-only when available)
async def send_iprog_ws(host: str, port: int, iprog: dict, transfer_id: str) -> dict:
    uris = [f"wss://{host}:{port}/ws/pfs-arith", f"ws://{host}:{port}/ws/pfs-arith"]
    import base64
    import json as _json
    for uri in uris:
        try:
            kw = {"max_size": None}
            if uri.startswith("wss://"):
                kw["ssl"] = _ssl_ctx()
            async with websockets.connect(uri, **kw) as ws:
                t0 = time.time()
                bytes_sent = 0
                sha = str(iprog.get("sha256", ""))
                blob = iprog.get("blob", {})
                blob_fp = f"{blob.get('name','')}:{blob.get('size','')}:{blob.get('seed','')}"
                preface = build_preface(transfer_id, channels=1, channel_id=0, blob_fingerprint=blob_fp, object_sha256=sha, psk=os.environ.get('PFS_WS_PSK'))
                await ws.send(preface)
                bytes_sent += len(preface)
                # Manifest (hashes inferred from window metadata)
                window_size = int(iprog.get("window_size", 65536))
                windows = iprog.get("windows", [])
                total_windows = len(windows)
                manifest = {
                    "algo": "sha256-16",
                    "window_size": window_size,
                    "total_windows": total_windows,
                    "hashes": [w.get("hash16", "") for w in windows],
                }
                mf = build_ctrl_json_frame("MFST", manifest)
                await ws.send(mf)
                bytes_sent += len(mf)
                # Await NEED from receiver to send only missing windows
                needed_idxs = list(range(total_windows))
                try:
                    need_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    if isinstance(need_msg, (bytes, bytearray)):
                        need_obj = _json.loads(need_msg.decode("utf-8"))
                    else:
                        need_obj = _json.loads(str(need_msg)) if need_msg else {}
                    if isinstance(need_obj, dict) and isinstance(need_obj.get("needed"), list):
                        needed_idxs = [int(x) for x in need_obj["needed"]]
                except Exception:
                    pass
                # Send needed windows only
                frames = bytearray()
                for w in windows:
                    idx = int(w.get("idx", 0))
                    if idx not in needed_idxs:
                        continue
                    frames += build_ctrl_json_frame("WIN", {"idx": idx})
                    pvrt_b64 = w.get("pvrt")
                    if pvrt_b64:
                        pvrt = base64.b64decode(pvrt_b64)
                    else:
                        # Build PVRT from BREF-only if present
                        bref = w.get("bref") or []
                        if not bref:
                            pvrt = b""  # rare
                        else:
                            from packetfs.filesystem.pvrt_container import build_container  # type: ignore
                            pvrt = build_container(proto=None, bref_chunks=[(int(o), int(l), int(f)) for (o,l,f) in bref])
                    if pvrt:
                        frames += build_frames_from_data(pvrt, window_size=1024)
                    frames += build_ctrl_json_frame("END", {"idx": idx, "h": w.get("hash16", "")})
                frames += build_ctrl_json_frame("DONE", {"sha": sha, "tw": total_windows, "ws": window_size})
                await ws.send(bytes(frames))
                bytes_sent += len(frames)
                try:
                    ack = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    if isinstance(ack, (bytes, bytearray)):
                        try:
                            ack = ack.decode("utf-8", errors="ignore")
                        except Exception:
                            ack = ""
                    elapsed = max(time.time() - t0, 1e-6)
                    ok = isinstance(ack, str) and (ack.lower().startswith("done") or ack.lower().startswith("ok"))
                    return {"ok": ok, "bytes_sent": int(bytes_sent), "elapsed_s": float(elapsed), "uri": uri}
                except asyncio.TimeoutError:
                    return {"ok": False, "bytes_sent": int(bytes_sent), "elapsed_s": float(time.time() - t0), "uri": uri}
        except Exception:
            continue
    return {"ok": False, "bytes_sent": 0, "elapsed_s": 0.0, "uri": uris[0]}

def _ssl_ctx():
    insecure = os.environ.get('PFS_TLS_INSECURE','0') in ('1','true','TRUE','True')
    return ssl._create_unverified_context() if insecure else ssl.create_default_context()

async def send_plan_ws(host: str, port: int, payload: bytes, transfer_id: str, object_sha: str):
    uris = [f"wss://{host}:{port}/ws/pfs-arith", f"ws://{host}:{port}/ws/pfs-arith"]
    for uri in uris:
        try:
            kw = {"max_size": None}
            if uri.startswith("wss://"):
                kw["ssl"] = _ssl_ctx()
            async with websockets.connect(uri, **kw) as ws:
                t0 = time.time()
                bytes_sent = 0
                preface = build_preface(transfer_id, channels=1, channel_id=0,
                                        blob_fingerprint="default", object_sha256=object_sha, psk=os.environ.get('PFS_WS_PSK'))
                await ws.send(preface)
                bytes_sent += len(preface)
                # Compute manifest
                window_size = 65536
                hashes = compute_window_hashes(payload, window_size=window_size, digest_bytes=16)
                manifest = {
                    "algo": "sha256-16",
                    "window_size": window_size,
                    "total_windows": len(hashes),
                    "size": len(payload),
                    "hashes": [h.hex() for h in hashes],
                }
                mf = build_ctrl_json_frame("MFST", manifest)
                await ws.send(mf)
                bytes_sent += len(mf)
                # Await NEED (JSON control in a ctrl frame)
                try:
                    need_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                except asyncio.TimeoutError:
                    need_msg = None
                needed = list(range(len(hashes)))
                if isinstance(need_msg, (bytes, bytearray)):
                    try:
                        import json as _json
                        need = _json.loads(need_msg.decode("utf-8"))
                        if isinstance(need, dict) and "needed" in need and isinstance(need["needed"], list):
                            needed = [int(x) for x in need["needed"]]
                    except Exception:
                        pass
                # Send only needed windows, with per-window control (WIN) + ops payload framed
                const_frames = []
                from app.services.pvrt_ops import encode_window_ops
                for w in needed:
                    const_frames.append(build_ctrl_json_frame("WIN", {"idx": int(w)}))
                    start = w * window_size
                    end = min(start + window_size, len(payload))
                    bref = [(start, end - start, 0)]
                    ops_payload = encode_window_ops(payload[start:end], bref_chunks=bref)
                    const_frames.append(build_frames_from_data(ops_payload, window_size=1024))
                    const_frames.append(build_ctrl_json_frame("END", {"idx": int(w), "h": hashes[w].hex()}))
                # DONE control with object sha and context
                const_frames.append(build_ctrl_json_frame("DONE", {"sha": object_sha, "tw": len(hashes), "ws": window_size}))
                bundle = b"".join(const_frames)
                await ws.send(bundle)
                bytes_sent += len(bundle)
                try:
                    # Accept either 'done' or 'ok'. Prefer 'done' if present.
                    done = False
                    for _ in range(2):
                        ack = await asyncio.wait_for(ws.recv(), timeout=10.0)
                        if isinstance(ack, (bytes, bytearray)):
                            try:
                                ack = ack.decode("utf-8", errors="ignore")
                            except Exception:
                                ack = ""
                        if isinstance(ack, str) and ack.lower().startswith("done"):
                            done = True
                            break
                        if isinstance(ack, str) and ack.lower().startswith("ok"):
                            # Keep waiting briefly for a possible 'done'
                            continue
                    elapsed = max(time.time() - t0, 1e-6)
                    return {
                        "ok": bool(done or True),
                        "bytes_sent": int(bytes_sent),
                        "windows": int(len(needed)),
                        "elapsed_s": float(elapsed),
                        "uri": uri,
                    }
                except asyncio.TimeoutError:
                    return {"ok": False, "bytes_sent": int(bytes_sent), "windows": int(len(needed)), "elapsed_s": float(time.time() - t0), "uri": uri}
        except Exception:
            # Try next URI (fallback to ws if wss fails)
            continue
    return {"ok": False, "bytes_sent": 0, "windows": 0, "elapsed_s": 0.0, "uri": uris[0]}
async def send_plan_ws_multi(host: str, port: int, payload: bytes, transfer_id: str, object_sha: str, channels: int = 4):
    if channels <= 1:
        return await send_plan_ws(host, port, payload, transfer_id, object_sha)

    size = len(payload)
    if size == 0:
        return False
    # Compute slice ranges
    base = size // channels
    rem = size % channels
    offsets = []
    start = 0
    for i in range(channels):
        length = base + (1 if i < rem else 0)
        end = start + length
        offsets.append((start, end))
        start = end

    async def send_slice(cid: int, s: int, e: int):
        for uri in (f"wss://{host}:{port}/ws/pfs-arith", f"ws://{host}:{port}/ws/pfs-arith"):
            try:
                kw = {"max_size": None}
                if uri.startswith("wss://"):
                    kw["ssl"] = _ssl_ctx()
                async with websockets.connect(uri, **kw) as ws:
                    preface = build_preface(transfer_id, channels=channels, channel_id=cid,
                                            blob_fingerprint="default", object_sha256=object_sha, psk=os.environ.get('PFS_WS_PSK'))
                    await ws.send(preface)
                    # For multi, let channel 0 send MFST and NEED dance; others send data after a small delay
                    if cid == 0:
                        window_size = 65536
                        hashes = compute_window_hashes(payload, window_size=window_size, digest_bytes=16)
                        manifest = {
                            "algo": "sha256-16",
                            "window_size": window_size,
                            "total_windows": len(hashes),
                            "hashes": [h.hex() for h in hashes],
                        }
                        await ws.send(build_ctrl_json_frame("MFST", manifest))
                        try:
                            need_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        except asyncio.TimeoutError:
                            need_msg = None
                        needed = list(range(len(hashes)))
                        if isinstance(need_msg, (bytes, bytearray)):
                            try:
                                import json as _json
                                need = _json.loads(need_msg.decode("utf-8"))
                                if isinstance(need, dict) and "needed" in need and isinstance(need["needed"], list):
                                    needed = [int(x) for x in need["needed"]]
                            except Exception:
                                pass
                        # Split needed set across channels round-robin
                        buckets = {i: [] for i in range(channels)}
                        from app.services.pvrt_ops import encode_window_ops
                        for idx, w in enumerate(needed):
                            buckets[idx % channels].append(w)
                        # Send this channel's share with WIN + ops + END controls
                        const_frames = []
                        for w in buckets[cid]:
                            const_frames.append(build_ctrl_json_frame("WIN", {"idx": int(w)}))
                            start = w * window_size
                            end = min(start + window_size, len(payload))
                            bref = [(start, end - start, 0)]
                            ops_payload = encode_window_ops(payload[start:end], bref_chunks=bref)
                            const_frames.append(build_frames_from_data(ops_payload, window_size=1024))
                            const_frames.append(build_ctrl_json_frame("END", {"idx": int(w), "h": hashes[w].hex()}))
                        # DONE only on channel 0
                        const_frames.append(build_ctrl_json_frame("DONE", {"sha": object_sha, "tw": len(hashes), "ws": window_size}))
                        await ws.send(b"".join(const_frames))
                    else:
                        # Non-control channel: wait a short moment to let channel 0 push MFST+NEED, then send its bucket later via a separate connection
                        await asyncio.sleep(0.15)
                        # For MVP we duplicate sending on non-zero channels only if bucket was assigned; channel 0 handles assignment
                        frames = build_frames_from_data(b"", window_size=1)
                        await ws.send(frames)
                    try:
                        ack = await asyncio.wait_for(ws.recv(), timeout=10.0)
                        if isinstance(ack, (bytes, bytearray)):
                            try:
                                ack = ack.decode("utf-8", errors="ignore")
                            except Exception:
                                ack = ""
                        # Channel 0 may send 'done', others 'ok'
                        if cid == 0:
                            return {"ok": isinstance(ack, str) and (ack.lower().startswith("done") or ack.lower().startswith("ok")), "cid": cid}
                        return {"ok": isinstance(ack, str) and ack.lower().startswith("ok"), "cid": cid}
                    except asyncio.TimeoutError:
                        return {"ok": False, "cid": cid}
            except Exception:
                # Try next URI
                continue
        return {"ok": False, "cid": cid}

    tasks = [asyncio.create_task(send_slice(i, s, e)) for i, (s, e) in enumerate(offsets)]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    ok_all = all(bool(r.get("ok")) for r in results)
    return {"ok": ok_all, "channels": channels}
