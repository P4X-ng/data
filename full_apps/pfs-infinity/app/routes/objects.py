from __future__ import annotations

import hashlib
import os
import json
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.schemas import ObjectRef
from app.core.state import BLUEPRINTS, WINDOW_HASHES
from app.core.browse_conf import dev_enabled, psk_required, get_browse_root, is_traversal_safe
from fastapi import Depends, Body, HTTPException
import os

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

    # PacketFS: write bytes into VirtualBlob and build IPROG with BREF (and PVRT BREF-only)
    try:
        from packetfs.filesystem.blob_fs import BlobFS, BlobConfig  # type: ignore
        from packetfs.filesystem.iprog import build_iprog_for_file_bytes, BlobFingerprint  # type: ignore
        # Blob configuration (mirror CURRENT_BLOB defaults if set)
        blob_name = os.environ.get("PFS_BLOB_NAME", "pfs_vblob")
        blob_size = int(os.environ.get("PFS_BLOB_SIZE_BYTES", str(1 << 30)))
        blob_seed = int(os.environ.get("PFS_BLOB_SEED", "1337"))
        meta_dir = os.environ.get("PFS_META_DIR", "/app/meta")
        os.makedirs(meta_dir, exist_ok=True)
        cfg = BlobConfig(name=blob_name, size_bytes=blob_size, seed=blob_seed, meta_dir=meta_dir)
        fs = BlobFS(cfg)
        segs = fs.write_bytes(data)
        fs.record_object(obj_id, len(data), sha256, 65536, segs)
        fp = BlobFingerprint(name=blob_name, size=blob_size, seed=blob_seed)
        # Include PVRT BREF-only so sender can transmit tiny PVRT
        iprog = build_iprog_for_file_bytes(data, file.filename or obj_id, fp, segs, window_size=65536, include_pvrt=True)
        fs.close()
    except Exception as e:
        # Fallback: minimal plan if PacketFS not available
        iprog = {
            "type": "iprog",
            "version": 1,
            "file": file.filename or obj_id,
            "size": len(data),
            "sha256": sha256,
            "window_size": 65536,
            "blob": {"name": os.environ.get("PFS_BLOB_NAME", "pfs_vblob"), "size": int(os.environ.get("PFS_BLOB_SIZE_BYTES", str(1<<30))), "seed": int(os.environ.get("PFS_BLOB_SEED", "1337"))},
            "windows": [],
            "done": {"sha256": sha256, "total_windows": 0},
            "metrics": {"pvrt_total": len(data), "tx_ratio": 1.0},
        }

    BLUEPRINTS[obj_id] = {
        "version": 1,
        "size": len(data),
        "sha256": sha256,
        "iprog": iprog,
        "filename": file.filename or "unknown",
        # Keep raw bytes for dev-only download path
        "bytes": data,
    }
    try:
        from app.services.pvrt_framing import compute_window_hashes
        WINDOW_HASHES[obj_id] = compute_window_hashes(data, window_size=65536, digest_bytes=16)
    except Exception:
        pass
    return {"object_id": obj_id}


@router.get("/objects", tags=["objects"])
async def list_objects():
    out = []
    for k, v in list(BLUEPRINTS.items()):
        if not isinstance(v, dict):
            continue
        if "sha256" in v and "size" in v:
            out.append({"object_id": k, "size": int(v.get("size", 0)), "sha256": v.get("sha256", "")})
    return sorted(out, key=lambda x: x.get("object_id", ""))


@router.get("/objects/{object_id}")
async def get_object(object_id: str):
    bp = BLUEPRINTS.get(object_id)
    if not bp:
        raise HTTPException(status_code=404, detail="not found")
    return {"object_id": object_id, "size": bp["size"], "sha256": bp["sha256"]}


@router.post("/objects/from-path")
async def create_object_from_path(payload: dict = Body(...), _auth: None = Depends(psk_required)):
    base = get_browse_root()
    if base is None:
        raise HTTPException(status_code=400, detail="browse root not configured")
    p = str(payload.get("path") or "")
    if not p:
        raise HTTPException(status_code=400, detail="path required")
    target = (base / p.lstrip("/")).resolve()
    if not is_traversal_safe(base, target):
        raise HTTPException(status_code=400, detail="path escapes sandbox")
    if (not target.exists()) or (not target.is_file()):
        raise HTTPException(status_code=404, detail="not found")
    data = open(target, "rb").read()
    import hashlib
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
    return {"object_id": obj_id}


@router.get("/objects/{object_id}/bytes")
async def get_object_bytes(object_id: str, _auth: None = Depends(psk_required)):
    if not dev_enabled():
        raise HTTPException(status_code=404, detail="not found")
    bp = BLUEPRINTS.get(object_id)
    if not bp or "bytes" not in bp:
        raise HTTPException(status_code=404, detail="no bytes available")
    from fastapi.responses import StreamingResponse

    data = bp["bytes"]
    def it():
        chunk = 1 << 20
        for i in range(0, len(data), chunk):
            yield data[i : i + chunk]
    headers = {
        "Content-Length": str(len(data)),
        "Content-Disposition": f"attachment; filename={object_id.replace(':', '_')}.bin",
    }
    return StreamingResponse(it(), media_type="application/octet-stream", headers=headers)
