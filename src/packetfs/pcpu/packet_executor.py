"""PacketExecutor bridges PacketFS packets to the pCPU scheduler.

It does not assume any specific compression or transport; it calls a
user-supplied packet execution function and records timing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Callable, Any, List
import time

from .pcpu_config import PCPUConfig
from .pcpu_registry import PCPURegistry
from .pcpu_scheduler import PCPUScheduler


@dataclass
class ExecutedPacket:
    packet_id: str
    pcpu_id: int
    duration_ns: int
    result: Any


class PacketExecutor:
    def __init__(self, execute_fn: Callable[[Any], Any], cfg: PCPUConfig | None = None):
        self.cfg = cfg or PCPUConfig()
        self.registry = PCPURegistry(self.cfg)
        self.scheduler = PCPUScheduler(self.cfg, self.registry)
        self._execute_fn = execute_fn
        self._results: List[ExecutedPacket] = []

    def execute_packets(self, packets: Iterable[Any]):
        for idx, pkt in enumerate(packets):
            pcpu_id = idx % self.cfg.LOGICAL_PCPU_COUNT
            self.scheduler.submit(pcpu_id, self._run_one, pcpu_id, pkt)

    def _run_one(self, pcpu_id: int, packet: Any):
        start = time.time_ns()
        res = self._execute_fn(packet)
        end = time.time_ns()
        self._results.append(ExecutedPacket(packet_id=getattr(packet, "packet_id", str(id(packet))),
                                           pcpu_id=pcpu_id,
                                           duration_ns=end - start,
                                           result=res))

    def finalize(self, wait: bool = True):
        if wait:
            # Wait for queue drain
            while self.scheduler.stats()["queue_depth"] > 0:
                time.sleep(0.05)
        self.scheduler.stop(wait=wait)
        return self.report()

    def report(self) -> dict:
        total_ns = sum(r.duration_ns for r in self._results)
        return {
            "packets_executed": len(self._results),
            "aggregate_exec_ms": total_ns / 1e6,
            "scheduler": self.scheduler.stats(),
        }
