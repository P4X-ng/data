from __future__ import annotations

import asyncio
import hashlib
import json
import time
from fastapi import APIRouter, HTTPException

from app.core.schemas import TransferRequest, TransferStatus
from app.core.state import TRANSFERS, CURRENT_BLOB, BLUEPRINTS

router = APIRouter()


async def _send_quic_plan(host: str, port: int, payload: bytes, tid: str, object_sha: str) -> bool:
    try:
        from app.services.transports.quic_proxy import send_plan_quic
        return await send_plan_quic(host, port, payload, tid, object_sha)
    except Exception:
        return False

async def _send_quic_iprog(host: str, port: int, iprog: dict, tid: str) -> bool:
    try:
        from app.services.transports.quic_proxy import send_iprog_quic
        return await send_iprog_quic(host, port, iprog, tid)
    except Exception:
        return False

async def _send_https_offsets(host: str, https_port: int, iprog: dict, tid: str, timeout_s: float) -> bool:
    try:
        from app.services.transports.iprog_pack import build_iprog_http_payload
        payload = build_iprog_http_payload(iprog, tid)
        import httpx
        url = f"https://{host}:{https_port}/arith/offsets"
        async with httpx.AsyncClient(verify=False, timeout=timeout_s) as client:
            r = await client.post(url, content=payload, headers={"Content-Type": "application/octet-stream"})
            return r.status_code in (200, 201, 204)
    except Exception:
        return False
    try:
        from app.services.transports.quic_proxy import send_iprog_quic
        return await send_iprog_quic(host, port, iprog, tid)
    except Exception:
        return False


async def _send_webrtc_plan(host: str, https_port: int, payload: bytes, tid: str, object_sha: str) -> bool:
    try:
        import importlib

        mod = importlib.import_module("app.services.transports.webrtc_proxy")
        send_plan_webrtc = getattr(mod, "send_plan_webrtc", None)
        if send_plan_webrtc is None:
            return False
        return await send_plan_webrtc(host, https_port, payload, tid, object_sha)  # type: ignore[misc]
    except Exception:
        return False


async def _send_tcp_grams(host: str, port: int, payload: bytes) -> bool:
    try:
        reader, writer = await asyncio.open_connection(host, port)
        writer.write(len(payload).to_bytes(4, "big") + payload)
        await writer.drain()
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _send_ws_plan(host: str, port: int, payload: bytes, transfer_id: str, object_sha: str) -> bool:
    try:
        from app.services.transports.ws_proxy import send_plan_ws

        return await send_plan_ws(host, port, payload, transfer_id, object_sha)
    except Exception:
        return False


async def _send_ws_plan_multi(
    host: str, port: int, payload: bytes, transfer_id: str, object_sha: str, channels: int = 4
) -> bool:
    try:
        from app.services.transports.ws_proxy import send_plan_ws_multi

        return await send_plan_ws_multi(host, port, payload, transfer_id, object_sha, channels=channels)
    except Exception:
        return False


@router.post("/transfers", response_model=TransferStatus)
async def start_transfer(req: TransferRequest):
    obj = BLUEPRINTS.get(req.object_id)
    if not obj:
        raise HTTPException(status_code=404, detail="object not found")
    # Arithmetic-first: require IPROG by default; plan/raw only for emergency
    iprog = obj.get("iprog")
    plan = obj.get("plan")
    if not iprog and not plan:
        raise HTTPException(status_code=400, detail="no blueprint or plan for object")

    tid = hashlib.sha256((req.object_id + req.peer.host).encode()).hexdigest()[:16]
    status = TransferStatus(transfer_id=tid, state="running", details={})
    TRANSFERS[tid] = status

    # Metrics context
    object_size = int((iprog or plan).get("size", 0)) if (iprog or plan) else 0
    t0 = time.time()
    path_sel = "unknown"

    # Env configuration
    import os
    WS_CHANNELS = int(os.environ.get("PFS_WS_CHANNELS", "4") or 4)
    EMERGENCY_HTTPS = os.environ.get("PFS_EMERGENCY_HTTPS", "0") in ("1","true","TRUE","True")

    async def _run():
        nonlocal path_sel
        ok = False
        if req.mode == "auto":
            # Arithmetic-only: prefer WS multi if enough windows, else single WS
            if iprog:
                windows = iprog.get("windows", []) if isinstance(iprog, dict) else []
                ws_port = req.peer.ws_port or req.peer.https_port
                try:
                    if WS_CHANNELS > 1 and len(windows) >= WS_CHANNELS:
                        from app.services.transports.ws_proxy import send_iprog_ws_multi
                        res = await send_iprog_ws_multi(req.peer.host, ws_port, iprog, tid, channels=WS_CHANNELS)
                        ok = bool(res.get("ok"))
                        if ok:
                            path_sel = "ws-iprog-multi"
                            status.details.update({
                                "bytes_sent": int(res.get("bytes_sent", 0)),
                                "elapsed_s": float(res.get("elapsed_s", 0.0)),
                                "tx_ratio": float(iprog.get("metrics", {}).get("tx_ratio", 0.0)),
                                "channels": int(WS_CHANNELS),
                            })
                    if not ok:
                        from app.services.transports.ws_proxy import send_iprog_ws
                        res = await send_iprog_ws(req.peer.host, ws_port, iprog, tid)
                        ok = bool(res.get("ok"))
                        if ok:
                            path_sel = "ws-iprog"
                            status.details.update({
                                "bytes_sent": int(res.get("bytes_sent", 0)),
                                "elapsed_s": float(res.get("elapsed_s", 0.0)),
                                "tx_ratio": float(iprog.get("metrics", {}).get("tx_ratio", 0.0)),
                            })
                except Exception:
                    ok = False
            # Emergency HTTPS offsets only if explicitly enabled
            if not ok and iprog and EMERGENCY_HTTPS:
                ok = await _send_https_offsets(req.peer.host, req.peer.https_port, iprog, tid, req.timeout_s)
                if ok:
                    path_sel = "https-offsets"
        else:
            if req.mode == "ws":
                if not iprog:
                    raise HTTPException(status_code=400, detail="iprog required for ws mode")
                from app.services.transports.ws_proxy import send_iprog_ws
                ws_port = req.peer.ws_port or req.peer.https_port
                res = await send_iprog_ws(req.peer.host, ws_port, iprog, tid)
                ok = bool(res.get("ok"))
                if ok:
                    path_sel = "ws-iprog"
                    status.details.update({
                        "bytes_sent": int(res.get("bytes_sent", 0)),
                        "elapsed_s": float(res.get("elapsed_s", 0.0)),
                        "tx_ratio": float(iprog.get("metrics", {}).get("tx_ratio", 0.0)),
                    })
            elif req.mode == "ws-multi":
                if not iprog:
                    raise HTTPException(status_code=400, detail="iprog required for ws-multi mode")
                from app.services.transports.ws_proxy import send_iprog_ws_multi
                ws_port = req.peer.ws_port or req.peer.https_port
                channels = WS_CHANNELS
                res = await send_iprog_ws_multi(req.peer.host, ws_port, iprog, tid, channels=channels)
                ok = bool(res.get("ok"))
                if ok:
                    path_sel = "ws-iprog-multi"
                    status.details.update({
                        "bytes_sent": int(res.get("bytes_sent", 0)),
                        "elapsed_s": float(res.get("elapsed_s", 0.0)),
                        "tx_ratio": float(iprog.get("metrics", {}).get("tx_ratio", 0.0)),
                        "channels": int(channels),
                    })
            elif req.mode in ("iprog-only", "pfs-only"):
                if not iprog:
                    raise HTTPException(status_code=400, detail="iprog required for pfs-only")
                from app.services.transports.ws_proxy import send_iprog_ws
                ws_port = req.peer.ws_port or req.peer.https_port
                res = await send_iprog_ws(req.peer.host, ws_port, iprog, tid)
                ok = bool(res.get("ok"))
                if ok:
                    path_sel = "ws-iprog"
                    status.details.update({
                        "bytes_sent": int(res.get("bytes_sent", 0)),
                        "elapsed_s": float(res.get("elapsed_s", 0.0)),
                        "tx_ratio": float(iprog.get("metrics", {}).get("tx_ratio", 0.0)),
                    })
            elif req.mode == "bytes":
                if not EMERGENCY_HTTPS:
                    raise HTTPException(status_code=400, detail="bytes mode disabled (emergency only)")
                try:
                    payload_bytes = json.dumps(plan or {}).encode("utf-8")
                    import httpx
                    async def agen():
                        yield payload_bytes
                    url = f"https://{req.peer.host}:{req.peer.https_port}/arith/{req.object_id}"
                    async with httpx.AsyncClient(verify=False, timeout=req.timeout_s) as client:
                        r = await client.post(url, content=agen())
                        ok = r.status_code in (200, 201, 204)
                        if ok:
                            path_sel = "https"
                except Exception:
                    ok = False
            else:
                # Explicitly ignore/disable other paths (quic/tcp/webrtc) in this build
                raise HTTPException(status_code=400, detail=f"mode '{req.mode}' not supported")
        # Finalize metrics and state
        elapsed = max(time.time() - t0, 1e-6)
        bytes_sent = int(status.details.get("bytes_sent", 0)) if isinstance(status.details, dict) else 0
        sent_bps = (bytes_sent / elapsed) if bytes_sent else 0.0
        tx_ratio = (float(object_size) / float(bytes_sent)) if (bytes_sent and object_size) else 1.0
        speedup_vs_raw = tx_ratio
        status.details = {
            "object_size": int(object_size),
            "bytes_sent": int(bytes_sent),
            "elapsed_s": float(elapsed),
            "sent_bytes_per_s": float(sent_bps),
            "tx_ratio": float(tx_ratio),
            "speedup_vs_raw": float(speedup_vs_raw),
            "path": path_sel,
        }
        status.state = "success" if ok else "failed"

    asyncio.create_task(_run())
    return status


@router.get("/transfers/{transfer_id}", response_model=TransferStatus)
async def get_transfer(transfer_id: str):
    st = TRANSFERS.get(transfer_id)
    if not st:
        raise HTTPException(status_code=404, detail="not found")
    return st

@router.get("/transfers/{transfer_id}/progress")
async def get_transfer_progress(transfer_id: str):
    # Count ACKs recorded by receiver as progress proxy
    try:
        acks = 0
        total = 0
        for k, v in list(BLUEPRINTS.items()):
            if k.startswith(f"ack:{transfer_id}:") and isinstance(v, dict):
                acks += 1
        # Try to infer total windows from CRCs or mfst
        for k, v in list(BLUEPRINTS.items()):
            if k.startswith(f"crc:{transfer_id}:"):
                total = max(total, 1)
        # Fallback to details
        st = TRANSFERS.get(transfer_id)
        if st and isinstance(st.details, dict):
            total = max(total, int(st.details.get("windows", 0)))
        return {"transfer_id": transfer_id, "acks": int(acks), "total": int(total), "ratio": (float(acks)/float(total) if total else 0.0)}
    except Exception:
        return {"transfer_id": transfer_id, "acks": 0, "total": 0, "ratio": 0.0}
