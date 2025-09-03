from packetfs.fs.packet_store import InMemoryPacketStore
from packetfs.fs.object_index import ObjectIndex
from packetfs.fs.execution_adapter import ObjectExecutor


def test_inmemory_store_dedupe():
    store = InMemoryPacketStore()
    p1 = store.append(b"abc")
    p2 = store.append(b"abc")
    assert p1.packet_id == p2.packet_id
    assert store.stats()["packet_count"] == 1


def test_object_ingest_and_execute():
    idx = ObjectIndex()
    data = b"hello world" * 100
    meta = idx.ingest_bytes("sample", data, mtu=32)
    assert meta.size == len(data)
    assert len(meta.packet_ids) == (len(data) + 31) // 32

    def exec_fn(payload):
        # Return length as stand-in for real work
        return len(payload)

    adapter = ObjectExecutor(idx, exec_fn)
    rep = adapter.execute_object("sample")
    assert rep["packets_executed"] == len(meta.packet_ids)
