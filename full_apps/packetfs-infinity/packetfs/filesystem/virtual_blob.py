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
    def __init__(self, name: str, size_bytes: int, seed: int, profile: Optional[str] = None):
        if size_bytes <= 0:
            raise ValueError("size_bytes must be > 0")
        self.name = name
        self.size = int(size_bytes)
        self.seed = int(seed) & 0xFFFFFFFF
        self.profile = (profile or "prand").strip().lower()
        self._shm: Optional[shared_memory.SharedMemory] = None
        self._filled_key: Optional[str] = None

    @property
    def id(self) -> str:
        h = hashlib.sha256()
        h.update(self.name.encode())
        h.update(self.size.to_bytes(8, "little"))
        h.update(self.seed.to_bytes(4, "little"))
        h.update(self.profile.encode())
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
        """Fill the shared memory region deterministically if not already filled for this (name,size,seed,profile).
        Adds a fixed 256 KiB palette immediately after the header with deterministic tiles that both sides can reference.
        """
        if self._shm is None:
            raise RuntimeError("VirtualBlob is not attached")
        # Defensive: if requested size is larger than actual shared memory size, clamp
        actual_size = self._shm.size
        if actual_size < self.size:
            # Adjust internal notion to prevent slicing beyond mapping which could raise SIGBUS
            # (User likely set PFS_BLOB_SIZE_BYTES > container /dev/shm). We clamp and continue.
            self.size = actual_size
        # Simple sentinel: first 32 bytes contain an integrity tag for (name,size,seed,profile)
        # Format: 16-byte id + 16-byte md5 over header.
        header_len = 32
        buf = self._shm.buf
        current = bytes(buf[:header_len])
        hdr = self.id.encode()[:16]
        md5 = hashlib.md5(hdr + self.size.to_bytes(8, "little") + self.seed.to_bytes(4, "little") + self.profile.encode()).digest()
        want = hdr + md5
        if current == want:
            return  # already filled for this key
        try:
            mv = memoryview(buf)
        except BufferError:
            # Extremely unlikely; fallback to bytes interface
            mv = memoryview(bytes(buf))
        mv[:header_len] = want

        # Deterministic palette region: 256 KiB after header
        palette_start = header_len
        palette_size = min(256 * 1024, max(0, self.size - palette_start))
        palette_end = palette_start + palette_size
        self._fill_palette(mv, palette_start, palette_end)

        # Choose fill strategy for remainder
        if palette_end < self.size:
            if self.profile == "orchard":
                self._fill_orchard(mv, palette_end)
            else:
                # Default: prand
                block = self._fill_block(1 << 20)
                pos = palette_end
                end = self.size
                blen = len(block)
                # Write in safe chunks to reduce chance of partial mapping issues
                while pos < end:
                    n = min(blen, end - pos)
                    try:
                        mv[pos:pos + n] = block[:n]
                    except BufferError:
                        # Fallback: zero fill remainder to avoid crash
                        mv[pos:pos + n] = b"\x00" * n
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

    # --- Orchard profile helpers ---
    def _fill_palette(self, mv: memoryview, start: int, end: int) -> None:
        """Fill a deterministic palette region with 256-byte tiles.
        Layout:
          - Tiles[0..255]: constant tiles value=tile_index (guarantees all constant bytes)
          - Remaining tiles: cycle through a mix of structured banks
            (ramp, gray, lfsr, periodic stripes, numeric stride, ascii tokens, debruijn-like)
        """
        tile = 256
        off = start
        idx = 0
        # First 256 tiles: exact constants 0..255
        while off + tile <= end and idx < 256:
            val = idx & 0xFF
            mv[off:off+tile] = bytes([val]) * tile
            off += tile
            idx += 1
        # Mixed banks thereafter
        while off + tile <= end:
            fam = (idx // 1) % 6  # 6 families cycling
            if fam == 0:
                # ramp with step depending on idx
                step = ((idx + 1) * 5) & 0xFF or 1
                mv[off:off+tile] = bytes(((i * step) & 0xFF) for i in range(tile))
            elif fam == 1:
                # gray code
                mv[off:off+tile] = bytes(((i ^ (i >> 1)) & 0xFF) for i in range(tile))
            elif fam == 2:
                # lfsr
                lfsr = (idx * 37 + 1) & 0xFF
                arr = bytearray(tile)
                for i in range(tile):
                    lfsr = ((lfsr >> 1) ^ (-(lfsr & 1) & 0xB8)) & 0xFF
                    arr[i] = lfsr
                mv[off:off+tile] = bytes(arr)
            elif fam == 3:
                # periodic stripes: period depends on idx (2,4,8,16)
                period = 1 << (((idx // 4) % 4) + 1)  # 2,4,8,16
                arr = bytearray(tile)
                for i in range(tile):
                    arr[i] = 0xFF if (i % period) < (period // 2) else 0x00
                mv[off:off+tile] = bytes(arr)
            elif fam == 4:
                # numeric stride (LE 32-bit counter)
                base = (idx * 97) & 0xFFFFFFFF
                arr = bytearray(tile)
                for i in range(0, tile, 4):
                    w = (base + (i // 4)) & 0xFFFFFFFF
                    arr[i+0] = (w >> 0) & 0xFF
                    arr[i+1] = (w >> 8) & 0xFF
                    arr[i+2] = (w >> 16) & 0xFF
                    arr[i+3] = (w >> 24) & 0xFF
                mv[off:off+tile] = bytes(arr)
            else:
                # ascii tokens / punctuation common in JSON/text
                tokens = (b"{}[]:\", \\n true false null : , \t \r \n ")
                arr = bytearray(tile)
                for i in range(tile):
                    arr[i] = tokens[i % len(tokens)]
                mv[off:off+tile] = bytes(arr)
            off += tile
            idx += 1

    def _fill_orchard(self, mv: memoryview, start: int) -> None:
        """Fill using a composed dictionary of banks engineered for matchability.
        Banks (approx proportions):
          - exec padding/codelets (0x00/0xCC/NOP-ish): ~15%
          - ascii tokens (JSON-like): ~10%
          - numeric stride (LE uint32++): ~15%
          - periodic modulo stripes (64/128/512/4096): ~20%
          - coverage tile (0..255 repeat): ~15%
          - prand tail: ~25%
        """
        total = self.size
        pos = start
        end = total
        def take(frac: float) -> int:
            # allocate in multiples of 4096 for alignment, keep room for end
            want = int((total - start) * frac)
            want = (want // 4096) * 4096
            return max(0, min(want, end - pos))

        sizes = [
            ("execpad", take(0.10)),
            ("code",    take(0.12)),
            ("rodata",  take(0.12)),
            ("ascii",   take(0.10)),
            ("words",   take(0.06)),
            ("numeric", take(0.14)),
            ("period",  take(0.20)),
            ("cover",   take(0.10)),
        ]
        used = sum(s for _, s in sizes)
        tail = max(0, end - pos - used)
        sizes.append(("prand", tail))

        for name, length in sizes:
            if length <= 0:
                continue
            if name == "execpad":
                self._bank_execpad(mv, pos, length)
            elif name == "code":
                self._bank_codelets(mv, pos, length)
            elif name == "rodata":
                self._bank_rodata_ascii(mv, pos, length)
            elif name == "ascii":
                self._bank_ascii_tokens(mv, pos, length)
            elif name == "words":
                self._bank_english_words(mv, pos, length)
            elif name == "numeric":
                self._bank_numeric_stride(mv, pos, length)
            elif name == "period":
                self._bank_periodic(mv, pos, length)
            elif name == "cover":
                self._bank_coverage(mv, pos, length)
            else:
                self._bank_prand(mv, pos, length)
            pos += length

    def _bank_execpad(self, mv: memoryview, start: int, length: int) -> None:
        # Alternate 0x00 and 0xCC in 4KB pages to mirror common padding styles.
        page = 4096
        off = start
        end = start + length
        toggle = 0
        while off < end:
            n = min(page, end - off)
            b = 0x00 if (toggle % 2 == 0) else 0xCC
            mv[off:off+n] = bytes([b]) * n
            toggle += 1
            off += n

    def _bank_ascii_tokens(self, mv: memoryview, start: int, length: int) -> None:
        tokens = (b"{ } [ ] : , \" \n true false null \n : \n , \n \t \r \n" * 64)
        off = start
        end = start + length
        while off < end:
            n = min(len(tokens), end - off)
            mv[off:off+n] = tokens[:n]
            off += n

    def _bank_codelets(self, mv: memoryview, start: int, length: int) -> None:
        # Common x86-64 codelets: prologue/epilogue, NOPs, short rel branches
        seqs = [
            b"\x55\x48\x89\xe5",        # push rbp; mov rbp,rsp
            b"\x48\x83\xec\x10",        # sub rsp,0x10
            b"\x48\x83\xc4\x10\xc3",  # add rsp,0x10; ret
            b"\xc9\xc3",                # leave; ret
            b"\x90" * 8,                 # NOP sled
            b"\x66\x90\x0f\x1f\x00",  # multi-byte NOPs
            b"\xe8\x00\x00\x00\x00",  # call rel32 (placeholder)
            b"\xeb\x00",                # jmp rel8 (placeholder)
        ]
        off = start
        end = start + length
        i = 0
        while off < end:
            s = seqs[i % len(seqs)]
            n = min(len(s), end - off)
            mv[off:off+n] = s[:n]
            off += n
            i += 1

    def _bank_rodata_ascii(self, mv: memoryview, start: int, length: int) -> None:
        # Mix of printable strings terminated by NULs
        strings = [
            b"/bin/sh\x00", b"printf\x00", b"libc.so.6\x00", b"malloc\x00", b"free\x00",
            b"main\x00", b"_start\x00", b".text\x00", b".rodata\x00", b"__libc_start_main\x00",
        ]
        tile = b"".join(strings) + (b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789\x00" * 2)
        off = start
        end = start + length
        while off < end:
            n = min(len(tile), end - off)
            mv[off:off+n] = tile[:n]
            off += n

    def _bank_english_words(self, mv: memoryview, start: int, length: int) -> None:
        # Common English words (lowercase) separated by spaces and NULs
        words = (
            b"the and for you that with have this from not are but all any can had her was one our out day get has how man new now old see two who why use work year time make know take good back even want give most \x00"
            b"about because before between different during first great little long might never place public right small still thing think under where while world would young \x00"
        )
        off = start
        end = start + length
        while off < end:
            n = min(len(words), end - off)
            mv[off:off+n] = words[:n]
            off += n

    def _bank_numeric_stride(self, mv: memoryview, start: int, length: int) -> None:
        # 32-bit little-endian incrementing integers
        import struct
        count = length // 4
        off = start
        val = 0
        for _ in range(count):
            mv[off:off+4] = struct.pack('<I', val & 0xFFFFFFFF)
            val += 1
            off += 4
        rem = start + length - off
        if rem > 0:
            mv[off:off+rem] = bytes([0]) * rem

    def _bank_periodic(self, mv: memoryview, start: int, length: int) -> None:
        # Four equal sub-bands with modulo patterns 64/128/512/4096
        mods = [64, 128, 512, 4096]
        sub = length // len(mods)
        off = start
        for m in mods:
            endsub = off + sub
            i = off
            while i < endsub:
                v = (i % m) & 0xFF
                # simple gradient based on remainder
                mv[i:i+1] = bytes((v,))
                i += 1
            off = endsub
        # remainder
        if off < start + length:
            mv[off:start+length] = bytes([0]) * (start + length - off)

    def _bank_coverage(self, mv: memoryview, start: int, length: int) -> None:
        # Simple coverage tile: 0..255 repeating
        off = start
        end = start + length
        tile = bytes(range(256))
        while off < end:
            n = min(len(tile), end - off)
            mv[off:off+n] = tile[:n]
            off += n

    def _bank_prand(self, mv: memoryview, start: int, length: int) -> None:
        # Use xorshift32 block tile from _fill_block
        block = self._fill_block(1 << 20)
        off = start
        end = start + length
        blen = len(block)
        while off < end:
            n = min(blen, end - off)
            mv[off:off+n] = block[:n]
            off += n
