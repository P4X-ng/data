from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.core.state import CURRENT_BLOB, APP_STATE

from app.core.schemas import BlobSetup

router = APIRouter()


@router.post("/blob/setup")
async def blob_setup(req: BlobSetup):
    try:
        from packetfs.filesystem.virtual_blob import VirtualBlob  # type: ignore
        vb = VirtualBlob(name=req.name, size_bytes=req.size_bytes, seed=req.seed)
        vb.create_or_attach(create=True)
        vb.ensure_filled()
        CURRENT_BLOB.clear()
        CURRENT_BLOB.update({
            "name": req.name,
            "size": req.size_bytes,
            "seed": req.seed,
            "id": vb.id,
            "vb": vb,
        })
        APP_STATE.pop("BLOB_INIT_ERROR", None)
        return {"ok": True, "id": vb.id}
    except Exception as e:
        APP_STATE["BLOB_INIT_ERROR"] = str(e)
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/blob/status")
async def blob_status():
    data = {"attached": bool(CURRENT_BLOB)}
    if CURRENT_BLOB:
        data.update({
            k: v for k, v in CURRENT_BLOB.items() if k in ("name", "size", "seed", "id")
        })
    err = APP_STATE.get("BLOB_INIT_ERROR")
    if err:
        data["error"] = err
    fill = APP_STATE.get("BLOB_FILL")
    if isinstance(fill, dict):
        data["fill"] = {
            k: fill.get(k) for k in ("status", "filled", "size", "pct", "error") if k in fill
        }
    return data


@router.post("/blob/fill")
async def blob_fill():
    """Manually trigger a progressive fill if a blob is attached and not already running/done.
    Returns current fill status after (possibly) starting.
    """
    if not CURRENT_BLOB:
        raise HTTPException(status_code=400, detail="no blob attached")
    fill = APP_STATE.get("BLOB_FILL")
    if isinstance(fill, dict) and fill.get("status") in ("running", "done"):
        return {"started": False, "fill": fill}
    # Launch progressive fill task using existing vb
    vb = CURRENT_BLOB.get("vb")
    size = int(CURRENT_BLOB.get("size", 0))
    if not vb or size <= 0:
        raise HTTPException(status_code=500, detail="invalid blob state")
    import asyncio, time
    APP_STATE["BLOB_FILL"] = {"status": "running", "filled": 0, "size": size, "pct": 0.0, "started_ts": time.time()}
    async def _prog():
        try:
            header_len = 32
            mv = vb.buffer  # type: ignore[attr-defined]
            total_body = max(0, size - header_len)
            block_size = 1 << 20
            filled = 0
            t0 = time.time()
            while filled < total_body:
                want = min(block_size, total_body - filled)
                if want <= 0:
                    break
                mv[header_len + filled: header_len + filled + want] = vb._fill_block(want)  # type: ignore[attr-defined]
                filled += want
                pct = filled / max(1, total_body)
                dt = max(time.time() - t0, 1e-6)
                bps = filled / dt
                eta = (total_body - filled) / bps if bps > 0 else None
                APP_STATE["BLOB_FILL"].update({"filled": filled, "pct": pct, "bps": bps, "eta_s": eta})  # type: ignore[index]
                await asyncio.sleep(0)
            APP_STATE["BLOB_FILL"].update({"status": "done", "pct": 1.0, "filled": total_body})  # type: ignore[index]
        except Exception as e:  # pragma: no cover
            APP_STATE["BLOB_FILL"] = {"status": "error", "error": str(e), "size": size}
    asyncio.create_task(_prog())
    return {"started": True, "fill": APP_STATE.get("BLOB_FILL")}


@router.get("/blob/raw")
async def blob_raw(request: Request):
    """Stream the entire attached blob as application/octet-stream.
    Supports HTTP Range for partial requests.
    """
    if not CURRENT_BLOB or not CURRENT_BLOB.get("vb"):
        raise HTTPException(status_code=404, detail="no blob attached")
    vb = CURRENT_BLOB.get("vb")
    size = int(CURRENT_BLOB.get("size", getattr(vb, "size", 0)))
    if size <= 0:
        raise HTTPException(status_code=500, detail="invalid blob size")

    # Parse Range header: bytes=start-end
    range_header = request.headers.get("range") or request.headers.get("Range")
    start = 0
    end = size - 1
    if range_header and range_header.lower().startswith("bytes="):
        try:
            spec = range_header.split("=", 1)[1].strip()
            part = spec.split(",", 1)[0]
            s, _, e = part.partition("-")
            if s.strip():
                start = int(s)
            if e.strip():
                end = int(e)
            if start < 0:
                start = 0
            if end >= size:
                end = size - 1
            if start > end:
                start, end = 0, size - 1
        except Exception:
            start, end = 0, size - 1

    length = end - start + 1
    chunk_bytes = int(request.query_params.get("chunk", str(16 * 1024 * 1024)))  # default 16 MiB
    if chunk_bytes <= 0:
        chunk_bytes = 16 * 1024 * 1024

    async def iter_chunks():
        off = start
        while off <= end:
            want = min(chunk_bytes, end - off + 1)
            if want <= 0:
                break
            # vb.read returns bytes for [offset, length]
            data = vb.read(off, want)  # type: ignore[attr-defined]
            yield data
            off += want

    status_code = 206 if range_header else 200
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Type": "application/octet-stream",
    }
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    return StreamingResponse(iter_chunks(), status_code=status_code, headers=headers)
