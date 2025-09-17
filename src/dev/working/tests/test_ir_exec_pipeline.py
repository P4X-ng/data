#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import pytest

from packetfs.exec.ir_frontend import IRExecutor

CLANG = shutil.which("clang")

@pytest.mark.skipif(CLANG is None, reason="clang not found")
def test_ir_exec_add_chain(tmp_path):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    sample_c = os.path.join(root, "dev/working/samples/add4.c")
    out_bin = tmp_path / "add4"
    out_ll = tmp_path / "add4.ll"

    # Build native binary for reference result
    cp = subprocess.run([CLANG, "-O3", sample_c, "-o", str(out_bin)])
    assert cp.returncode == 0
    # Run native binary and use its exit code as reference value
    rcp = subprocess.run([str(out_bin)])
    ref_val = rcp.returncode

    # Build LLVM textual IR (-O3 ensures add-chains without allocas)
    subprocess.run([CLANG, "-O3", "-S", "-emit-llvm", sample_c, "-o", str(out_ll)], check=True)
    assert out_ll.exists()

    # Execute via PacketFS IR front-end (micro_executor for arithmetic)
    ex = IRExecutor()
    got = ex.execute_file(str(out_ll))

    assert got == ref_val, f"PacketFS IR exec got {got}, expected {ref_val}"

