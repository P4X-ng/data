from __future__ import annotations

import hashlib
import os
import json
from fastapi import APIRouter, UploadFile, File, HTTPException
import logging

from app.core.schemas import ObjectRef, ObjectUploadResponse
from app.core.state import BLUEPRINTS, WINDOW_HASHES, APP_STATE, get_tenant_ctx
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


@router.post("/objects", response_model=ObjectUploadResponse)
async def create_object(file: UploadFile = File(...)):
    # Tenant resolution (header-based prototype; later token/auth integration)
    from fastapi import Request
    import inspect
    tenant_id = "public"
    # Attempt to pull request from current stack (FastAPI dependency not added to avoid breaking schema)
    try:
        for frame in inspect.stack():  # pragma: no cover - introspection path
            loc = frame.frame.f_locals
            if "request" in loc:
                req = loc["request"]
                try:
                    tenant_hdr = req.headers.get("X-Tenant-ID")  # type: ignore[attr-defined]
                    if tenant_hdr:
                        tenant_id = tenant_hdr.strip()[:64]
                except Exception:
                    pass
                break
    except Exception:
        pass
    # Ensure tenant context + sandbox (non-blocking aside from first creation)
    try:
        from app.sandbox.adapter import ensure_started  # type: ignore
        await ensure_started(tenant_id)
    except Exception:
        pass
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    sha256 = hashlib.sha256(data).hexdigest()
    obj_id = f"sha256:{sha256}"

    # PacketFS: write bytes into VirtualBlob and build IPROG with BREF (and PVRT BREF-only)
    seg_count = 0
    fallback_error: Exception | None = None
    # Enforce PacketFS by default; allow explicit fallback via env flag
    allow_fallback = os.environ.get("PFS_ALLOW_FALLBACK", "0") in ("1","true","TRUE","True")
    try:
        from packetfs.filesystem.blob_fs import BlobFS, BlobConfig  # type: ignore
        from packetfs.filesystem.iprog import build_iprog_for_file_bytes, BlobFingerprint  # type: ignore
        # Prefer already-attached CURRENT_BLOB (ensures size matches actual shared memory)
        try:
            from app.core.state import CURRENT_BLOB  # lazy import to avoid cycle
        except Exception:
            CURRENT_BLOB = {}
        if CURRENT_BLOB and isinstance(CURRENT_BLOB, dict) and CURRENT_BLOB.get("name"):
            blob_name = str(CURRENT_BLOB.get("name"))
            blob_size = int(CURRENT_BLOB.get("size", 0))
            blob_seed = int(CURRENT_BLOB.get("seed", 0))
        else:
            # Fallback to env (mirror startup clamp logic to avoid size mismatch RuntimeError)
            blob_name = os.environ.get("PFS_BLOB_NAME", "pfs_vblob")
            raw_size = int(os.environ.get("PFS_BLOB_SIZE_BYTES", str(1 << 30)))
            # Default clamp to 1 GiB to match app startup and Justfile docs
            max_size = int(os.environ.get("PFS_BLOB_MAX_SIZE", str(1 << 30)))
            blob_size = raw_size if raw_size <= max_size else max_size
            blob_seed = int(os.environ.get("PFS_BLOB_SEED", "1337"))
        meta_dir = os.environ.get("PFS_META_DIR", "/app/meta")
        os.makedirs(meta_dir, exist_ok=True)
        cfg = BlobConfig(name=blob_name, size_bytes=blob_size, seed=blob_seed, meta_dir=meta_dir)
        fs = BlobFS(cfg)
        segs = fs.write_bytes(data)
        seg_count = len(segs) if isinstance(segs, list) else 0
        fs.record_object(obj_id, len(data), sha256, 65536, segs)
        fp = BlobFingerprint(name=blob_name, size=blob_size, seed=blob_seed)
        # Include PVRT BREF-only so sender can transmit tiny PVRT
        iprog = build_iprog_for_file_bytes(data, file.filename or obj_id, fp, segs, window_size=65536, include_pvrt=True)
        fs.close()
    except Exception as e:
        fallback_error = e
        if not allow_fallback:
            # Strict mode: require PacketFS; surface clear error
            raise HTTPException(status_code=500, detail=f"PacketFS pipeline error: {e.__class__.__name__}: {e}")
        # Legacy fallback: minimal plan when explicitly allowed
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
            "metrics": {"pvrt_total": len(data), "tx_ratio": 1.0, "fallback_reason": f"{e.__class__.__name__}: {e}"},
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

    # Extract transmission metrics for UI (pvrt_total ~= blueprint bytes on wire)
    metrics = {}
    try:
        metrics = iprog.get("metrics", {}) if isinstance(iprog, dict) else {}
    except Exception:
        metrics = {}
    pvrt_total = int(metrics.get("pvrt_total", 0)) if isinstance(metrics, dict) else 0
    tx_ratio = float(metrics.get("tx_ratio", 0.0)) if isinstance(metrics, dict) else 0.0
    if (not tx_ratio) and pvrt_total and len(data):
        try:
            tx_ratio = pvrt_total / float(len(data))
            metrics["tx_ratio"] = tx_ratio
        except Exception:
            pass

    # Aggregate compression stats in APP_STATE (global + per-tenant)
    try:
        stats = APP_STATE.setdefault("COMPRESSION_STATS", {"total_original": 0, "total_transmitted": 0, "uploads": 0, "per_tenant": {}})  # type: ignore[assignment]
        transmitted = pvrt_total if pvrt_total > 0 else len(data)
        stats["total_original"] += len(data)
        stats["total_transmitted"] += transmitted
        stats["uploads"] += 1
        # Per-tenant aggregation
        pt = stats["per_tenant"].setdefault(tenant_id, {"total_original": 0, "total_transmitted": 0, "uploads": 0})
        pt["total_original"] += len(data)
        pt["total_transmitted"] += transmitted
        pt["uploads"] += 1
        # Update tenant ctx usage counters
        try:
            tctx = get_tenant_ctx(tenant_id)
            usage = tctx.setdefault("usage", {"bytes_orig": 0, "bytes_comp": 0, "uploads": 0})
            usage["bytes_orig"] += len(data)
            usage["bytes_comp"] += transmitted
            usage["uploads"] += 1
        except Exception:
            pass
    except Exception:
        pass

    # Optional verbose compression logging
    if os.environ.get("PFS_COMPRESSION_DEBUG") == "1":
        clog = logging.getLogger("compression")
        try:
            blob_meta = {}
            try:
                from app.core.state import CURRENT_BLOB  # type: ignore
                if isinstance(CURRENT_BLOB, dict):
                    blob_meta = {k: CURRENT_BLOB.get(k) for k in ("name", "size", "seed", "id") if CURRENT_BLOB.get(k) is not None}
            except Exception:
                pass
            clog.info(
                "upload_compression object_id=%s file=%s size=%d pvrt_total=%d tx_ratio=%.6f segs=%d fallback=%s blob=%s",
                obj_id,
                file.filename or obj_id,
                len(data),
                pvrt_total,
                tx_ratio or 0.0,
                seg_count,
                bool(fallback_error),
                json.dumps(blob_meta, separators=(",", ":")),
            )
            if fallback_error:
                clog.warning("compression_fallback object_id=%s error=%s", obj_id, repr(fallback_error))
            if tx_ratio >= 0.98:
                clog.warning("low_compression object_id=%s ratio=%.4f hint='Check blob mismatch or small file'", obj_id, tx_ratio)
        except Exception:
            pass

    return {
        "object_id": obj_id,
        "size": len(data),
        "sha256": sha256,
        "compressed_size": pvrt_total or None,
        "tx_ratio": tx_ratio or None,
    }


@router.get("/compression/stats")
async def compression_stats():
    stats = APP_STATE.get("COMPRESSION_STATS")
    if not isinstance(stats, dict):
        return {"total_original": 0, "total_transmitted": 0, "saved_bytes": 0, "saved_percent": 0.0, "uploads": 0}
    tot_o = int(stats.get("total_original", 0))
    tot_t = int(stats.get("total_transmitted", 0))
    saved = max(0, tot_o - tot_t)
    saved_pct = (saved / tot_o * 100.0) if tot_o else 0.0
    resp = {"total_original": tot_o, "total_transmitted": tot_t, "saved_bytes": saved, "saved_percent": saved_pct, "uploads": int(stats.get("uploads", 0))}
    # Include per-tenant summary if present (omit raw internals to reduce payload)
    per_tenant = stats.get("per_tenant") if isinstance(stats.get("per_tenant"), dict) else None
    if per_tenant:
        brief = {}
        for tid, tstat in per_tenant.items():
            try:
                o = int(tstat.get("total_original", 0))
                t = int(tstat.get("total_transmitted", 0))
                sv = max(0, o - t)
                pct = (sv / o * 100.0) if o else 0.0
                brief[tid] = {"total_original": o, "total_transmitted": t, "saved_bytes": sv, "saved_percent": pct, "uploads": int(tstat.get("uploads", 0))}
            except Exception:
                continue
        resp["per_tenant"] = brief
    return resp


@router.get("/tenants")
async def list_tenants():
    from app.core.state import TENANTS  # lazy import to avoid cycles
    out = []
    for tid, ctx in TENANTS.items():
        if not isinstance(ctx, dict):
            continue
        usage = ctx.get("usage", {}) if isinstance(ctx.get("usage"), dict) else {}
        o = int(usage.get("bytes_orig", 0))
        c = int(usage.get("bytes_comp", 0))
        saved = max(0, o - c)
        pct = (saved / o * 100.0) if o else 0.0
        out.append({
            "tenant_id": tid,
            "status": ctx.get("status", "unknown"),
            "uploads": int(usage.get("uploads", 0)),
            "bytes_original": o,
            "bytes_transmitted": c,
            "saved_bytes": saved,
            "saved_percent": pct,
        })
    return sorted(out, key=lambda x: x["tenant_id"])


@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str):
    from app.core.state import TENANTS
    ctx = TENANTS.get(tenant_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="tenant not found")
    usage = ctx.get("usage", {}) if isinstance(ctx.get("usage"), dict) else {}
    o = int(usage.get("bytes_orig", 0))
    c = int(usage.get("bytes_comp", 0))
    saved = max(0, o - c)
    pct = (saved / o * 100.0) if o else 0.0
    return {
        "tenant_id": tenant_id,
        "status": ctx.get("status", "unknown"),
        "uploads": int(usage.get("uploads", 0)),
        "bytes_original": o,
        "bytes_transmitted": c,
        "saved_bytes": saved,
        "saved_percent": pct,
        "vm": ctx.get("vm"),
    }


@router.get("/objects", tags=["objects"])
async def list_objects():
    out = []
    for k, v in list(BLUEPRINTS.items()):
        if not isinstance(v, dict):
            continue
        if "sha256" in v and "size" in v:
            fname = v.get("filename") or None
            sha = str(v.get("sha256", ""))
            sha_short = sha[:12] if sha else ""
            stored_name = (f"{fname}.{sha_short}" if fname and sha_short else None)
            # Extract metrics if present
            iprog = v.get("iprog") if isinstance(v, dict) else None
            metrics = iprog.get("metrics", {}) if isinstance(iprog, dict) else {}
            compressed_size = int(metrics.get("pvrt_total", 0)) if isinstance(metrics, dict) else None
            tx_ratio = float(metrics.get("tx_ratio", 0.0)) if isinstance(metrics, dict) else None
            out.append({
                "object_id": k,
                "size": int(v.get("size", 0)),
                "sha256": sha,
                "filename": fname,
                "stored_name": stored_name,
                "compressed_size": compressed_size,
                "tx_ratio": tx_ratio,
            })
    return sorted(out, key=lambda x: x.get("object_id", ""))


@router.get("/objects/{object_id}")
async def get_object(object_id: str):
    bp = BLUEPRINTS.get(object_id)
    if not bp:
        raise HTTPException(status_code=404, detail="not found")
    return {"object_id": object_id, "size": bp["size"], "sha256": bp["sha256"]}

@router.get("/objects/{object_id}/iprog")
async def get_object_iprog(object_id: str):
    bp = BLUEPRINTS.get(object_id)
    if not bp or not isinstance(bp, dict) or not isinstance(bp.get("iprog"), dict):
        raise HTTPException(status_code=404, detail="iprog not found")
    return bp["iprog"]


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
    # Prefer original filename; fall back to object_id.bin
    fname = (bp.get("filename") or "").strip() if isinstance(bp, dict) else ""
    if not fname:
        fname = f"{object_id.replace(':', '_')}.bin"
    headers = {
        "Content-Length": str(len(data)),
        "Content-Disposition": f"attachment; filename={fname}",
    }
    return StreamingResponse(it(), media_type="application/octet-stream", headers=headers)
