#!/usr/bin/env python3
import os
import shutil
import subprocess
import pytest

from packetfs.exec.ir_frontend import IRExecutor

CLANG = shutil.which("clang")

@pytest.mark.skipif(CLANG is None, reason="clang not found")
def test_ir_exec_sum64(tmp_path):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    sample_c = os.path.join(root, "dev/working/samples/sum64.c")
    out_bin = tmp_path / "sum64"
    out_ll = tmp_path / "sum64.ll"

    # Build native and run to get reference (exit code)
    cp = subprocess.run([CLANG, "-O3", sample_c, "-o", str(out_bin)])
    assert cp.returncode == 0
    rcp = subprocess.run([str(out_bin)])
    ref_val = rcp.returncode

    # Build textual IR
    subprocess.run([CLANG, "-O3", "-S", "-emit-llvm", sample_c, "-o", str(out_ll)], check=True)

    # Build in-process endpoints (only add needed)
    lib_path = os.path.abspath(os.path.join(root, "bin", "libpfs_exec.so"))
    if not os.path.exists(lib_path):
        subprocess.run(["just", "build-exec-lib"], check=True)

    ex = IRExecutor()
    got = ex.execute_file(str(out_ll))

    # Linux exit codes are truncated to 8 bits; compare modulo 256
    assert (got & 0xFF) == ref_val, f"PacketFS IR exec got {got} (mod 256 {(got & 0xFF)}), expected {ref_val}"

