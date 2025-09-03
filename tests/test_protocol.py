from packetfs import ProtocolEncoder, ProtocolDecoder, SyncConfig


def test_sync_emission_and_decode():
    cfg = SyncConfig(window_pow2=4, window_crc16=True)  # window size 16
    enc = ProtocolEncoder(cfg)
    out = bytearray()
    # Fake _bitpack: skip actual packing by monkeypatching
    class Dummy:
        @staticmethod
        def pack_refs(outb, tier, refs, ref_bits):
            # simulate writing bytes directly
            outb.extend(refs)
            return len(refs) * 8
    import packetfs.protocol.protocol as proto_impl
    proto_impl._bitpack = Dummy()  # type: ignore

    # 16 refs of 1 byte each with ref_bits=8 triggers sync once
    enc.pack_refs(out, 0, b"A" * 16, 8)
    sync_pkt = enc.maybe_sync()
    assert sync_pkt is not None
    dec = ProtocolDecoder(cfg)
    win_crc = dec.scan_for_sync(sync_pkt)
    assert win_crc is not None
    win, crc = win_crc
    assert win == 0
    assert crc >= 0
