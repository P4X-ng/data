"""PacketFS core package (clean scaffold).

Currently provides:
 - pCPU virtualization scaffolding (registry + scheduler)
 - Neutral, metrics-based execution adapter.

Marketing / exaggerated messaging has been intentionally removed.
"""

from .pcpu.packet_executor import PacketExecutor  # noqa: F401
from .protocol import SyncConfig, ProtocolEncoder, ProtocolDecoder  # noqa: F401
from .network import make_eth_header, get_if_mac, send_frames, ETH_P_PFS  # noqa: F401
