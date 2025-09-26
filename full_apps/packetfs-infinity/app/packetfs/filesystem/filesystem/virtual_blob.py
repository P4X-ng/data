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
        """Fill the shared memory region deterministically if not already filled for this (name,size,seed,profile)."""
        if self._shm is None:
            raise RuntimeError("VirtualBlob is not attached")
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
        mv = memoryview(buf)
        mv[:header_len] = want
        # Choose fill strategy
        if self.profile == "orchard":
            self._fill_orchard(mv, header_len)
        else:
            # Default: prand
            block = self._fill_block(1 << 20)
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

    # --- Orchard profile helpers ---
    def _memset_region(self, mv: memoryview, start: int, length: int, value: int) -> None:
        # Fallback per-byte write to avoid memoryview structure mismatch across Python versions
        end = start + length
        bval = value & 0xFF
        for i in range(start, end):
            mv[i] = bval

    def _fill_orchard(self, mv: memoryview, start: int) -> None:
        """Fill using a composed dictionary of banks engineered for matchability.
        Banks (approx proportions), tuned for ELF-heavy workloads + general coverage:
          - exec padding/codelets (0x00/0xCC/NOP-ish)
          - ELF markers and common strings ("\x7fELF", ".text", ".rodata", "GLIBC", etc.)
          - rodata-ish ASCII and English words
          - numeric stride (LE uint32++)
          - periodic modulo stripes (64/128/512/4096)
          - coverage: 0..255 repeat, de Bruijn nibble tile (k≈4) to guarantee short k-grams
          - long runs of 0x00 and 0xFF
          - prand tail
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
            ("execpad",   take(0.06)),
            ("code",      take(0.13)),
            ("elf",       take(0.14)),
            ("rodata",    take(0.09)),
            ("ascii",     take(0.07)),
            ("words",     take(0.05)),
            ("numeric",   take(0.10)),
            ("period",    take(0.12)),
            ("cover",     take(0.05)),
            ("debruijn",  take(0.10)),
            ("pltgot",    take(0.06)),
            ("reloc",     take(0.06)),
        ]
        used = sum(s for _, s in sizes)
        tail = max(0, end - pos - used)
        sizes.append(("prand", tail))

        for name, length in sizes:
            if length <= 0:
                continue
            # Clamp to remaining space
            remaining = end - pos
            if remaining <= 0:
                break
            if length > remaining:
                length = remaining
            if name == "execpad":
                self._bank_execpad(mv, pos, length)
            elif name == "code":
                self._bank_codelets(mv, pos, length)
            elif name == "elf":
                self._bank_elf_markers(mv, pos, length)
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
            elif name == "debruijn":
                self._bank_debruijn_nibble(mv, pos, length)
            elif name == "pltgot":
                self._bank_pltgot_dense(mv, pos, length)
            elif name == "reloc":
                self._bank_reloc_tables(mv, pos, length)
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
        # Common x86-64 codelets: prologue/epilogue, NOPs, short rel branches, PLT-like stubs
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

    def _bank_elf_markers(self, mv: memoryview, start: int, length: int) -> None:
        # ELF signatures and common strings/section names
        tokens = [
            b"\x7fELF", b".text\x00", b".rodata\x00", b".data\x00", b".bss\x00",
            b".plt\x00", b".plt.got\x00", b".plt.sec\x00", b".got\x00", b".got.plt\x00",
            b".dynsym\x00", b".dynstr\x00", b".rela.dyn\x00", b".rela.plt\x00",
            b"GNU\x00", b"GLIBC\x00", b"libc.so.6\x00", b"ld-linux-x86-64.so.2\x00",
            b"__libc_start_main\x00", b"__libc_csu_init\x00", b"__libc_csu_fini\x00",
            b"_start\x00", b"main\x00", b"/bin/bash\x00",
        ]
        tile = b"".join(tokens)
        # Simulate relocation-like structures (strided 8 or 16 bytes)
        rel8 = bytes.fromhex(
            "0000000000000000 1000000000000000 2000000000000000 3000000000000000"
        )
        rel16 = bytes.fromhex(
            "00000000000000000000000000000000 01000000000000000100000000000000"
        )
        plt_stub = bytes.fromhex("ff2500000000 6800000000 e900000000")  # jmp [rip+..]; push ..; jmp ..
        pad = b"\x00" * 64
        mix = tile + rel8 + rel16 + plt_stub + pad
        off = start
        end = start + length
        while off < end:
            n = min(len(mix), end - off)
            mv[off:off+n] = mix[:n]
            off += n

    def _bank_pltgot_dense(self, mv: memoryview, start: int, length: int) -> None:
        # Dense PLT/GOT-like stubs: jmp [rip+..]; push imm; jmp rel32, interleaved with GOT entry placeholders
        stub = bytes.fromhex("ff2500000000 68 11223344 e9 00000000")
        got = bytes.fromhex("0000000000000000 0000000000000000")
        tile = stub + got
        off = start
        end = start + length
        while off < end:
            n = min(len(tile), end - off)
            mv[off:off+n] = tile[:n]
            off += n

    def _bank_reloc_tables(self, mv: memoryview, start: int, length: int) -> None:
        # Relocation-like entries: 16-byte records with index and type-like fields
        import struct
        off = start
        end = start + length
        idx = 0
        while off + 16 <= end:
            rec = struct.pack('<QQ', idx & 0xFFFFFFFFFFFFFFFF, 0x0000000000000078)
            # per-byte copy to avoid memoryview structure mismatch
            for j in range(16):
                mv[off + j] = rec[j]
            off += 16
            idx += 1
        if off < end:
            mv[off:end] = bytes([0]) * (end - off)

    def _bank_debruijn_nibble(self, mv: memoryview, start: int, length: int) -> None:
        # Generate a de Bruijn sequence over nibbles (alphabet 0..15) of order k=5 for denser 4-gram coverage
        # Encode two nibbles per byte.
        k = 5
        # Generate a de Bruijn sequence over nibbles (alphabet 0..15) of order k=5 for denser 4-gram coverage
        # Encode two nibbles per byte.
        k = 5
        alphabet = list(range(16))
        n = len(alphabet)
        a = [0] * (n * k)
        seq = []
        def db(t: int, p: int):
            if t > k:
                if k % p == 0:
                    seq.extend(a[1:p+1])
            else:
                a[t] = a[t-p]
                db(t+1, p)
                for j in range(a[t-p]+1, n):
                    a[t] = j
                    db(t+1, t)
        db(1,1)
        # seq is a list of nibbles; pack into bytes
        def pack_nibbles(nibs):
            out = bytearray((len(nibs)+1)//2)
            i = 0
            bi = 0
            while i < len(nibs):
                hi = nibs[i] & 0xF
                lo = nibs[i+1] & 0xF if i+1 < len(nibs) else 0
                out[bi] = (hi << 4) | lo
                bi += 1
                i += 2
            return bytes(out)
        tile = pack_nibbles(seq)
        off = start
        end = start + length
        tlen = len(tile)
        while off < end:
            nbytes = min(tlen, end - off)
            mv[off:off+nbytes] = tile[:nbytes]
            off += nbytes
