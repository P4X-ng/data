from __future__ import annotations

import hashlib
import os
import json
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.schemas import ObjectRef
from app.core.state import BLUEPRINTS, WINDOW_HASHES

router = APIRouter()


@router.post("/blueprints/from-bytes")
async def blueprint_from_bytes(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    sha256 = hashlib.sha256(data).hexdigest()
    bp = {
        "version": 1,
        "size": len(data),
        "sha256": sha256,
        "ops": [{"op": "const_hash", "algo": "sha256", "hex": sha256}],
        "notes": ["MVP placeholder; replace with PacketFS blueprint derivation"],
    }
    return bp


@router.post("/objects", response_model=ObjectRef)
async def create_object(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    sha256 = hashlib.sha256(data).hexdigest()
    obj_id = f"sha256:{sha256}"
    plan = {
        "type": "pfs-plan",
        "version": 1,
        "object_id": obj_id,
        "size": len(data),
        "sha256": sha256,
        "blob": os.environ.get("PFS_BLOB_NAME", "default"),
        "ops": [{"op": "ref_object", "id": obj_id}],
    }
    BLUEPRINTS[obj_id] = {
        "version": 1,
        "size": len(data),
        "sha256": sha256,
        "plan": plan,
        "bytes": data,
    }
    try:
        from app.services.pvrt_framing import compute_window_hashes

        WINDOW_HASHES[obj_id] = compute_window_hashes(data, window_size=65536, digest_bytes=16)
    except Exception:
        pass
    return {"object_id": obj_id}


@router.get("/objects/{object_id}")
async def get_object(object_id: str):
    bp = BLUEPRINTS.get(object_id)
    if not bp:
        raise HTTPException(status_code=404, detail="not found")
    return {"object_id": object_id, "size": bp["size"], "sha256": bp["sha256"]}
