from __future__ import annotations

import ctypes
import os
from typing import Optional

_LIB_CANDIDATES = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../bin/libpfs_exec.so")),
    "libpfs_exec.so",
]

class PfsExecNative:
    def __init__(self):
        self.lib: Optional[ctypes.CDLL] = None
        for path in _LIB_CANDIDATES:
            try:
                self.lib = ctypes.CDLL(path)
                break
            except OSError:
                continue
        if self.lib is None:
            raise RuntimeError("libpfs_exec.so not found; build with `just build-exec-lib`")
        # Prototype
        self.lib.pfs_execute_add.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        self.lib.pfs_execute_add.restype = ctypes.c_uint32
        self.lib.pfs_execute_sub.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        self.lib.pfs_execute_sub.restype = ctypes.c_uint32
        self.lib.pfs_execute_mul.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        self.lib.pfs_execute_mul.restype = ctypes.c_uint32
        # pfs_add_loop_u32(uint32_t start, uint32_t inc, uint64_t count)
        try:
            self.lib.pfs_add_loop_u32.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint64]
            self.lib.pfs_add_loop_u32.restype = ctypes.c_uint32
            self._has_add_loop = True
        except AttributeError:
            self._has_add_loop = False

    def add(self, a: int, b: int) -> int:
        return int(self.lib.pfs_execute_add(a & 0xFFFFFFFF, b & 0xFFFFFFFF))

    def sub(self, a: int, b: int) -> int:
        return int(self.lib.pfs_execute_sub(a & 0xFFFFFFFF, b & 0xFFFFFFFF))

    def mul(self, a: int, b: int) -> int:
        return int(self.lib.pfs_execute_mul(a & 0xFFFFFFFF, b & 0xFFFFFFFF))

    def add_loop(self, start: int, inc: int, count: int) -> int:
        if not getattr(self, "_has_add_loop", False):
            # Fallback: simple Python loop (slow)
            acc = start & 0xFFFFFFFF
            for _ in range(int(count)):
                acc = (acc + (inc & 0xFFFFFFFF)) & 0xFFFFFFFF
            return acc
        return int(self.lib.pfs_add_loop_u32(start & 0xFFFFFFFF, inc & 0xFFFFFFFF, int(count)))

