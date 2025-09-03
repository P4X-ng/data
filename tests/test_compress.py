from packetfs.fs.compress import compress_bytes, decompress_bytes


def test_gzip_roundtrip_and_stats():
    payload = b"A" * 1024 + b"B" * 512
    comp, meta = compress_bytes(payload, level=5)
    assert meta.original_size == len(payload)
    assert meta.compressed_size == len(comp)
    assert meta.ratio >= 1.0  # At worst 1 (should be >1 for repetitive data)
    restored = decompress_bytes(comp)
    assert restored == payload
