"""
Shared application state and in-memory stores.
"""
from __future__ import annotations

import asyncio
from typing import Dict

# App-scoped state bag for background servers (e.g., QUIC)
APP_STATE: Dict[str, object] = {}

# MVP: in-memory blueprint store (replace with real PacketFS-backed store later)
BLUEPRINTS: Dict[str, dict] = {}
# Optional window-hash cache per object_id
WINDOW_HASHES: Dict[str, list] = {}
# Optional preshared VirtualBlob (receiver side)
CURRENT_BLOB: Dict[str, object] = {}

# Transfers
TRANSFERS: Dict[str, object] = {}
# Aggregator for multi-WebSocket transfers on receiver
TRANSFER_WS_AGG: Dict[str, Dict[str, object]] = {}
TRANSFER_WS_LOCK = asyncio.Lock()
