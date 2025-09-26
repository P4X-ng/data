from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.core.browse_conf import get_browse_root, is_traversal_safe
from app.core.browse_models import DirEntry


def register_browse_ws(app: FastAPI) -> None:
    @app.websocket("/ws/pfs-browse")
    async def ws_browse(ws: WebSocket):  # noqa: ANN001
        await ws.accept()
        psk_required = False
        want_psk = None
        try:
            # Read optional hello first (JSON)
            msg = await ws.receive()
            hello_bytes = msg.get("bytes") or msg.get("text", "").encode()
            try:
                hello = json.loads(hello_bytes.decode("utf-8")) if hello_bytes else {}
            except Exception:
                hello = {}
            want_psk = os.environ.get("PFS_BROWSE_PSK")
            if want_psk:
                psk_required = True
                got = hello.get("psk") if isinstance(hello, dict) else None
                if not got or got != want_psk:
                    await ws.send_text(json.dumps({"t": "hello", "ok": False, "error": "unauthorized"}))
                    await ws.close(code=1008)
                    return
            await ws.send_text(json.dumps({"t": "hello", "ok": True, "server": "pfs-infinity", "version": "0.2.0"}))

            # Event loop
            while True:
                m = await ws.receive()
                data = m.get("bytes") or m.get("text", "").encode()
                try:
                    req = json.loads(data.decode("utf-8"))
                except Exception:
                    continue
                if not isinstance(req, dict):
                    continue
                t = req.get("t")
                if t == "roots":
                    roots = [
                        {"id": "objects", "type": "virtual", "description": "Uploaded objects"}
                    ]
                    base = get_browse_root()
                    if base is not None:
                        roots.append({"id": "share", "type": "fs", "root": str(base)})
                    await ws.send_text(json.dumps({"t": "roots", "ok": True, "roots": roots}))
                elif t == "list":
                    root = req.get("root")
                    path = str(req.get("path") or "/")
                    if root != "share":
                        await ws.send_text(json.dumps({"t": "list", "ok": False, "error": "unknown root"}))
                        continue
                    base = get_browse_root()
                    if base is None:
                        await ws.send_text(json.dumps({"t": "list", "ok": False, "error": "no share configured"}))
                        continue
                    target = (base / path.lstrip("/")).resolve()
                    if not is_traversal_safe(base, target) or not target.exists():
                        await ws.send_text(json.dumps({"t": "list", "ok": False, "error": "not found"}))
                        continue
                    entries: List[Dict[str, Any]] = []
                    if target.is_dir():
                        for de in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                            try:
                                st = de.stat()
                            except Exception:
                                continue
                            entries.append({
                                "name": de.name,
                                "is_dir": de.is_dir(),
                                "size": int(st.st_size),
                                "mtime": float(st.st_mtime),
                            })
                    else:
                        st = target.stat()
                        entries.append({
                            "name": target.name,
                            "is_dir": False,
                            "size": int(st.st_size),
                            "mtime": float(st.st_mtime),
                        })
                    await ws.send_text(json.dumps({"t": "list", "ok": True, "entries": entries}))
                elif t == "stat":
                    root = req.get("root")
                    path = str(req.get("path") or "/")
                    if root != "share":
                        await ws.send_text(json.dumps({"t": "stat", "ok": False, "error": "unknown root"}))
                        continue
                    base = get_browse_root()
                    if base is None:
                        await ws.send_text(json.dumps({"t": "stat", "ok": False, "error": "no share configured"}))
                        continue
                    target = (base / path.lstrip("/")).resolve()
                    if not is_traversal_safe(base, target) or not target.exists():
                        await ws.send_text(json.dumps({"t": "stat", "ok": False, "error": "not found"}))
                        continue
                    st = target.stat()
                    await ws.send_text(json.dumps({
                        "t": "stat", "ok": True,
                        "attrs": {
                            "path": str(target),
                            "size": int(st.st_size),
                            "mtime": float(st.st_mtime),
                            "mode": int(st.st_mode),
                            "is_dir": target.is_dir(),
                        }
                    }))
                else:
                    await ws.send_text(json.dumps({"t": "error", "error": "unknown"}))
        except WebSocketDisconnect:
            return
        except Exception:
            try:
                await ws.close()
            except Exception:
                pass
