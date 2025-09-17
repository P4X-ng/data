#!/usr/bin/env python3
import os
import shutil
import subprocess
import pytest

from packetfs.exec.ir_frontend import IRExecutor

CLANG = shutil.which("clang")

@pytest.mark.skipif(CLANG is None, reason="clang not found")
def test_ir_exec_arith_mix(tmp_path):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    sample_c = os.path.join(root, "dev/working/samples/arith_mix.c")
    out_bin = tmp_path / "arith_mix"
    out_ll = tmp_path / "arith_mix.ll"

    # Build native and run to get reference (exit code)
    cp = subprocess.run([CLANG, "-O3", sample_c, "-o", str(out_bin)])
    assert cp.returncode == 0
    rcp = subprocess.run([str(out_bin)])
    ref_val = rcp.returncode

    # Build textual IR
    subprocess.run([CLANG, "-O3", "-S", "-emit-llvm", sample_c, "-o", str(out_ll)], check=True)

    # Require native in-process library for sub/mul
    # Build it if missing
    lib_path = os.path.abspath(os.path.join(root, "bin", "libpfs_exec.so"))
    if not os.path.exists(lib_path):
        subprocess.run(["just", "build-exec-lib"], check=True)

    ex = IRExecutor()
    got = ex.execute_file(str(out_ll))

    assert got == ref_val, f"PacketFS IR exec got {got}, expected {ref_val}"

