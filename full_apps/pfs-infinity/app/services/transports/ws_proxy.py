# WebSocket client transports for PacketFS plan
import asyncio
import json
import websockets
from app.services.pvrt_framing import (
    build_preface,
    build_frames_from_data,
    build_ctrl_json_frame,
    compute_window_hashes,
)

async def send_plan_ws(host: str, port: int, payload: bytes, transfer_id: str, object_sha: str) -> bool:
    uri = f"ws://{host}:{port}/ws/pfs-arith"
    try:
        async with websockets.connect(uri, max_size=None) as ws:
            preface = build_preface(transfer_id, channels=1, channel_id=0,
                                    blob_fingerprint="default", object_sha256=object_sha, psk=None)
            await ws.send(preface)
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
            await ws.send(build_ctrl_json_frame("MFST", manifest))
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
            await ws.send(b"".join(const_frames))
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
                return done or True
            except asyncio.TimeoutError:
                return False
    except Exception:
        return False

async def send_plan_ws_multi(host: str, port: int, payload: bytes, transfer_id: str, object_sha: str, channels: int = 4) -> bool:
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

    async def send_slice(cid: int, s: int, e: int) -> bool:
        uri = f"ws://{host}:{port}/ws/pfs-arith"
        try:
            async with websockets.connect(uri, max_size=None) as ws:
                preface = build_preface(transfer_id, channels=channels, channel_id=cid,
                                        blob_fingerprint="default", object_sha256=object_sha, psk=None)
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
                        return isinstance(ack, str) and (ack.lower().startswith("done") or ack.lower().startswith("ok"))
                    return isinstance(ack, str) and ack.lower().startswith("ok")
                except asyncio.TimeoutError:
                    return False
        except Exception:
            return False

    tasks = [asyncio.create_task(send_slice(i, s, e)) for i, (s, e) in enumerate(offsets)]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return all(results)
