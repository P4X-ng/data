#!/usr/bin/env python3
import os
import shutil
import subprocess
import pytest

from packetfs.exec.scheduler import WindowedScheduler

CLANG = shutil.which("clang")

@pytest.mark.skipif(CLANG is None, reason="clang not found")
def test_windowed_scheduler_sum64(tmp_path):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    sample_c = os.path.join(root, "dev/working/samples/sum64.c")
    out_bin = tmp_path / "sum64"
    out_ll = tmp_path / "sum64.ll"

    cp = subprocess.run([CLANG, "-O3", sample_c, "-o", str(out_bin)])
    assert cp.returncode == 0
    rcp = subprocess.run([str(out_bin)])
    ref_val = rcp.returncode

    subprocess.run([CLANG, "-O3", "-S", "-emit-llvm", sample_c, "-o", str(out_ll)], check=True)

    # Use a small window (2^4=16 ops) so 64 ops -> 4 windows
    sched = WindowedScheduler(window_pow2=4)
    got, syncs = sched.run(str(out_ll))

    assert (got & 0xFF) == ref_val
    window_size = 1 << 4
    expected_windows = len(sched.ref_bytes) // window_size
    assert len(syncs) == expected_windows

    # Verify CRC per window over the op codes (1 byte per op)
    # WindowedScheduler uses codes: 1=ADD; sum64 is adds only
    from packetfs.protocol import crc16_ccitt
    window_size = 1 << 4
    for idx, ws in enumerate(syncs):
        start = idx * window_size
        end = start + window_size
        window_bytes = bytes(sched.ref_bytes[start:end])
        expect_crc = crc16_ccitt(window_bytes)
        assert ws.crc == expect_crc, f"crc mismatch win {idx}: {ws.crc} != {expect_crc}"

