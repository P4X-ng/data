from __future__ import annotations

"""Shared application state and in-memory stores.

NOTE: This module intentionally keeps only ephemeral/dev data structures.
Production hardening should replace many of these with persistent or
bounded-size stores.
"""

import asyncio
from typing import Dict, List, Any

# App-scoped state bag for background servers (e.g., QUIC)
APP_STATE: Dict[str, object] = {}

# In-memory blueprint store (replace with real PacketFS-backed store later)
BLUEPRINTS: Dict[str, dict] = {}
# Optional window-hash cache per object_id
WINDOW_HASHES: Dict[str, list] = {}
# Optional preshared VirtualBlob (receiver side)
CURRENT_BLOB: Dict[str, object] = {}

# --- Multitenancy (initial scaffolding) ---
# A single shared master blob is used for all tenants initially (per user request).
# Tenant isolation will occur at the execution / upload sandbox layer (e.g. VMKit VMs)
# rather than per-tenant blob dictionaries for the first iteration.

# In-memory tenant registry (ephemeral). Later: persist minimal metadata + usage.
TENANTS: Dict[str, dict] = {}

def get_tenant_ctx(tenant_id: str) -> dict:
    """Return (and lazily create) a tenant context dict.

    The context currently holds:
      id: tenant identifier
      status: provisioning|ready|suspended
      vm: placeholder for VMKit handle/object (None until started)
      usage: basic counters (bytes_orig, bytes_comp, uploads)

    Future extensions: quota, tier, sandbox policy, delta windows.
    """
    ctx = TENANTS.get(tenant_id)
    if ctx is None:
        ctx = {
            "id": tenant_id,
            "status": "ready",
            "vm": None,            # To be populated by VMKit integration
            "usage": {"bytes_orig": 0, "bytes_comp": 0, "uploads": 0},
        }
        TENANTS[tenant_id] = ctx
    return ctx

async def ensure_tenant_vm(tenant_id: str, *, memory_mb: int = 512, storage_bytes: int = 10 * (1 << 30)) -> dict:
    """Ensure a VM environment exists for a tenant (lazy start).

    Placeholder implementation. When VMKit Python bindings are available, integrate like:
        import vmkit
        vm = vmkit.create(name=tenant_id, storage_size=storage_bytes, memory=memory_mb)
    For now, we just mark a synthetic handle.
    """
    ctx = get_tenant_ctx(tenant_id)
    if ctx.get("vm") is None:
        # TODO: Replace with real vmkit invocation
        ctx["vm"] = {
            "memory_mb": memory_mb,
            "storage_bytes": storage_bytes,
            "handle": f"vmkit:{tenant_id}",
        }
    return ctx

# Transfers
TRANSFERS: Dict[str, object] = {}
# Aggregator for multi-WebSocket transfers on receiver
TRANSFER_WS_AGG: Dict[str, Dict[str, object]] = {}
TRANSFER_WS_LOCK = asyncio.Lock()

# Recent errors (ring buffer)
ERRORS: List[dict] = []
ERRORS_MAX = 200


def record_error(source: str, message: str, **extra: Any) -> None:
    """Add an error entry to the in-memory ring buffer.

    Parameters
    ----------
    source: str
        Logical component (e.g., 'quic', 'ws', 'transfer').
    message: str
        Human-readable description.
    extra: Any
        Arbitrary serializable context (stack, object_id, etc.).
    """
    try:
        entry = {"source": source, "message": message}
        if extra:
            entry.update(extra)
        ERRORS.append(entry)
        if len(ERRORS) > ERRORS_MAX:
            # Trim oldest entries
            del ERRORS[: len(ERRORS) - ERRORS_MAX]
    except Exception:
        # Never raise from error recording
        pass
