from __future__ import annotations

import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/")
async def index_page():
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    static_dir = os.path.abspath(static_dir)
    try:
        with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception:
        return {"status": "ok", "message": "pfs-infinity running"}
