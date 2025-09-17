from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.schemas import BlobSetup
from app.core.state import CURRENT_BLOB

router = APIRouter()


@router.post("/blob/setup")
async def blob_setup(cfg: BlobSetup):
    try:
        from packetfs.filesystem.virtual_blob import VirtualBlob  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VirtualBlob unavailable: {e}")
    try:
        vb = VirtualBlob(name=cfg.name, size_bytes=cfg.size_bytes, seed=cfg.seed)
        vb.create_or_attach(create=True)
        vb.ensure_filled()
        CURRENT_BLOB.clear()
        CURRENT_BLOB.update({
            "name": cfg.name,
            "size": cfg.size_bytes,
            "seed": cfg.seed,
            "id": vb.id,
            "vb": vb,
        })
        return {"status": "ok", "id": vb.id, "name": cfg.name, "size": cfg.size_bytes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blob/status")
async def blob_status():
    if not CURRENT_BLOB:
        return {"status": "none"}
    return {
        "status": "attached",
        "name": CURRENT_BLOB.get("name"),
        "size": CURRENT_BLOB.get("size"),
        "seed": CURRENT_BLOB.get("seed"),
        "id": CURRENT_BLOB.get("id"),
    }
