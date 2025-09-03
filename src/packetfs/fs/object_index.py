"""ObjectIndex maps logical objects to ordered packet ids.

This sits above a PacketStore implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Iterable
import math

from .packet_store import InMemoryPacketStore, PacketRecord


@dataclass(frozen=True)
class ObjectMeta:
    object_id: str
    size: int
    packet_ids: List[str]
    mtu: int


class ObjectIndex:
    def __init__(self, store: InMemoryPacketStore | None = None):
        self.store = store or InMemoryPacketStore()
        self._objects: Dict[str, ObjectMeta] = {}

    def ingest_bytes(self, name: str, data: bytes, mtu: int = 1024) -> ObjectMeta:
        if name in self._objects:
            raise ValueError("object already exists")
        packet_ids: List[str] = []
        for off in range(0, len(data), mtu):
            chunk = data[off:off+mtu]
            rec = self.store.append(chunk)
            packet_ids.append(rec.packet_id)
        meta = ObjectMeta(object_id=name, size=len(data), packet_ids=packet_ids, mtu=mtu)
        self._objects[name] = meta
        return meta

    def get(self, name: str) -> ObjectMeta:
        return self._objects[name]

    def iter_packet_ids(self, name: str):
        return iter(self._objects[name].packet_ids)

    def stats(self) -> dict:
        total_packets = sum(len(m.packet_ids) for m in self._objects.values())
        return {
            'object_count': len(self._objects),
            'total_packets': total_packets,
            'store': self.store.stats(),
        }
