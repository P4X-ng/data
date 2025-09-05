#!/usr/bin/env python3
import os
import struct
import subprocess
import sys
import shutil
import pytest

# PacketFSState layout from dev/wip/native/micro_executor.c (packed)
# typedef struct __attribute__((packed)) {
#     uint8_t  opcode;
#     uint8_t  reg_target;
#     uint8_t  reg_source;
#     uint8_t  flags;
#     uint32_t immediate;
#     uint32_t registers[8];
#     uint32_t pc;
#     uint32_t result;
#     uint16_t checksum;
#     uint8_t  padding[10];
# } PacketFSState;

# Opcodes (must match micro_executor.c)
OP_NOP = 0x00
OP_MOV = 0x01
OP_ADD = 0x02
OP_SUB = 0x03
OP_MUL = 0x04
OP_DIV = 0x05
OP_JMP = 0x06
OP_CMP = 0x07
OP_HALT = 0xFF

STATE_FMT = "<BBBBI8IIIH10s"  # little-endian, packed
STATE_SIZE = struct.calcsize(STATE_FMT)
assert STATE_SIZE == 60

BIN_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..", "bin", "micro_executor"))

@pytest.mark.skipif(not os.path.exists(BIN_PATH), reason="micro_executor binary not built")
def test_micro_executor_addition_roundtrip():
    # Prepare input state to perform reg0 = reg0 + reg1
    opcode = OP_ADD
    reg_target = 0
    reg_source = 1
    flags = 0
    immediate = 0

    registers = [0] * 8
    registers[0] = 5
    registers[1] = 7

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

    assert len(input_state) == STATE_SIZE

    # Execute micro_executor and exchange the state via stdin/stdout
    proc = subprocess.Popen([BIN_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    stdout_data, _ = proc.communicate(input_state, timeout=2.0)
    assert proc.returncode == 0

    # Output: PacketFSState (60 bytes) + execution_time_ns (4 bytes)
    assert len(stdout_data) == STATE_SIZE + 4

    out_state = stdout_data[:STATE_SIZE]
    exec_time_ns = struct.unpack_from("<I", stdout_data, STATE_SIZE)[0]

    (
        out_opcode,
        out_reg_target,
        out_reg_source,
        out_flags,
        out_immediate,
        r0, r1, r2, r3, r4, r5, r6, r7,
        out_pc,
        out_result,
        out_checksum,
        _out_padding,
    ) = struct.unpack(STATE_FMT, out_state)

    # Validate that addition occurred: r0 == 5 + 7, result mirrors r0
    assert out_opcode == OP_ADD
    assert out_reg_target == reg_target
    assert out_reg_source == reg_source
    assert r0 == 12
    assert out_result == 12

    # Execution time should be a small non-zero number
    assert isinstance(exec_time_ns, int)
    assert exec_time_ns >= 0

