from __future__ import annotations

import hashlib
import json
from fastapi import APIRouter, Body, HTTPException

from app.core.schemas import SDP
from app.core.state import BLUEPRINTS

router = APIRouter()


# WebRTC signaling (receiver side)
try:
    import importlib

    _webrtc_mod = importlib.import_module("app.services.transports.webrtc_proxy")
    create_answer_for_offer = getattr(_webrtc_mod, "create_answer_for_offer", None)
except Exception:
    create_answer_for_offer = None  # type: ignore


@router.post("/webrtc/offer")
async def webrtc_offer(offer: SDP):
    if create_answer_for_offer is None:
        raise HTTPException(status_code=503, detail="webrtc not available")
    answer = await create_answer_for_offer(offer.sdp)  # type: ignore[misc]
    return {"sdp": answer, "type": "answer"}


# Arithmetic over HTTPS (chunked) sink (receiver side)
@router.post("/arith/{object_id}")
async def post_arith(object_id: str, body: bytes = Body(...)):
    try:
        plan = json.loads(body.decode("utf-8"))
        BLUEPRINTS[object_id] = {
            "version": plan.get("version", 1),
            "size": plan.get("size", 0),
            "sha256": plan.get("sha256", ""),
            "plan": plan,
        }
        return {"status": "ok", "object_id": object_id}
    except Exception:
        raise HTTPException(status_code=400, detail="invalid plan")


# Bytes fallback sink (receiver side, catastrophic only)
@router.put("/bytes/{object_id}")
async def put_bytes(object_id: str, body: bytes = Body(...)):
    BLUEPRINTS[object_id] = {
        "version": 1,
        "size": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": body,
    }
    return {"status": "ok", "object_id": object_id}
