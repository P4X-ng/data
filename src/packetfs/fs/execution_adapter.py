"""Execution adapter: stream stored packets through PacketExecutor.
"""
from __future__ import annotations

from typing import Iterable, Any

from packetfs.pcpu import PacketExecutor, PCPUConfig
from .object_index import ObjectIndex


class StoredPacketWrapper:
    __slots__ = ("packet_id", "payload")
    def __init__(self, packet_id: str, payload: memoryview):
        self.packet_id = packet_id
        self.payload = payload


class ObjectExecutor:
    def __init__(self, index: ObjectIndex, execute_fn, cfg: PCPUConfig | None = None):
        self.index = index
        self.execute_fn = execute_fn
        self.cfg = cfg or PCPUConfig()

    def execute_object(self, name: str):
        meta = self.index.get(name)
        packets_iter = self._packet_iter(meta.packet_ids)
        ex = PacketExecutor(lambda pkt: self.execute_fn(pkt.payload), self.cfg)
        ex.execute_packets(packets_iter)
        return ex.finalize()

    def _packet_iter(self, packet_ids: Iterable[str]):
        store = self.index.store
        for pid in packet_ids:
            yield StoredPacketWrapper(pid, store.get(pid))
