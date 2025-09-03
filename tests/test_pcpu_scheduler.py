import time

from packetfs.pcpu import PCPUConfig, PCPURegistry, PCPUScheduler, PacketExecutor


def _noop(packet):
    # Simulate tiny work
    return 1


class DummyPacket:
    def __init__(self, pid):
        self.packet_id = f"p{pid}"


def test_scheduler_basic():
    cfg = PCPUConfig()
    sched = PCPUScheduler(cfg, PCPURegistry(cfg))
    for i in range(1000):
        sched.submit(i % cfg.LOGICAL_PCPU_COUNT, lambda x=i: x)
    # Allow processing
    time.sleep(0.2)
    stats = sched.stats()
    assert stats["completed_tasks"] > 0
    sched.stop()


def test_packet_executor():
    ex = PacketExecutor(_noop)
    packets = [DummyPacket(i) for i in range(500)]
    ex.execute_packets(packets)
    rep = ex.finalize()
    assert rep["packets_executed"] == 500
    assert rep["scheduler"]["completed_tasks"] >= 500
