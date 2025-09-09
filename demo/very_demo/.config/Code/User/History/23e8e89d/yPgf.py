"""RFKilla package exports.

RFKilla - Full Spectrum RF Defense Toolkit
Modern Click + Rich powered CLI for RF security operations.

Primary entrypoint is now the modern CLI interface.
Legacy argparse interface is deprecated but maintained for compatibility.
"""

# Primary CLI interface (Click + Rich)
from .cli import cli as main_cli

# Legacy compatibility exports
try:
    # Optional: requires pywifi
    from .wifi_manager import scan_networks  # type: ignore
except Exception:
    def scan_networks():  # type: ignore
        """Fallback when pywifi is not installed: return empty list."""
        return []

from .rfkilla import main as legacy_main  # Deprecated argparse CLI
from . import json_store

# Bluetooth manager with alias for compatibility
from . import bluetooth_manager
from . import bt_manager
from .bluetooth_manager import BluetoothManager

# Convenience functions for external use
from . import whitelist_manager, core_discovery, feature_flags

__all__ = [
    "main_cli",           # Primary CLI (Click + Rich)
    "legacy_main",        # Deprecated argparse CLI
    "scan_networks",      # WiFi scanning
    "json_store",         # Data persistence
    "whitelist_manager",  # Whitelist management
    "core_discovery",     # Discovery engine
    "feature_flags",      # Feature flag system
]

# Set the main CLI as the primary entrypoint
main = main_cli

# Version info
__version__ = "2.0.0"
__author__ = "RFKilla Development Team"
__description__ = "Full Spectrum RF Defense Toolkit"
