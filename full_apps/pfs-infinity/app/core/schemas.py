from __future__ import annotations

from pydantic import BaseModel
from typing import Dict, Optional, Literal


class ObjectRef(BaseModel):
    object_id: str


class Peer(BaseModel):
    host: str
    udp_port: int = 8853
    tcp_port: int = 8433
    https_port: int = 8443
    ws_port: Optional[int] = None  # defaults to https_port if None


class TransferRequest(BaseModel):
    object_id: str
    mode: Literal["auto", "quic", "webrtc", "ws", "ws-multi", "tcp", "bytes"] = "auto"
    peer: Peer
    timeout_s: float = 5.0
    force_cross_arch: bool = False


class TransferStatus(BaseModel):
    transfer_id: str
    state: Literal["pending", "running", "success", "failed"]
    # details may include metrics like object_size, plan_bytes, elapsed_s, eff_bytes_per_s, plan_bytes_per_s, speedup_vs_raw, path
    details: Dict[str, float | int | str | None] = {}


class BlobSetup(BaseModel):
    name: str
    size_bytes: int
    seed: int = 1337


class SDP(BaseModel):
    sdp: str
    type: Literal["offer", "answer"] = "offer"
