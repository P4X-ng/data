import pytest
from app.services.pvrt_framing import build_preface, parse_preface, compute_needed_from_manifest


def test_preface_roundtrip_with_psk():
    tid = "abc123"
    blob = "pfs_vblob:1073741824:1337"
    obj = "deadbeef" * 4
    psk = "s3cr3t"
    pre = build_preface(tid, channels=2, channel_id=1, blob_fingerprint=blob, object_sha256=obj, psk=psk)
    got = parse_preface(pre)
    assert got["transfer_id"] == tid
    assert got["channels"] == 2
    assert got["channel_id"] == 1
    assert got["blob"] == blob
    assert got["object"] == obj
    assert got["psk"] == psk


def test_compute_needed_empty_local_means_all_needed():
    # When local has no hashes, everything should be needed
    remote = [bytes([i])*16 for i in range(4)]
    needed = compute_needed_from_manifest([], remote)
    assert needed == [0,1,2,3]


def test_compute_needed_same_hashes_none_needed():
    local = [bytes([i])*16 for i in range(3)]
    remote = list(local)
    needed = compute_needed_from_manifest(local, remote)
    assert needed == []
