from __future__ import annotations
"""Sandbox adapter abstraction for tenant execution environments.

Initial implementation provides a no-op (in-process) sandbox. A future
VMKit-backed implementation can be added without changing calling code.

Env flags:
  PFS_SANDBOX_IMPL = 'none' (default) | 'vmkit'

Public functions kept minimal for now:
  get_sandbox(tenant_id) -> Sandbox
  ensure_started(tenant_id) -> Sandbox

A Sandbox exposes:
  .tenant_id
  .impl (string implementation id)
  .status ('ready'|'starting'|'error')
  .meta (dict with impl-specific details)

Lifecycle operations are intentionally light; uploads just ensure sandbox
exists (lazy start) and record usage metrics. Real isolation hooks (process
namespaces, VMKit CLI calls, etc.) bolt on here later.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
import os
import asyncio

from app.core.state import get_tenant_ctx

@dataclass
class Sandbox:
    tenant_id: str
    impl: str
    status: str = "ready"
    meta: Dict[str, Any] = field(default_factory=dict)

_SANDBOXES: Dict[str, Sandbox] = {}
_SANDBOX_LOCK = asyncio.Lock()

async def ensure_started(tenant_id: str) -> Sandbox:
    """Ensure a sandbox exists (lazy create)."""
    impl = os.environ.get("PFS_SANDBOX_IMPL", "none").lower()
    async with _SANDBOX_LOCK:
        sb = _SANDBOXES.get(tenant_id)
        if sb:
            return sb
        if impl == "vmkit":
            # Placeholder; integrate real vmkit invocation here
            sb = Sandbox(tenant_id=tenant_id, impl="vmkit", status="ready", meta={"note": "vmkit stub"})
        else:
            sb = Sandbox(tenant_id=tenant_id, impl="none", status="ready")
        _SANDBOXES[tenant_id] = sb
    # Link into tenant ctx for visibility
    ctx = get_tenant_ctx(tenant_id)
    ctx["vm"] = {"impl": impl, "status": sb.status, **sb.meta}
    return sb

async def get_sandbox(tenant_id: str) -> Optional[Sandbox]:
    return _SANDBOXES.get(tenant_id)
