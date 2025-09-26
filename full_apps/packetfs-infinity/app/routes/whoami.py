from __future__ import annotations

import os
from typing import Dict
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/whoami")
async def whoami(request: Request) -> Dict[str, str]:
    # Determine server URL as seen by the client
    scheme = request.url.scheme
    host_hdr = request.headers.get("host") or "localhost:8811"
    server_url = f"{scheme}://{host_hdr}"
    ws_port = os.environ.get("WS_PORT", "8811")
    net_mode = os.environ.get("PFS_NET", "bridge")
    hostname = os.uname().nodename if hasattr(os, "uname") else os.environ.get("HOSTNAME", "unknown")
    return {
        "server_url": server_url,
        "ws_port": str(ws_port),
        "net_mode": net_mode,
        "hostname": hostname,
    }