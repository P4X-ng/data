#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import tempfile

from packetfs.network.packetfs_file_transfer import PacketFSFileTransfer
from packetfs.filesystem.virtual_blob import VirtualBlob


def test_blueprint_reconstruct(tmp_path):
    # Create a small shared blob (8 MiB) for test
    blob_name = "pfs_test_blob"
    blob_size_mb = 8
    seed = 4242
    vb = VirtualBlob(blob_name, blob_size_mb * (1 << 20), seed)
    vb.create_or_attach(create=True)
    vb.ensure_filled()

    # Blueprint formula covering ~1 MiB
    size_mb = 1
    seg_len = 4096
    count = (size_mb * (1 << 20)) // seg_len
    stride = 12289  # prime stride to cause wrap-around
    blueprint = {
        "mode": "formula",
        "blob": {"name": blob_name, "size": blob_size_mb * (1 << 20), "seed": seed},
        "segments": {
            "count": count,
            "seg_len": seg_len,
            "start_offset": 0,
            "stride": stride,
            "delta": 0,
        },
        "file_size": size_mb * (1 << 20),
    }

    # Reconstruct using PacketFS method (no server needed for this unit check)
    pfs = PacketFSFileTransfer()
    out_path = tmp_path / "bp_out.bin"
    pfs.reconstruct_from_blueprint(blueprint, str(out_path))

    # Independently compute expected MD5
    h = hashlib.md5()
    written = 0
    off = 0
    while written < blueprint["file_size"]:
        n = min(seg_len, blueprint["file_size"] - written)
        chunk = vb.read(off, n)
        h.update(chunk)
        written += n
        off = (off + stride) % vb.size
    expected_md5 = h.hexdigest()

    with open(out_path, "rb") as f:
        actual_md5 = hashlib.md5(f.read()).hexdigest()

    assert actual_md5 == expected_md5
