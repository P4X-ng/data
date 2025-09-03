"""Packet storage abstraction.

Initial in-memory + (optional) mmap-backed packet store.
No marketing claims; only real metrics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Optional
import time
import hashlib
import os
import mmap


@dataclass(frozen=True)
class PacketRecord:
    packet_id: str
    size: int
    offset: int
    storage: str  # 'memory' or file path


class InMemoryPacketStore:
    """Simple append-only in-memory packet store.

    Optionally content-addressed if enable_hash_ids=True.
    """
    def __init__(self, enable_hash_ids: bool = True):
        self._data: Dict[str, bytes] = {}
        self.enable_hash_ids = enable_hash_ids
        self._count = 0
        self._bytes = 0
        self._created_ns = time.time_ns()

    def _make_id(self, payload: bytes) -> str:
        if self.enable_hash_ids:
            return hashlib.sha256(payload).hexdigest()[:32]
        self._count += 1
        return f"pkt{self._count}"

    def append(self, payload: bytes) -> PacketRecord:
        pid = self._make_id(payload)
        if pid in self._data:
            # Deduplicate silently if hash matches
            return PacketRecord(packet_id=pid, size=len(payload), offset=0, storage='memory')
        self._data[pid] = payload
        self._bytes += len(payload)
        return PacketRecord(packet_id=pid, size=len(payload), offset=0, storage='memory')

    def get(self, packet_id: str) -> memoryview:
        return memoryview(self._data[packet_id])

    def stats(self) -> dict:
        return {
            'packet_count': len(self._data),
            'total_bytes': self._bytes,
            'uptime_sec': (time.time_ns() - self._created_ns) / 1e9
        }


class MMapPacketStore:
    """Very simple linear append log using a single mmap file.

    Not concurrent-write safe (coarse usage for prototyping).
    Index kept in-memory only for now.
    """
    def __init__(self, path: str, capacity_bytes: int = 64 * 1024 * 1024, enable_hash_ids: bool = True):
        self.path = path
        self.capacity = capacity_bytes
        self.enable_hash_ids = enable_hash_ids
        self._fd = os.open(path, os.O_RDWR | os.O_CREAT)
        os.ftruncate(self._fd, capacity_bytes)
        self._mm = mmap.mmap(self._fd, capacity_bytes)
        self._write_off = 0
        self._index: Dict[str, PacketRecord] = {}
        self._created_ns = time.time_ns()

    def _make_id(self, payload: bytes) -> str:
        if self.enable_hash_ids:
            return hashlib.sha256(payload).hexdigest()[:32]
        return f"pkt{len(self._index)+1}"

    def append(self, payload: bytes) -> PacketRecord:
        pid = self._make_id(payload)
        if pid in self._index:
            return self._index[pid]
        sz = len(payload)
        if self._write_off + sz > self.capacity:
            raise RuntimeError("packet store full")
        self._mm.seek(self._write_off)
        self._mm.write(payload)
        rec = PacketRecord(packet_id=pid, size=sz, offset=self._write_off, storage=self.path)
        self._index[pid] = rec
        self._write_off += sz
        return rec

    def get(self, packet_id: str) -> memoryview:
        rec = self._index[packet_id]
        self._mm.seek(rec.offset)
        data = self._mm.read(rec.size)
        return memoryview(data)

    def stats(self) -> dict:
        return {
            'packet_count': len(self._index),
            'used_bytes': self._write_off,
            'capacity_bytes': self.capacity,
            'uptime_sec': (time.time_ns() - self._created_ns) / 1e9
        }

    def close(self):
        self._mm.close()
        os.close(self._fd)
