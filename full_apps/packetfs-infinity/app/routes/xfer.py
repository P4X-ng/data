from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

from app.core.browse_conf import get_browse_root, is_traversal_safe
from app.core.state import BLUEPRINTS
from fastapi import Body

router = APIRouter()

class Endpoint(BaseModel):
    host: str
    ws_port: int = 8811

class XferSide(BaseModel):
    endpoint: Endpoint
    path: str

class XferRequest(BaseModel):
    src: XferSide
    dst: Endpoint
    dst_path: str | None = None  # path relative to destination browse root; if None, no write-to-disk
    src_psk: str | None = None
    dst_psk: str | None = None
    timeout_s: float = 10.0

@router.post("/xfer")
async def xfer(req: XferRequest):
    """Orchestrate a remote->remote PFS transfer:
    1) Ask source host to ingest src.path from its browse root: POST /objects/from-path
    2) Ask source host to start /transfers with peer=dst
    3) Poll source /transfers/{id} until success/fail or timeout
    Returns final transfer status.
    """
    src_base = f"http://{req.src.endpoint.host}:{req.src.endpoint.ws_port}"
    dst_ws = req.dst.ws_port or req.src.endpoint.ws_port
    try:
        async with httpx.AsyncClient(timeout=req.timeout_s) as client:
            # 1) create object on source
            headers = {}
            if req.src_psk:
                headers["X-PFS-PSK"] = req.src_psk
            r = await client.post(f"{src_base}/objects/from-path", json={"path": req.src.path}, headers=headers)
            if r.status_code != 200:
                raise HTTPException(status_code=502, detail=f"source ingest failed: {r.text}")
            obj = r.json()
            object_id = obj.get("object_id")
            if not object_id:
                raise HTTPException(status_code=502, detail="source did not return object_id")
            # 2) start transfer on source
            body = {
                "object_id": object_id,
                "mode": "auto",
                "peer": {
                    "host": req.dst.host,
                    "ws_port": dst_ws,
                    "https_port": dst_ws,
                    "udp_port": 8853,
                },
                "timeout_s": req.timeout_s,
            }
            r2 = await client.post(f"{src_base}/transfers", json=body, headers=headers)
            if r2.status_code != 200:
                raise HTTPException(status_code=502, detail=f"source start transfer failed: {r2.text}")
            tx = r2.json()
            tid = tx.get("transfer_id")
            if not tid:
                raise HTTPException(status_code=502, detail="source did not return transfer_id")
            # 3) poll
            for _ in range(30):
                st = await client.get(f"{src_base}/transfers/{tid}", headers=headers)
                if st.status_code != 200:
                    break
                j = st.json()
                if j.get("state") in ("success", "failed"):
                    # Optionally instruct destination to save to disk
                    if j.get("state") == "success" and req.dst_path:
                        try:
                            sha = object_id.split(":", 1)[1] if ":" in object_id else object_id
                        except Exception:
                            sha = object_id
                        dst_base = f"http://{req.dst.host}:{dst_ws}"
                        await client.post(f"{dst_base}/xfer/save", json={"sha256": sha, "path": req.dst_path})
                    return j
            return {"state": "pending", "transfer_id": tid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SaveRequest(BaseModel):
    sha256: str
    path: str  # relative to browse root

@router.post("/xfer/save")
async def xfer_save(req: SaveRequest):
    base = get_browse_root()
    if base is None:
        raise HTTPException(status_code=400, detail="browse root not configured")
    key = f"recv:{req.sha256}"
    meta = BLUEPRINTS.get(key)
    if not meta or "bytes" not in meta:
        raise HTTPException(status_code=404, detail="received bytes not found")
    target = (base / req.path.lstrip("/")).resolve()
    if not is_traversal_safe(base, target):
        raise HTTPException(status_code=400, detail="path escapes sandbox")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as f:
        f.write(meta["bytes"])  # type: ignore[index]
    return {"status": "ok", "path": str(target)}
