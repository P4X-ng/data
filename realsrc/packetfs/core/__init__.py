# Empty package init
from importlib import import_module as _im

try:
    _im("packetfs._bitpack")
except Exception:
    pass

# Public API shortcuts
from .protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig  # noqa: E402,F401
