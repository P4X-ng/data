from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple
from fastapi import Header, HTTPException, status


def get_browse_root() -> Optional[Path]:
    """Return the sandboxed root for filesystem browsing.
    Prefers PFS_BROWSE_ROOT; falls back to PFS_SHARE_DIR.
    Returns None if not configured.
    """
    root = os.environ.get("PFS_BROWSE_ROOT") or os.environ.get("PFS_SHARE_DIR")
    if not root:
        return None
    try:
        p = Path(root).resolve()
        if p.exists() and p.is_dir():
            return p
    except Exception:
        return None
    return None


def is_traversal_safe(base: Path, target: Path) -> bool:
    """Ensure target is within base after resolution."""
    try:
        base_r = base.resolve()
        targ_r = target.resolve()
        try:
            targ_r.relative_to(base_r)
            return True
        except Exception:
            return False
    except Exception:
        return False


def dev_enabled() -> bool:
    return os.environ.get("PFS_DEV", "0") in ("1", "true", "TRUE", "True") or os.environ.get("APP_ENV") == "dev"


async def psk_required(x_pfs_psk: Optional[str] = Header(default=None)) -> None:
    """Optional PSK gate: if PFS_BROWSE_PSK is set, require matching header.
    Attach as a FastAPI dependency to guard endpoints.
    """
    want = os.environ.get("PFS_BROWSE_PSK")
    if not want:
        return
    if not x_pfs_psk or x_pfs_psk != want:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def parse_range(range_header: str, size: int) -> Tuple[int, int]:
    """Parse a single HTTP Range header of the form 'bytes=start-end'.
    Returns (start, end) inclusive. Raises HTTPException on invalid.
    """
    if not range_header:
        raise HTTPException(status_code=416, detail="invalid range")
    if not range_header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="invalid range unit")
    spec = range_header[len("bytes=") :].strip()
    if "," in spec:
        # We only support a single range
        raise HTTPException(status_code=416, detail="multiple ranges not supported")
    if "-" not in spec:
        raise HTTPException(status_code=416, detail="invalid range spec")
    start_s, end_s = spec.split("-", 1)
    if start_s == "":
        # suffix range: last N bytes
        try:
            n = int(end_s)
        except Exception:
            raise HTTPException(status_code=416, detail="invalid range bounds")
        if n <= 0:
            raise HTTPException(status_code=416, detail="invalid range bounds")
        start = max(size - n, 0)
        end = size - 1
    else:
        try:
            start = int(start_s)
        except Exception:
            raise HTTPException(status_code=416, detail="invalid range bounds")
        if end_s == "":
            end = size - 1
        else:
            try:
                end = int(end_s)
            except Exception:
                raise HTTPException(status_code=416, detail="invalid range bounds")
        if start < 0 or end < start:
            raise HTTPException(status_code=416, detail="invalid range bounds")
        if start >= size:
            # Not satisfiable
            raise HTTPException(status_code=416, detail="range not satisfiable")
        end = min(end, size - 1)
    return start, end
