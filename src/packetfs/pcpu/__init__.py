"""pCPU virtualization layer.

Implements a lightweight logical pCPU model multiplexed onto a bounded
worker thread pool. All counts and metrics are real measurements; no
fabricated acceleration factors.
"""

from .pcpu_config import PCPUConfig  # noqa: F401
from .pcpu_registry import PCPURegistry  # noqa: F401
from .pcpu_scheduler import PCPUScheduler, PCPUWorkItem  # noqa: F401
from .packet_executor import PacketExecutor  # noqa: F401
