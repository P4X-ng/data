from packetfs.fs.computed_offset_index import ComputedOffsetIndexBuilder, ModuleDescriptor, EncodingMode


def test_stride_mode_offsets_and_roundtrip():
    b = ComputedOffsetIndexBuilder(module_id="m1", version=1, seed=42)
    for _ in range(100):
        b.add_size(8)
    desc = b.build()
    assert desc.mode == EncodingMode.STRIDE
    # Serialize + deserialize
    raw = desc.serialize()
    desc2 = ModuleDescriptor.deserialize(raw)
    assert desc2.instruction_count == 100
    assert desc2.mode == EncodingMode.STRIDE
    # Check some offsets arithmetic
    base = desc2.base_offset()
    assert desc2.offset(0) == base
    assert desc2.offset(1) == base + 8
    assert desc2.offset(10) == base + 80


def test_delta_block_offsets_and_roundtrip():
    sizes = [5,7,9,4,3,6,11,2,8,10, 12,1,5,5,5,9,3,3,2,7]
    b = ComputedOffsetIndexBuilder(module_id="mvar", version=2, seed=99, block_span=8)
    b.add_sizes(sizes)
    desc = b.build()
    assert desc.mode == EncodingMode.DELTA_BLOCK
    raw = desc.serialize()
    desc2 = ModuleDescriptor.deserialize(raw)
    # Verify offsets by manual accumulation
    cumulative = 0
    for i, sz in enumerate(sizes):
        off = desc2.offset(i)
        assert off == desc2.base_offset() + cumulative
        cumulative += sz
    assert desc2.instruction_count == len(sizes)


def test_out_of_range_index():
    b = ComputedOffsetIndexBuilder(module_id="m3", version=1, seed=1)
    b.add_sizes([4,4,4])
    desc = b.build()
    try:
        desc.offset(3)
        assert False, "expected IndexError"
    except IndexError:
        pass
