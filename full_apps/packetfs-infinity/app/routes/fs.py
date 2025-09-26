from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.state import APP_STATE

router = APIRouter(prefix="/api/fs", tags=["fs"])

# In-memory stores in APP_STATE
# FS_SOURCES: Dict[str, Dict]
# FS_WORKSPACES: Dict[str, Dict]
# JOBS: Dict[str, Dict]

def _now_ts() -> float:
    return time.time()


def _jobs() -> Dict[str, Dict]:
    return APP_STATE.setdefault("JOBS", {})  # type: ignore


def _sources() -> Dict[str, Dict]:
    return APP_STATE.setdefault("FS_SOURCES", {})  # type: ignore


def _workspaces() -> Dict[str, Dict]:
    return APP_STATE.setdefault("FS_WORKSPACES", {})  # type: ignore


class SourceAddRequest(BaseModel):
    device: str = Field(..., description="Block device, e.g., /dev/sda1")
    label: str = Field(..., description="Short label for the source, becomes namespace path")
    watch: bool = Field(False, description="Enable continuous sync (requires inotify-tools on host)")
    mount_path: Optional[str] = Field(None, description="Host mount path override (read-only)")
    target: Optional[str] = Field(None, description="Cluster target host:port; defaults to local service")


class SourceSyncRequest(BaseModel):
    label: str


class WorkspaceCreateRequest(BaseModel):
    name: str
    lowers: List[str] = Field(..., description="List of source labels to union")


@router.get("/sources")
def list_sources():
    items = []
    for label, rec in _sources().items():
        items.append({
            "label": label,
            "device": rec.get("device"),
            "host_mount": rec.get("host_mount"),
            "pfspath": rec.get("pfspath"),
            "watch": rec.get("watch", False),
            "last_sync": rec.get("last_sync"),
            "status": rec.get("status", "unknown"),
            "error": rec.get("error"),
        })
    return {"sources": items}


@router.post("/sources")
def add_source(req: SourceAddRequest):
    label = req.label
    if label in _sources():
        raise HTTPException(status_code=409, detail="Source already exists")

    # Compute defaults
    mnt = req.mount_path or f"/mnt/{label}_ro"
    # Path where the cluster exposes it (separate dir model)
    pfspath = f"/mnt/packetfs/{label}"

    # Prepare a job suggestion (we do not auto-run host-level mounts here)
    cmd = f"just add-filesystem device={req.device} name={label} mnt={mnt}"
    if req.target:
        cmd += f" target={req.target}"
    if req.watch:
        cmd = f"WATCH=1 {cmd}"

    job_id = str(uuid.uuid4())
    _jobs()[job_id] = {
        "id": job_id,
        "type": "add_source",
        "created": _now_ts(),
        "status": "pending",
        "suggested_command": cmd,
        "output": [],
        "error": None,
    }

    # Record the source immediately with pending status
    _sources()[label] = {
        "device": req.device,
        "host_mount": mnt,
        "pfspath": pfspath,
        "watch": bool(req.watch),
        "last_sync": None,
        "status": "pending",
        "error": None,
        "job_id": job_id,
    }

    # We mark as suggested (pending) so the UI can offer a terminal to run the command
    return {"job_id": job_id, "suggested_command": cmd}


@router.post("/sources/sync")
def sync_source(req: SourceSyncRequest):
    rec = _sources().get(req.label)
    if not rec:
        raise HTTPException(status_code=404, detail="Unknown source")

    device = rec.get("device")
    mnt = rec.get("host_mount")
    label = req.label
    # Suggest the sync command (pfsrsync run)
    cmd = f"pfsrsync {mnt} localhost:8811:/mnt/packetfs/{label} --compress"

    job_id = str(uuid.uuid4())
    _jobs()[job_id] = {
        "id": job_id,
        "type": "sync_source",
        "created": _now_ts(),
        "status": "pending",
        "suggested_command": cmd,
        "output": [],
        "error": None,
    }
    rec["status"] = "pending"
    rec["job_id"] = job_id
    return {"job_id": job_id, "suggested_command": cmd}


@router.delete("/sources/{label}")
def remove_source(label: str):
    rec = _sources().get(label)
    if not rec:
        raise HTTPException(status_code=404, detail="Unknown source")

    # We don’t auto-unmount; suggest an unmount
    mnt = rec.get("host_mount")
    cmd = f"just fs-unmount mnt={mnt}"
    job_id = str(uuid.uuid4())
    _jobs()[job_id] = {
        "id": job_id,
        "type": "remove_source",
        "created": _now_ts(),
        "status": "pending",
        "suggested_command": cmd,
        "output": [],
        "error": None,
    }
    # Tentatively mark for removal; UI should execute unmount
    rec["status"] = "remove_pending"
    rec["job_id"] = job_id
    return {"job_id": job_id, "suggested_command": cmd}


@router.get("/workspaces")
def list_workspaces():
    items = []
    for name, rec in _workspaces().items():
        items.append({
            "name": name,
            "pfspath": rec.get("pfspath"),
            "lowers": rec.get("lowers", []),
            "upperdir": rec.get("upperdir"),
            "status": rec.get("status", "unknown"),
            "error": rec.get("error"),
        })
    return {"workspaces": items}


@router.post("/workspaces")
def create_workspace(req: WorkspaceCreateRequest):
    name = req.name
    if name in _workspaces():
        raise HTTPException(status_code=409, detail="Workspace already exists")

    lowers = req.lowers
    # Provide a suggested just command to implement overlay from synced native dirs
    # Here we assume synchronized sinks live under /var/lib/packetfs/ingest/<label>
    lowerdirs = ":".join([f"/var/lib/packetfs/ingest/{l}" for l in lowers])
    upperdir = f"/var/lib/packetfs/workspaces/{name}/upper"
    workdir = f"/var/lib/packetfs/workspaces/{name}/work"
    mountpoint = f"/mnt/packetfs/workspaces/{name}"

    cmd = (
        "sudo mkdir -p "
        + upperdir
        + " "
        + workdir
        + f" {mountpoint} && "
        + f"sudo mount -t overlay overlay -o lowerdir={lowerdirs},upperdir={upperdir},workdir={workdir} {mountpoint}"
    )

    job_id = str(uuid.uuid4())
    _jobs()[job_id] = {
        "id": job_id,
        "type": "create_workspace",
        "created": _now_ts(),
        "status": "pending",
        "suggested_command": cmd,
        "output": [],
        "error": None,
    }

    _workspaces()[name] = {
        "pfspath": mountpoint,
        "lowers": lowers,
        "upperdir": upperdir,
        "workdir": workdir,
        "status": "pending",
        "job_id": job_id,
        "error": None,
    }

    return {"job_id": job_id, "suggested_command": cmd}


@router.delete("/workspaces/{name}")
def remove_workspace(name: str):
    rec = _workspaces().get(name)
    if not rec:
        raise HTTPException(status_code=404, detail="Unknown workspace")
    mnt = rec.get("pfspath")
    cmd = f"sudo umount {mnt} && sudo rm -rf /var/lib/packetfs/workspaces/{name}"
    job_id = str(uuid.uuid4())
    _jobs()[job_id] = {
        "id": job_id,
        "type": "remove_workspace",
        "created": _now_ts(),
        "status": "pending",
        "suggested_command": cmd,
        "output": [],
        "error": None,
    }
    rec["status"] = "remove_pending"
    rec["job_id"] = job_id
    return {"job_id": job_id, "suggested_command": cmd}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = _jobs().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job")
    return job
