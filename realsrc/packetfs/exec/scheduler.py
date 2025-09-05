from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import List, Dict, Tuple

from packetfs.protocol import ProtocolEncoder, SyncConfig, SYNC_MARK, crc16_ccitt
from packetfs.exec.ir_frontend import IRExecutor, _NATIVE

@dataclass
class WindowSync:
    window_id: int
    crc: int
    op_count: int
    bytes_len: int

class WindowedScheduler:
    def __init__(self, window_pow2: int = 16):
        self.config = SyncConfig(window_pow2=window_pow2, window_crc16=True)
        self.encoder = ProtocolEncoder(self.config)
        # References per op: a single byte code: 1=ADD, 2=SUB, 3=MUL
        self.ref_bytes: List[int] = []
        self.window_syncs: List[WindowSync] = []
        # Reuse IR regex/resolve logic via IRExecutor, but do not execute via subprocess
        self.ir = IRExecutor()

    def run(self, ll_path: str) -> Tuple[int, List[WindowSync]]:
        # Reset state
        self.encoder = ProtocolEncoder(self.config)
        self.ref_bytes.clear()
        self.window_syncs.clear()
        self.ir.env.clear()
        self.ir.globals.clear()
        # Parse file content lines
        with open(ll_path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip() for ln in f]
        # Prime globals (same as IRExecutor)
        for ln in lines:
            m_g = self.ir.GLOBAL_I32_RE.match(ln.strip())
            if m_g:
                gname, gval = m_g.group(1), int(m_g.group(2)) & 0xFFFFFFFF
                self.ir.globals[gname] = gval
        # Process lines
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            m_load = self.ir.LOAD_VOL_RE.match(line)
            if m_load:
                name, gsym = m_load.group(1), m_load.group(2)
                if gsym not in self.ir.globals:
                    raise RuntimeError(f"Unknown global @{gsym}")
                self.ir.env[name] = self.ir.globals[gsym]
                continue
            m_add = self.ir.ADD_RE.match(line)
            if m_add:
                name, lhs, rhs = m_add.group(1), m_add.group(2), m_add.group(3)
                lhs_val = self.ir._resolve(lhs)
                rhs_val = self.ir._resolve(rhs)
                # Execute in-process
                if _NATIVE is not None:
                    res = _NATIVE.add(lhs_val, rhs_val)
                else:
                    # Fallback to IRExecutor's add path
                    res = self.ir._resolve(lhs) + self.ir._resolve(rhs)
                self.ir.env[name] = res
                self._push_ref(1)
                continue
            m_sub = self.ir.SUB_RE.match(line)
            if m_sub:
                name, lhs, rhs = m_sub.group(1), m_sub.group(2), m_sub.group(3)
                lhs_val = self.ir._resolve(lhs)
                rhs_val = self.ir._resolve(rhs)
                if _NATIVE is None:
                    raise RuntimeError("SUB requires native lib; build with `just build-exec-lib`")
                self.ir.env[name] = _NATIVE.sub(lhs_val, rhs_val)
                self._push_ref(2)
                continue
            m_mul = self.ir.MUL_RE.match(line)
            if m_mul:
                name, lhs, rhs = m_mul.group(1), m_mul.group(2), m_mul.group(3)
                lhs_val = self.ir._resolve(lhs)
                rhs_val = self.ir._resolve(rhs)
                if _NATIVE is None:
                    raise RuntimeError("MUL requires native lib; build with `just build-exec-lib`")
                self.ir.env[name] = _NATIVE.mul(lhs_val, rhs_val)
                self._push_ref(3)
                continue
            m_ret_var = self.ir.RET_VAR_RE.match(line)
            if m_ret_var:
                name = m_ret_var.group(1)
                if name not in self.ir.env:
                    raise RuntimeError(f"Undefined return value %{name}")
                return self.ir.env[name], list(self.window_syncs)
            m_ret_const = self.ir.RET_CONST_RE.match(line)
            if m_ret_const:
                return int(m_ret_const.group(1)) & 0xFFFFFFFF, list(self.window_syncs)
        raise RuntimeError("No return encountered in IR")

    def _push_ref(self, code: int) -> None:
        # Append a 1-byte ref and feed to encoder for CRC/windowing
        self.ref_bytes.append(code & 0xFF)
        out = bytearray(2)
        self.encoder.pack_refs(out, 0, bytes([code & 0xFF]), 8)
        sync = self.encoder.maybe_sync()
        if sync:
            # Parse SYNC packet: [SYNC_MARK][window_id(2)][crc16(2)]
            if len(sync) < 3:
                raise RuntimeError("Invalid sync frame")
            if sync[0] != SYNC_MARK:
                raise RuntimeError("Bad sync mark")
            win = int.from_bytes(sync[1:3], "big")
            crc = 0
            if len(sync) >= 5:
                crc = int.from_bytes(sync[3:5], "big")
            # Compute op_count and bytes_len for this window from trailing slice
            window_size = 1 << self.config.window_pow2
            op_count = window_size
            bytes_len = window_size  # 1 byte per op
            self.window_syncs.append(WindowSync(win, crc, op_count, bytes_len))

