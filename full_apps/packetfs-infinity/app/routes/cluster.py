from __future__ import annotations

import os
import json
import uuid
import datetime
import subprocess
from pathlib import Path
from typing import List, Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Storage path (var/cluster/hosts.json under repo root by default)
ROOT = Path(__file__).resolve().parents[2]
CLUSTER_DIR = Path(os.environ.get("PFS_CLUSTER_DIR") or (ROOT / "var" / "cluster"))
CLUSTER_FILE = CLUSTER_DIR / "hosts.json"


class HostEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    label: str
    host: str
    user: Optional[str] = None
    ws_port: int = 8811
    https_port: int = 8811
    quic_port: int = 8853
    added_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z")


class HostCreate(BaseModel):
    label: str
    host: str
    user: Optional[str] = None
    ws_port: int = 8811
    https_port: int = 8811
    quic_port: int = 8853


def _find_host(items: List[HostEntry], host: str, user: Optional[str]) -> Optional[int]:
    for i, h in enumerate(items):
        if h.host == host and h.user == user:
            return i
    return None


router = APIRouter()


class BootstrapRequest(BaseModel):
    host: str
    user: Optional[str] = None
    mode: Literal["backend", "native"] = "backend"
    browse_root: str = "/srv/pfs-share"
    ws_port: int = 8811
    psk: Optional[str] = None


def _load_hosts() -> List[HostEntry]:
    try:
        if not CLUSTER_FILE.exists():
            return []
        data = json.loads(CLUSTER_FILE.read_text())
        return [HostEntry(**x) for x in data if isinstance(x, dict)]
    except Exception:
        return []


def _save_hosts(items: List[HostEntry]) -> None:
    CLUSTER_DIR.mkdir(parents=True, exist_ok=True)
    data = [x.model_dump() for x in items]
    tmp = CLUSTER_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(CLUSTER_FILE)


def _ssh_reachable(user: Optional[str], host: str) -> bool:
    target = f"{user}@{host}" if user else host
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
        target,
        "true",
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 255:
            # Older OpenSSH may not support accept-new; retry with no
            cmd2 = [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "StrictHostKeyChecking=no",
                target,
                "true",
            ]
            res = subprocess.run(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False


@router.get("/cluster/hosts", response_model=List[HostEntry])
async def list_hosts():
    return _load_hosts()


@router.post("/cluster/hosts", response_model=HostEntry)
async def add_host(item: HostCreate):
    if not _ssh_reachable(item.user, item.host):
        raise HTTPException(status_code=400, detail="ssh not reachable (keys/agent required)")
    hosts = _load_hosts()
    idx = _find_host(hosts, item.host, item.user)
    if idx is not None:
        # Update existing entry ports/label
        existing = hosts[idx]
        existing.label = item.label or existing.label
        existing.ws_port = item.ws_port
        existing.https_port = item.https_port
        existing.quic_port = item.quic_port
        hosts[idx] = existing
        _save_hosts(hosts)
        return existing
    entry = HostEntry(
        label=item.label,
        host=item.host,
        user=item.user,
        ws_port=item.ws_port,
        https_port=item.https_port,
        quic_port=item.quic_port,
    )
    hosts.append(entry)
    _save_hosts(hosts)
    return entry


@router.post("/cluster/hosts/probe")
async def probe_host(item: HostCreate):
    ok = _ssh_reachable(item.user, item.host)
    return {"reachable": bool(ok)}


@router.post("/cluster/bootstrap/ssh")
async def bootstrap_host(req: BootstrapRequest):
    if not _ssh_reachable(req.user, req.host):
        return {"ok": False, "reachable": False}
    target = f"{req.user}@{req.host}" if req.user else req.host
    psk_env = f"-e PFS_BROWSE_PSK={req.psk}" if req.psk else ""
    script = f"""
set -euo pipefail
if ! command -v podman >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y podman || true
  else
    apt-get update && apt-get install -y podman || true
  fi
fi
mkdir -p '{req.browse_root}' || true
if [ "{req.mode}" = "backend" ]; then
  podman rm -f pfs-infinity >/dev/null 2>&1 || true
  podman run -d --name pfs-infinity -p {req.ws_port}:8811 \
    -v '{req.browse_root}':'{req.browse_root}':Z \
    -e PFS_BROWSE_ROOT='{req.browse_root}' -e PFS_TLS=1 -e PFS_TLS_INSECURE=1 {psk_env} \
    packetfs/pfs-infinity:latest
else
  podman rm -f pfs-native >/dev/null 2>&1 || true
  podman run -d --name pfs-native --privileged --device /dev/fuse -p {req.ws_port}:8811 \
    -v '{req.browse_root}':'{req.browse_root}':Z \
    -e PFS_BROWSE_ROOT='{req.browse_root}' -e PFS_TLS=1 -e PFS_TLS_INSECURE=1 \
    packetfs/pfs-native:latest
fi
"""
    try:
        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            target,
            "bash",
            "-lc",
            "bash -s",
        ]
        res = subprocess.run(cmd, input=script.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ok = res.returncode == 0
        return {"ok": bool(ok), "code": int(res.returncode), "stdout": res.stdout.decode(errors="ignore"), "stderr": res.stderr.decode(errors="ignore")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/cluster/hosts/{host_id}")
async def delete_host(host_id: str):
    hosts = _load_hosts()
    new_hosts = [h for h in hosts if h.id != host_id]
    if len(new_hosts) == len(hosts):
        raise HTTPException(status_code=404, detail="not found")
    _save_hosts(new_hosts)
    return {"status": "ok"}
