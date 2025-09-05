#!/usr/bin/env python3
"""
VirtualBlob: deterministic, shared-memory resident blob for PacketFS blueprint mode.

- Backed by multiprocessing.shared_memory for local-machine shared access
- Deterministic fill using a seeded xorshift32-based generator
- Supports efficient slicing via memoryview

Usage:
    vb = VirtualBlob(name="pfs_vblob_test", size_bytes=100*1024*1024, seed=1337)
    vb.create_or_attach(create=True)
    vb.ensure_filled()
    data = vb.read(0, 4096)
    vb.close()
"""
from __future__ import annotations

import hashlib
import mmap
from multiprocessing import shared_memory
from typing import Optional


class VirtualBlob:
    def __init__(self, name: str, size_bytes: int, seed: int):
        if size_bytes <= 0:
            raise ValueError("size_bytes must be > 0")
        self.name = name
        self.size = int(size_bytes)
        self.seed = int(seed) & 0xFFFFFFFF
        self._shm: Optional[shared_memory.SharedMemory] = None
        self._filled_key: Optional[str] = None

    @property
    def id(self) -> str:
        h = hashlib.sha256()
        h.update(self.name.encode())
        h.update(self.size.to_bytes(8, "little"))
        h.update(self.seed.to_bytes(4, "little"))
        return h.hexdigest()[:16]

    def create_or_attach(self, create: bool = True) -> None:
        try:
            self._shm = shared_memory.SharedMemory(name=self.name, create=False)
        except FileNotFoundError:
            if not create:
                raise
            self._shm = shared_memory.SharedMemory(name=self.name, create=True, size=self.size)
        if self._shm.size < self.size:
            # Ensure region is at least requested size (SharedMemory cannot resize; enforce)
            raise RuntimeError(f"Existing shared memory '{self.name}' smaller than requested size")

    def close(self) -> None:
        if self._shm is not None:
            try:
                self._shm.close()
            finally:
                self._shm = None

    def unlink(self) -> None:
        if self._shm is not None:
            try:
                self._shm.unlink()
            except FileNotFoundError:
                pass

    @property
    def buffer(self) -> memoryview:
        if self._shm is None:
            raise RuntimeError("VirtualBlob is not attached")
        return self._shm.buf

    def _fill_block(self, size: int) -> bytes:
        """Generate a deterministic block (<= 1 MiB recommended) of pseudo-random bytes."""
        # xorshift32-based generator, seeded by self.seed
        size = int(size)
        out = bytearray(size)
        state = (self.seed ^ 0x9E3779B9) & 0xFFFFFFFF
        i = 0
        # Generate in 4-byte words when possible
        while i + 4 <= size:
            state ^= (state << 13) & 0xFFFFFFFF
            state ^= (state >> 17) & 0xFFFFFFFF
            state ^= (state << 5) & 0xFFFFFFFF
            w = state
            out[i + 0] = (w >> 0) & 0xFF
            out[i + 1] = (w >> 8) & 0xFF
            out[i + 2] = (w >> 16) & 0xFF
            out[i + 3] = (w >> 24) & 0xFF
            i += 4
        while i < size:
            state ^= (state << 13) & 0xFFFFFFFF
            state ^= (state >> 17) & 0xFFFFFFFF
            state ^= (state << 5) & 0xFFFFFFFF
            out[i] = state & 0xFF
            i += 1
        return bytes(out)

    def ensure_filled(self) -> None:
        """Fill the shared memory region deterministically if not already filled for this (name,size,seed)."""
        if self._shm is None:
            raise RuntimeError("VirtualBlob is not attached")
        # Simple sentinel: first 32 bytes contain an integrity tag for (name,size,seed)
        # Format: 16-byte id + 16-byte md5 over header.
        header_len = 32
        buf = self._shm.buf
        current = bytes(buf[:header_len])
        hdr = self.id.encode()[:16]
        md5 = hashlib.md5(hdr + self.size.to_bytes(8, "little") + self.seed.to_bytes(4, "little")).digest()
        want = hdr + md5
        if current == want:
            return  # already filled for this key
        # Fill with repeated deterministic 1 MiB block
        block = self._fill_block(1 << 20)
        mv = memoryview(buf)
        mv[:header_len] = want
        pos = header_len
        end = self.size
        blen = len(block)
        while pos < end:
            n = min(blen, end - pos)
            mv[pos:pos + n] = block[:n]
            pos += n

    def read(self, offset: int, length: int) -> bytes:
        if self._shm is None:
            raise RuntimeError("VirtualBlob is not attached")
        if length <= 0:
            return b""
        offset = int(offset) % self.size
        end = offset + length
        buf = self._shm.buf
        if end <= self.size:
            return bytes(buf[offset:end])
        # Wrap-around
        first = bytes(buf[offset:self.size])
        rem = end - self.size
        second = bytes(buf[0:rem])
        return first + second
