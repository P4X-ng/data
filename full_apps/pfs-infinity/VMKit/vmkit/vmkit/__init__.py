"""
VMKit - Simple Python abstraction for libvirt/KVM with Secure Boot support

A human-friendly wrapper around libvirt for creating and managing VMs,
with built-in UEFI Secure Boot support and cloud-init integration.
"""

from .core import SecureVM, VMError
from .images import CloudImage, ISOImage, ExistingDisk
from .cloudinit import CloudInitConfig, quick_config, ssh_only_config
from .passthrough import PassthroughManager, PCIDevice, find_gpu, find_nvme, scan_system

# New modules for extended functionality
from .host import HostCapture, VirtualizedHost
from .storage import StorageRepository, StorageManager
from .network import NetworkManager
from .migration import MigrationManager
from .hotplug import HotplugManager

__version__ = "0.1.0"
__all__ = [
    # Core VM functionality
    "SecureVM", "VMError",
    # Image handling
    "CloudImage", "ISOImage", "ExistingDisk", 
    # Cloud-init
    "CloudInitConfig", "quick_config", "ssh_only_config",
    # Hardware passthrough
    "PassthroughManager", "PCIDevice", "find_gpu", "find_nvme", "scan_system",
    # Host virtualization
    "HostCapture", "VirtualizedHost",
    # Storage management
    "StorageRepository", "StorageManager",
    # Network management
    "NetworkManager",
    # Migration support
    "MigrationManager",
    # Hot-plugging
    "HotplugManager"
]
