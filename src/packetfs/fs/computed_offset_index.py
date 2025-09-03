"""Computed offset index for instruction packets.

Goal: arithmetic (or tiny bounded scan) resolution of instruction -> byte offset
without a hashmap at execution time. Two modes:

STRIDE: all instructions have identical size. offset(i)=base_offset + i*stride.
DELTA_BLOCK: variable sizes; partition instructions into fixed-size blocks.
  - For each block we store an anchor (cumulative offset at block start)
  - Inside a block we store size deltas for each instruction.
  - Lookup: anchor + prefix sum of prior deltas in block. Block span kept small
    (default 64) so a simple Python loop is acceptable; can be optimized later.

Descriptor is serializable for transfer / caching. Remote sides share a seed
and module_id allowing deterministic base_offset randomization while the raw
instruction arena layout stays implicit.

This module is intentionally minimal and free of performance marketing. It is
intended to be replaced or accelerated (e.g. C/FFI) later without changing the
contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Sequence
import hashlib
import struct

MAGIC = b"COIDX1"  # format identifier


class EncodingMode(Enum):
    STRIDE = 0
    DELTA_BLOCK = 1


def _varint_encode(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint encode negative")
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def _varint_decode(buf: bytes, offset: int = 0) -> tuple[int, int]:
    shift = 0
    result = 0
    while True:
        if offset >= len(buf):
            raise ValueError("truncated varint")
        b = buf[offset]
        offset += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
        if shift > 63:
            raise ValueError("varint too long")
    return result, offset


def _hash_bytes(*parts: bytes) -> bytes:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.digest()


def _derive_base_offset(module_id: str, seed: int) -> int:
    seed_bytes = seed.to_bytes(8, 'little', signed=False)
    h = hashlib.sha256(module_id.encode('utf-8') + seed_bytes).digest()
    # Use lower 8 bytes & align to 4KB page
    raw = int.from_bytes(h[:8], 'little')
    return raw & ~0xFFF


@dataclass(frozen=True)
class ModuleDescriptor:
    module_id: str
    version: int
    seed: int
    mode: EncodingMode
    instruction_count: int
    stride_bytes: int | None
    block_span: int | None
    anchors: List[int] | None  # cumulative offsets at block starts (relative)
    deltas: List[List[int]] | None  # per block instruction sizes
    integrity_hash: bytes  # sha256 over canonical payload (excluding magic & hash itself)

    def base_offset(self) -> int:
        return _derive_base_offset(self.module_id, self.seed)

    def offset(self, index: int) -> int:
        if index < 0 or index >= self.instruction_count:
            raise IndexError("instruction index out of range")
        base = self.base_offset()
        if self.mode == EncodingMode.STRIDE:
            assert self.stride_bytes is not None
            return base + index * self.stride_bytes
        # DELTA_BLOCK
        assert self.block_span and self.anchors and self.deltas
        block = index // self.block_span
        inner = index % self.block_span
        anchor = self.anchors[block]
        # Sum sizes of prior instructions in block
        if inner == 0:
            return base + anchor
        sizes = self.deltas[block]
        return base + anchor + sum(sizes[:inner])

    # --- Serialization ---
    def serialize(self) -> bytes:
        parts: List[bytes] = []
        # Header (without magic & final hash yet)
        # version (u16), mode(u8), seed(u64), instruction_count(varint)
        header = struct.pack('<H B Q', self.version, self.mode.value, self.seed)
        parts.append(header)
        parts.append(_varint_encode(self.instruction_count))
        parts.append(_varint_encode(1 if self.stride_bytes is not None else 0))
        if self.stride_bytes is not None:
            parts.append(_varint_encode(self.stride_bytes))
        else:
            # DELTA_BLOCK fields
            assert self.block_span and self.anchors and self.deltas
            parts.append(_varint_encode(self.block_span))
            parts.append(_varint_encode(len(self.anchors)))
            # anchors as varints of relative values
            prev = 0
            for a in self.anchors:
                parts.append(_varint_encode(a - prev))
                prev = a
            # deltas per block (each block length may be shorter for final)
            parts.append(_varint_encode(len(self.deltas)))
            for block_sizes in self.deltas:
                parts.append(_varint_encode(len(block_sizes)))
                for sz in block_sizes:
                    parts.append(_varint_encode(sz))
        # module id and integrity hash placement
        mid_bytes = self.module_id.encode('utf-8')
        parts.append(_varint_encode(len(mid_bytes)))
        parts.append(mid_bytes)
        payload = b''.join(parts)
        integrity = hashlib.sha256(payload).digest()
        return MAGIC + integrity + payload

    @staticmethod
    def deserialize(data: bytes) -> ModuleDescriptor:
        if not data.startswith(MAGIC):
            raise ValueError("bad magic")
        integrity = data[len(MAGIC):len(MAGIC)+32]
        payload = data[len(MAGIC)+32:]
        if hashlib.sha256(payload).digest() != integrity:
            raise ValueError("integrity hash mismatch")
        off = 0
        (version, mode_val, seed) = struct.unpack_from('<H B Q', payload, off)
        off += struct.calcsize('<H B Q')
        instruction_count, off = _varint_decode(payload, off)
        is_stride, off = _varint_decode(payload, off)
        stride_bytes = None
        block_span = None
        anchors = None
        deltas = None
        if is_stride:
            stride_bytes, off = _varint_decode(payload, off)
            mode = EncodingMode.STRIDE
        else:
            block_span, off = _varint_decode(payload, off)
            anchor_count, off = _varint_decode(payload, off)
            anchors = []
            cumulative = 0
            for _ in range(anchor_count):
                delta, off = _varint_decode(payload, off)
                cumulative += delta
                anchors.append(cumulative)
            deltas_block_count, off = _varint_decode(payload, off)
            deltas = []
            for _ in range(deltas_block_count):
                blen, off2 = _varint_decode(payload, off)
                off = off2
                sizes = []
                for _ in range(blen):
                    sz, off = _varint_decode(payload, off)
                    sizes.append(sz)
                deltas.append(sizes)
            mode = EncodingMode.DELTA_BLOCK
        # module id
        mid_len, off = _varint_decode(payload, off)
        module_id = payload[off:off+mid_len].decode('utf-8')
        off += mid_len
        return ModuleDescriptor(
            module_id=module_id,
            version=version,
            seed=seed,
            mode=mode,
            instruction_count=instruction_count,
            stride_bytes=stride_bytes,
            block_span=block_span,
            anchors=anchors,
            deltas=deltas,
            integrity_hash=integrity,
        )


class ComputedOffsetIndexBuilder:
    """Builder that ingests instruction sizes then emits a ModuleDescriptor.

    Usage:
        b = ComputedOffsetIndexBuilder(module_id="modA", version=1, seed=123)
        for sz in sizes: b.add_size(sz)
        desc = b.build()
    """

    def __init__(self, module_id: str, version: int, seed: int, block_span: int = 64):
        if block_span <= 0:
            raise ValueError("block_span must be positive")
        self.module_id = module_id
        self.version = version
        self.seed = seed
        self.block_span = block_span
        self._sizes: List[int] = []

    def add_size(self, size: int):
        if size <= 0:
            raise ValueError("instruction size must be >0")
        self._sizes.append(size)

    def add_sizes(self, sizes: Sequence[int]):
        for s in sizes:
            self.add_size(s)

    def build(self) -> ModuleDescriptor:
        if not self._sizes:
            raise ValueError("no instruction sizes added")
        # Detect stride
        first = self._sizes[0]
        if all(s == first for s in self._sizes):
            return ModuleDescriptor(
                module_id=self.module_id,
                version=self.version,
                seed=self.seed,
                mode=EncodingMode.STRIDE,
                instruction_count=len(self._sizes),
                stride_bytes=first,
                block_span=None,
                anchors=None,
                deltas=None,
                integrity_hash=b"",  # filled in serialize but keep placeholder
            )
        # Build delta block representation
        anchors: List[int] = []
        deltas: List[List[int]] = []
        cumulative = 0
        sizes = self._sizes
        for i in range(0, len(sizes), self.block_span):
            anchors.append(cumulative)
            block = sizes[i:i+self.block_span]
            deltas.append(list(block))
            cumulative += sum(block)
        return ModuleDescriptor(
            module_id=self.module_id,
            version=self.version,
            seed=self.seed,
            mode=EncodingMode.DELTA_BLOCK,
            instruction_count=len(sizes),
            stride_bytes=None,
            block_span=self.block_span,
            anchors=anchors,
            deltas=deltas,
            integrity_hash=b"",
        )


__all__ = [
    'EncodingMode',
    'ModuleDescriptor',
    'ComputedOffsetIndexBuilder'
]
