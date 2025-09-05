# IR execution front-end for PacketFS
# - Parses a small subset of optimized LLVM textual IR (add/ret)
# - Dispatches arithmetic operations to bin/micro_executor for execution
# - Maintains a simple SSA environment to compute results
#
# Notes:
# - This MVP assumes LLVM -O3 promotes locals to registers (no allocas/loads/stores).
# - It handles chains of `add i32` and a final `ret i32 %var`.
# - Further ops (sub/mul, loads/stores, phi, br) can be added incrementally.

from __future__ import annotations

import os
import re
import struct
import subprocess
from typing import Dict, Tuple

try:
    from packetfs.exec.native import PfsExecNative
    _NATIVE = PfsExecNative()
except Exception:
    _NATIVE = None

# micro_executor opcode definitions (must match dev/wip/native/micro_executor.c)
OP_ADD = 0x02
# No subprocess endpoints for SUB/MUL; prefer native in-process lib

STATE_FMT = "<BBBBI8IIIH10s"  # PacketFSState struct layout (60 bytes)
STATE_SIZE = struct.calcsize(STATE_FMT)


def _micro_add(micro_exec_path: str, a: int, b: int) -> int:
    """Execute addition via micro_executor and return the result.

    a, b are 32-bit unsigned for this MVP.
    """
    if not os.path.exists(micro_exec_path):
        raise FileNotFoundError(f"micro_executor not found at {micro_exec_path}")

    opcode = OP_ADD
    reg_target = 0
    reg_source = 1
    flags = 0
    immediate = 0

    registers = [0] * 8
    registers[0] = a & 0xFFFFFFFF
    registers[1] = b & 0xFFFFFFFF

    pc = 0
    result = 0
    checksum = 0
    padding = b"\x00" * 10

    input_state = struct.pack(
        STATE_FMT,
        opcode,
        reg_target,
        reg_source,
        flags,
        immediate,
        *registers,
        pc,
        result,
        checksum,
        padding,
    )

    proc = subprocess.Popen([micro_exec_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    stdout_data, _ = proc.communicate(input_state, timeout=2.0)
    if proc.returncode != 0:
        raise RuntimeError(f"micro_executor exited {proc.returncode}")

    if len(stdout_data) != STATE_SIZE + 4:
        raise RuntimeError("micro_executor returned unexpected output size")

    out_state = stdout_data[:STATE_SIZE]
    (
        _op,
        _rt,
        _rs,
        _fl,
        _imm,
        r0,
        r1,
        r2,
        r3,
        r4,
        r5,
        r6,
        r7,
        _pc,
        out_res,
        _chk,
        _pad,
    ) = struct.unpack(STATE_FMT, out_state)

    return out_res & 0xFFFFFFFF


class IRExecutor:
    """Minimal IR textual executor for add/sub/mul chains with a final ret.

    This executor expects IR generated with clang -O3 -S -emit-llvm so locals are
    promoted to registers and we primarily see volatile loads and ALU chains.
    """

    # Match %n = add/sub/mul i32 X, Y (with flags tolerated)
    ADD_RE = re.compile(r"^\s*%([A-Za-z0-9_\.]+)\s*=\s*add\b.*?\bi32\s+([^,]+),\s+([^\s]+)")
    SUB_RE = re.compile(r"^\s*%([A-Za-z0-9_\.]+)\s*=\s*sub\b.*?\bi32\s+([^,]+),\s+([^\s]+)")
    MUL_RE = re.compile(r"^\s*%([A-Za-z0-9_\.]+)\s*=\s*mul\b.*?\bi32\s+([^,]+),\s+([^\s]+)")
    # Match numbered or named SSA returns
    RET_VAR_RE = re.compile(r"^\s*ret\s+i32\s+%([A-Za-z0-9_\.]+)\b")
    RET_CONST_RE = re.compile(r"^\s*ret\s+i32\s+(-?\d+)\b")
    # Match volatile loads of globals into SSA: %n = load volatile i32, ptr @A
    LOAD_VOL_RE = re.compile(r"^\s*%([A-Za-z0-9_\.]+)\s*=\s*load\s+volatile\s+i32,\s+ptr\s+@([A-Za-z0-9_]+)")
    # Match global integer initializers: @A = dso_local global i32 5
    GLOBAL_I32_RE = re.compile(r"^@([A-Za-z0-9_]+)\s*=\s*.*\bglobal\s+i32\s+(-?\d+)\b")

    def __init__(self, micro_exec_path: str | None = None):
        self.env: Dict[str, int] = {}
        self.globals: Dict[str, int] = {}
        self.micro_exec_path = micro_exec_path or os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../bin/micro_executor"))

    def execute_file(self, ll_path: str) -> int:
        if not os.path.exists(ll_path):
            raise FileNotFoundError(ll_path)
        with open(ll_path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip() for ln in f]
        # Pre-scan globals
        for ln in lines:
            m_g = self.GLOBAL_I32_RE.match(ln.strip())
            if m_g:
                gname, gval = m_g.group(1), int(m_g.group(2)) & 0xFFFFFFFF
                self.globals[gname] = gval
        # Execute
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            m_load = self.LOAD_VOL_RE.match(line)
            if m_load:
                name, gsym = m_load.group(1), m_load.group(2)
                if gsym not in self.globals:
                    raise RuntimeError(f"Unknown global @{gsym}")
                self.env[name] = self.globals[gsym]
                continue
            m_add = self.ADD_RE.match(line)
            if m_add:
                name, lhs, rhs = m_add.group(1), m_add.group(2), m_add.group(3)
                lhs_val = self._resolve(lhs)
                rhs_val = self._resolve(rhs)
                if _NATIVE is not None:
                    res = _NATIVE.add(lhs_val, rhs_val)
                else:
                    res = _micro_add(self.micro_exec_path, lhs_val, rhs_val)
                self.env[name] = res
                continue
            m_sub = self.SUB_RE.match(line)
            if m_sub:
                name, lhs, rhs = m_sub.group(1), m_sub.group(2), m_sub.group(3)
                lhs_val = self._resolve(lhs)
                rhs_val = self._resolve(rhs)
                if _NATIVE is None:
                    raise RuntimeError("SUB requires native lib; build with `just build-exec-lib`")
                self.env[name] = _NATIVE.sub(lhs_val, rhs_val)
                continue
            m_mul = self.MUL_RE.match(line)
            if m_mul:
                name, lhs, rhs = m_mul.group(1), m_mul.group(2), m_mul.group(3)
                lhs_val = self._resolve(lhs)
                rhs_val = self._resolve(rhs)
                if _NATIVE is None:
                    raise RuntimeError("MUL requires native lib; build with `just build-exec-lib`")
                self.env[name] = _NATIVE.mul(lhs_val, rhs_val)
                continue
            m_ret_var = self.RET_VAR_RE.match(line)
            if m_ret_var:
                name = m_ret_var.group(1)
                if name not in self.env:
                    raise RuntimeError(f"Undefined return value %{name}")
                return self.env[name]
            m_ret_const = self.RET_CONST_RE.match(line)
            if m_ret_const:
                return int(m_ret_const.group(1)) & 0xFFFFFFFF
        raise RuntimeError("No return encountered in IR")

    def _resolve(self, token: str) -> int:
        token = token.strip()
        if token.startswith("%"):
            key = token[1:]
            if key not in self.env:
                raise RuntimeError(f"Undefined SSA name %{key}")
            return self.env[key]
        # immediate constant (decimal)
        try:
            return int(token) & 0xFFFFFFFF
        except ValueError:
            raise RuntimeError(f"Unsupported operand token: {token}")

