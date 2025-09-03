"""Configuration constants for pCPU virtualization.

Kept minimal and centrally defined for clarity and future tuning.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import multiprocessing


@dataclass(frozen=True)
class PCPUConfig:
    # Declared logical pCPU count (cosmetic / addressing range)
    LOGICAL_PCPU_COUNT: int = 1_300_000
    # Maximum worker threads we allow (physical multiplex layer)
    MAX_WORKER_THREADS: int = max(1, min(64, (multiprocessing.cpu_count() * 2)))
    # Queue high-water mark for backpressure (can be tuned)
    QUEUE_HIGH_WATER: int = int(os.environ.get("PACKETFS_QUEUE_HIGH_WATER", 100_000))
    # Batch size a worker pulls per scheduling cycle
    DISPATCH_BATCH_SIZE: int = 256
    # Metrics sampling interval seconds (for derived rates)
    METRIC_SAMPLE_SEC: float = 1.0
