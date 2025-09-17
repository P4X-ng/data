from __future__ import annotations

import asyncio
import hashlib
import json
import time
from fastapi import APIRouter, HTTPException

from app.core.schemas import TransferRequest, TransferStatus
from app.core.state import BLUEPRINTS, TRANSFERS

router = APIRouter()


async def _send_quic_plan(host: str, port: int, payload: bytes, tid: str, object_sha: str) -> bool:
    try:
        from app.services.transports.quic_proxy import send_plan_quic

        return await send_plan_quic(host, port, payload, tid, object_sha)
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
    plan = obj.get("plan")
    if not plan:
        raise HTTPException(status_code=400, detail="no plan for object")
    payload = json.dumps(plan).encode("utf-8")

    tid = hashlib.sha256((req.object_id + req.peer.host).encode()).hexdigest()[:16]
    status = TransferStatus(transfer_id=tid, state="running", details={})
    TRANSFERS[tid] = status

    # Metrics context
    plan_bytes = len(payload)
    object_size = int(plan.get("size", 0))
    t0 = time.time()
    path_sel = "unknown"

    async def _run():
        nonlocal path_sel
        ok = False
        if req.mode == "auto":
            try:
                done, pending = await asyncio.wait(
                    {
                        asyncio.create_task(
                            _send_quic_plan(req.peer.host, req.peer.udp_port, payload, tid, plan.get("sha256", ""))
                        ),
                        asyncio.create_task(
                            _send_webrtc_plan(
                                req.peer.host, req.peer.https_port, payload, tid, plan.get("sha256", "")
                            )
                        ),
                    },
                    timeout=req.timeout_s,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in done:
                    if t.result() is True:
                        ok = True
                        # we can't easily map back to which coro finished here
                        # prefer setting path after subsequent fallbacks
                for p in pending:
                    p.cancel()
            except Exception:
                ok = False
            if not ok:
                ws_port = req.peer.ws_port or req.peer.https_port
                ok = await _send_ws_plan_multi(req.peer.host, ws_port, payload, tid, plan.get("sha256", ""), channels=4)
                if ok:
                    path_sel = "ws-multi"
            if not ok:
                ws_port = req.peer.ws_port or req.peer.https_port
                ok = await _send_ws_plan(req.peer.host, ws_port, payload, tid, plan.get("sha256", ""))
                if ok:
                    path_sel = "ws"
            if not ok:
                ok = await _send_tcp_grams(req.peer.host, req.peer.tcp_port, payload)
                if ok:
                    path_sel = "tcp"
            if not ok:
                try:
                    import httpx

                    async def agen():
                        yield payload

                    url = f"https://{req.peer.host}:{req.peer.https_port}/arith/{req.object_id}"
                    async with httpx.AsyncClient(verify=False, timeout=req.timeout_s) as client:
                        r = await client.post(url, content=agen())
                        ok = r.status_code in (200, 201, 204)
                        if ok:
                            path_sel = "https"
                except Exception:
                    ok = False
        else:
            if req.mode == "quic":
                ok = await _send_quic_plan(req.peer.host, req.peer.udp_port, payload, tid, plan.get("sha256", ""))
                if ok:
                    path_sel = "quic"
            elif req.mode == "webrtc":
                ok = await _send_webrtc_plan(req.peer.host, req.peer.https_port, payload, tid, plan.get("sha256", ""))
                if ok:
                    path_sel = "webrtc"
            elif req.mode == "ws":
                ws_port = req.peer.ws_port or req.peer.https_port
                ok = await _send_ws_plan(req.peer.host, ws_port, payload, tid, plan.get("sha256", ""))
                if ok:
                    path_sel = "ws"
            elif req.mode == "ws-multi":
                ws_port = req.peer.ws_port or req.peer.https_port
                ok = await _send_ws_plan_multi(req.peer.host, ws_port, payload, tid, plan.get("sha256", ""), channels=4)
                if ok:
                    path_sel = "ws-multi"
            elif req.mode == "tcp":
                ok = await _send_tcp_grams(req.peer.host, req.peer.tcp_port, payload)
                if ok:
                    path_sel = "tcp"
            elif req.mode == "bytes":
                try:
                    import httpx

                    async def agen():
                        yield payload

                    url = f"https://{req.peer.host}:{req.peer.https_port}/arith/{req.object_id}"
                    async with httpx.AsyncClient(verify=False, timeout=req.timeout_s) as client:
                        r = await client.post(url, content=agen())
                        ok = r.status_code in (200, 201, 204)
                except Exception:
                    ok = False
        # Finalize metrics
        elapsed = max(time.time() - t0, 1e-6)
        eff_bps = (object_size / elapsed) if object_size else 0.0
        plan_bps = (plan_bytes / elapsed) if plan_bytes else 0.0
        speedup = (float(object_size) / float(plan_bytes)) if plan_bytes else None
        status.details = {
            "object_size": int(object_size),
            "plan_bytes": int(plan_bytes),
            "elapsed_s": float(elapsed),
            "eff_bytes_per_s": float(eff_bps),
            "plan_bytes_per_s": float(plan_bps),
            "speedup_vs_raw": float(speedup) if speedup is not None else None,
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
