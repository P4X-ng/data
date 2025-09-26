from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.core.browse_conf import get_browse_root, is_traversal_safe, psk_required, parse_range
from app.core.browse_models import BrowseRoot, DirEntry, FileStat

router = APIRouter()


@router.get("/browse/roots", response_model=List[BrowseRoot])
async def browse_roots(_auth: None = Depends(psk_required)):
    roots: List[BrowseRoot] = [
        BrowseRoot(id="objects", type="virtual", description="Uploaded objects (local store)")
    ]
    base = get_browse_root()
    if base is not None:
        roots.append(BrowseRoot(id="share", type="fs", root=str(base)))
    return roots


@router.get("/browse/list", response_model=List[DirEntry])
async def browse_list(
    root: str = Query(..., description="Root id: 'share'"),
    path: str = Query("/", description="Path within root"),
    _auth: None = Depends(psk_required),
):
    if root != "share":
        raise HTTPException(status_code=404, detail="unknown root")
    base = get_browse_root()
    if base is None:
        raise HTTPException(status_code=404, detail="share root not configured")
    target = (base / path.lstrip("/")).resolve()
    if not is_traversal_safe(base, target):
        raise HTTPException(status_code=400, detail="path escapes sandbox")
    if not target.exists():
        raise HTTPException(status_code=404, detail="not found")
    entries: List[DirEntry] = []
    if target.is_dir():
        for de in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            try:
                st = de.stat()
            except Exception:
                continue
            entries.append(
                DirEntry(name=de.name, is_dir=de.is_dir(), size=int(st.st_size), mtime=float(st.st_mtime))
            )
        return entries
    else:
        st = target.stat()
        return [DirEntry(name=target.name, is_dir=False, size=int(st.st_size), mtime=float(st.st_mtime))]


@router.get("/browse/stat", response_model=FileStat)
async def browse_stat(
    root: str = Query(...),
    path: str = Query(...),
    _auth: None = Depends(psk_required),
):
    if root != "share":
        raise HTTPException(status_code=404, detail="unknown root")
    base = get_browse_root()
    if base is None:
        raise HTTPException(status_code=404, detail="share root not configured")
    target = (base / path.lstrip("/")).resolve()
    if not is_traversal_safe(base, target):
        raise HTTPException(status_code=400, detail="path escapes sandbox")
    if not target.exists():
        raise HTTPException(status_code=404, detail="not found")
    st = target.stat()
    rel = str(target.resolve()).replace(str(base.resolve()), "", 1) or "/"
    if rel.startswith("/"):
        rel = rel
    else:
        rel = "/" + rel
    return FileStat(
        path=str(target),
        relpath=rel,
        size=int(st.st_size),
        mtime=float(st.st_mtime),
        mode=int(st.st_mode),
        is_dir=target.is_dir(),
    )


@router.get("/browse/download")
async def browse_download(
    request: Request,
    root: str = Query(...),
    path: str = Query(...),
    _auth: None = Depends(psk_required),
):
    if root != "share":
        raise HTTPException(status_code=404, detail="unknown root")
    base = get_browse_root()
    if base is None:
        raise HTTPException(status_code=404, detail="share root not configured")
    target = (base / path.lstrip("/")).resolve()
    if not is_traversal_safe(base, target):
        raise HTTPException(status_code=400, detail="path escapes sandbox")
    if (not target.exists()) or (not target.is_file()):
        raise HTTPException(status_code=404, detail="not found")

    size = target.stat().st_size

    def iter_file_range(start: int = 0, end_inclusive: Optional[int] = None, chunk: int = 1 << 20):
        with open(target, "rb") as f:
            if start:
                f.seek(start)
            to_read = (end_inclusive - start + 1) if end_inclusive is not None else None
            while True:
                if to_read is not None and to_read <= 0:
                    break
                n = chunk if to_read is None else min(chunk, to_read)
                b = f.read(n)
                if not b:
                    break
                yield b
                if to_read is not None:
                    to_read -= len(b)

    headers = {"Accept-Ranges": "bytes"}
    content_type, _ = mimetypes.guess_type(str(target))
    content_type = content_type or "application/octet-stream"

    range_header = request.headers.get("range") or request.headers.get("Range")
    if range_header:
        start, end = parse_range(range_header, size)
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        headers["Content-Length"] = str(end - start + 1)
        return StreamingResponse(
            iter_file_range(start, end), status_code=206, media_type=content_type, headers=headers
        )

    headers["Content-Length"] = str(size)
    return StreamingResponse(iter_file_range(), media_type=content_type, headers=headers)
