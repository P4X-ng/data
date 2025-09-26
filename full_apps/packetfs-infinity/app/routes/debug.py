from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.state import BLUEPRINTS

router = APIRouter()


@router.get("/debug/recv/{object_sha}")
async def debug_recv(object_sha: str):
    key = f"recv:{object_sha}"
    if key not in BLUEPRINTS:
        raise HTTPException(status_code=404, detail="not found")
    return BLUEPRINTS[key]


@router.get("/debug/transfer/{transfer_id}/acks")
async def debug_acks(transfer_id: str):
    prefix = f"ack:{transfer_id}:"
    out = []
    for k, v in BLUEPRINTS.items():
        if k.startswith(prefix):
            try:
                idx = int(k.split(":")[-1])
            except Exception:
                idx = -1
            entry = {"idx": idx, **v}
            out.append(entry)
    out.sort(key=lambda e: e.get("idx", -1))
    return {"transfer_id": transfer_id, "acks": out}


@router.get("/debug/transfer/{transfer_id}/crcs")
async def debug_crcs(transfer_id: str):
    prefix = f"crc:{transfer_id}:"
    out = []
    for k, v in BLUEPRINTS.items():
        if k.startswith(prefix):
            try:
                idx = int(k.split(":")[-1])
            except Exception:
                idx = -1
            entry = {"idx": idx, **v}
            out.append(entry)
    out.sort(key=lambda e: e.get("idx", -1))
    return {"transfer_id": transfer_id, "crcs": out}


@router.get("/debug/keys")
async def debug_keys(prefix: str = ""):
    keys = [k for k in BLUEPRINTS.keys() if k.startswith(prefix)] if prefix else list(BLUEPRINTS.keys())
    keys.sort()
    return {"count": len(keys), "keys": keys}
