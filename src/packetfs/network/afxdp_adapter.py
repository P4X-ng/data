#!/usr/bin/env python3
import ctypes
import os
from ctypes import c_char_p, c_uint32, c_int, c_void_p, c_uint64

# Resolve shared library path within repo
_THIS_DIR = os.path.dirname(__file__)
_LIB_CANDIDATES = [
    os.path.join(_THIS_DIR, "user", "build", "libpfs_afxdp.so"),
]
_lib = None
for p in _LIB_CANDIDATES:
    if os.path.exists(p):
        _lib = ctypes.CDLL(p)
        break
if _lib is None:
    raise OSError("libpfs_afxdp.so not found; run: just net-build-afxdp")

# Prototype mapping
_lib.pfs_afxdp_open.argtypes = [c_char_p, c_uint32, c_uint32, c_uint32, c_int, c_int, c_int]
_lib.pfs_afxdp_open.restype = c_void_p

_lib.pfs_afxdp_is_zerocopy.argtypes = [c_void_p]
_lib.pfs_afxdp_is_zerocopy.restype = c_int

_lib.pfs_afxdp_mode.argtypes = [c_void_p]
_lib.pfs_afxdp_mode.restype = c_int

_lib.pfs_afxdp_fill.argtypes = [c_void_p, c_uint32]
_lib.pfs_afxdp_fill.restype = c_int

_lib.pfs_afxdp_poll.argtypes = [c_void_p, c_int]
_lib.pfs_afxdp_poll.restype = c_int

_lib.pfs_afxdp_rx_burst.argtypes = [c_void_p, c_uint32, ctypes.POINTER(c_uint64)]
_lib.pfs_afxdp_rx_burst.restype = c_int

_lib.pfs_afxdp_tx_burst.argtypes = [c_void_p, c_uint32, c_uint32]
_lib.pfs_afxdp_tx_burst.restype = c_int

_lib.pfs_afxdp_close.argtypes = [c_void_p]

PFS_AFXDP_MODE_AUTO = 0
PFS_AFXDP_MODE_DRV = 1
PFS_AFXDP_MODE_SKB = 2

class Afxdp:
    def __init__(self, iface: str, queue: int = 0, frame_size: int = 2048, ndescs: int = 4096, require_zc: bool = True, mode: int = PFS_AFXDP_MODE_DRV, busy_poll_ms: int = 50):
        h = _lib.pfs_afxdp_open(iface.encode(), c_uint32(queue), c_uint32(frame_size), c_uint32(ndescs), c_int(1 if require_zc else 0), c_int(mode), c_int(busy_poll_ms))
        if not h:
            raise OSError("pfs_afxdp_open failed (require_zc=%s)" % require_zc)
        self._h = c_void_p(h)
        self.frame_size = frame_size
        self.ndescs = ndescs

    def is_zerocopy(self) -> bool:
        return bool(_lib.pfs_afxdp_is_zerocopy(self._h))

    def mode(self) -> int:
        return int(_lib.pfs_afxdp_mode(self._h))

    def fill(self, count: int) -> int:
        return int(_lib.pfs_afxdp_fill(self._h, c_uint32(count)))

    def poll(self, timeout_ms: int) -> int:
        return int(_lib.pfs_afxdp_poll(self._h, c_int(timeout_ms)))

    def rx_burst(self, max_frames: int) -> tuple[int, int]:
        b = c_uint64(0)
        r = _lib.pfs_afxdp_rx_burst(self._h, c_uint32(max_frames), ctypes.byref(b))
        return int(r), int(b.value)

    def tx_burst(self, frame_len: int, frames: int) -> int:
        return int(_lib.pfs_afxdp_tx_burst(self._h, c_uint32(frame_len), c_uint32(frames)))

    def close(self) -> None:
        if self._h:
            _lib.pfs_afxdp_close(self._h)
            self._h = None

