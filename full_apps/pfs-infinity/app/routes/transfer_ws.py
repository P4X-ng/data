from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, WebSocket
from app.core.state import TRANSFERS

router = APIRouter()

@router.websocket("/ws/transfer")
async def ws_transfer(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            # Emit a summary of transfers every 1s
            snap = {}
            for tid, st in list(TRANSFERS.items()):
                try:
                    snap[tid] = {
                        "state": getattr(st, "state", "unknown"),
                        "details": getattr(st, "details", {}),
                    }
                except Exception:
                    pass
            await ws.send_text(json.dumps({"type": "transfers", "transfers": snap}))
            await asyncio.sleep(1.0)
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass