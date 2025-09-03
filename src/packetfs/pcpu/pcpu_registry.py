"""Lazy logical pCPU registry.

Avoids instantiating 1.3M objects up front. A logical pCPU record is
created on first use and tracked thereafter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import time

from .pcpu_config import PCPUConfig


@dataclass
class PCPUState:
    pcpu_id: int
    tasks_executed: int = 0
    last_active_ns: int = 0
    user_data: dict = field(default_factory=dict)

    def mark_active(self):
        self.tasks_executed += 1
        self.last_active_ns = time.time_ns()


class PCPURegistry:
    """Lazy registry for logical pCPUs.

    Provides: lookup, activation metrics, summary statistics.
    """

    def __init__(self, cfg: PCPUConfig | None = None):
        self.cfg = cfg or PCPUConfig()
        self._pcpus: Dict[int, PCPUState] = {}
        self._activated_count = 0

    def get(self, pcpu_id: int) -> PCPUState:
        if pcpu_id < 0 or pcpu_id >= self.cfg.LOGICAL_PCPU_COUNT:
            raise IndexError(f"pcpu_id {pcpu_id} out of range")
        st = self._pcpus.get(pcpu_id)
        if st is None:
            st = PCPUState(pcpu_id=pcpu_id)
            self._pcpus[pcpu_id] = st
            self._activated_count += 1
        return st

    def mark_task(self, pcpu_id: int):
        self.get(pcpu_id).mark_active()

    def activated_count(self) -> int:
        return self._activated_count

    def stats(self) -> dict:
        total_tasks = sum(s.tasks_executed for s in self._pcpus.values())
        return {
            "logical_pcpu_count": self.cfg.LOGICAL_PCPU_COUNT,
            "activated_pcpus": self._activated_count,
            "activation_ratio": (self._activated_count / self.cfg.LOGICAL_PCPU_COUNT),
            "total_tasks": total_tasks,
        }
