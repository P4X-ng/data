"""
PCI device passthrough support for VMKit

Handles GPU, NVMe, and generic PCI device passthrough with IOMMU/VFIO management.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class DeviceType(Enum):
    """PCI device types for passthrough"""
    GPU = "gpu"
    NVME = "nvme"
    NETWORK = "network"
    AUDIO = "audio"
    USB = "usb"
    GENERIC = "generic"


@dataclass
class PCIDevice:
    """Represents a PCI device for passthrough"""
    pci_id: str  # e.g., "0000:01:00.0"
    vendor_id: str  # e.g., "10de"
    device_id: str  # e.g., "2204"
    vendor_name: str  # e.g., "NVIDIA Corporation"
    device_name: str  # e.g., "GeForce RTX 3080"
    device_type: DeviceType
    iommu_group: Optional[int] = None
    driver: Optional[str] = None
    bound_to_vfio: bool = False
    
    @property
    def vendor_device_id(self) -> str:
        """Combined vendor:device ID (e.g., 10de:2204)"""
        return f"{self.vendor_id}:{self.device_id}"
    
    @property
    def is_gpu(self) -> bool:
        return self.device_type == DeviceType.GPU
    
    @property
    def is_nvme(self) -> bool:
        return self.device_type == DeviceType.NVME


@dataclass
class IOMMUGroup:
    """IOMMU group information"""
    group_id: int
    devices: List[PCIDevice]
    
    @property
    def is_isolated(self) -> bool:
        """Check if group contains only passthrough-safe devices"""
        # A group is considered isolated if it doesn't contain critical system devices
        critical_classes = ["Host bridge", "ISA bridge", "SATA controller"]
        for device in self.devices:
            if any(critical in device.device_name for critical in critical_classes):
                return False
        return True


class PassthroughManager:
    """Manages PCI device passthrough configuration"""
    
    def __init__(self):
        self.devices: List[PCIDevice] = []
        self.iommu_groups: Dict[int, IOMMUGroup] = {}
        self._scan_devices()
    
    def _run_command(self, cmd: List[str]) -> str:
        """Run command and return output"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""
    
    def _scan_devices(self):
        """Scan system for PCI devices"""
        self.devices = []
        self.iommu_groups = {}
        
        # Get PCI device info from lspci
        lspci_output = self._run_command(["lspci", "-nnmv"])
        self._parse_lspci_output(lspci_output)
        
        # Get IOMMU group info
        self._scan_iommu_groups()
        
        # Check driver bindings
        self._check_driver_bindings()
    
    def _parse_lspci_output(self, output: str):
        """Parse lspci output to extract device information"""
        devices = []
        current_device = {}
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                if current_device:
                    devices.append(current_device)
                    current_device = {}
                continue
            
            if line.startswith('Slot:'):
                current_device['pci_id'] = line.split()[1]
            elif line.startswith('Class:'):
                # Extract class name and code
                match = re.search(r'Class:\s+(.+?)\s+\[([^\]]+)\]', line)
                if match:
                    current_device['class_name'] = match.group(1)
                    current_device['class_code'] = match.group(2)
            elif line.startswith('Vendor:'):
                # Extract vendor name and ID
                match = re.search(r'Vendor:\s+(.+?)\s+\[([^\]]+)\]', line)
                if match:
                    current_device['vendor_name'] = match.group(1)
                    current_device['vendor_id'] = match.group(2)
            elif line.startswith('Device:'):
                # Extract device name and ID
                match = re.search(r'Device:\s+(.+?)\s+\[([^\]]+)\]', line)
                if match:
                    current_device['device_name'] = match.group(1)
                    current_device['device_id'] = match.group(2)
        
        # Handle last device
        if current_device:
            devices.append(current_device)
        
        # Convert to PCIDevice objects
        for dev_info in devices:
            if all(key in dev_info for key in ['pci_id', 'vendor_id', 'device_id']):
                device = PCIDevice(
                    pci_id=dev_info['pci_id'],
                    vendor_id=dev_info['vendor_id'],
                    device_id=dev_info['device_id'],
                    vendor_name=dev_info.get('vendor_name', 'Unknown'),
                    device_name=dev_info.get('device_name', 'Unknown'),
                    device_type=self._classify_device(dev_info)
                )
                self.devices.append(device)
    
    def _classify_device(self, dev_info: Dict) -> DeviceType:
        """Classify device type based on class and name"""
        class_name = dev_info.get('class_name', '').lower()
        device_name = dev_info.get('device_name', '').lower()
        
        if 'vga' in class_name or '3d' in class_name or any(gpu in device_name for gpu in ['geforce', 'radeon', 'nvidia', 'amd']):
            return DeviceType.GPU
        elif 'nvme' in device_name or 'non-volatile memory' in class_name:
            return DeviceType.NVME
        elif 'network' in class_name or 'ethernet' in class_name:
            return DeviceType.NETWORK
        elif 'audio' in class_name or 'sound' in class_name:
            return DeviceType.AUDIO
        elif 'usb' in class_name:
            return DeviceType.USB
        else:
            return DeviceType.GENERIC
    
    def _scan_iommu_groups(self):
        """Scan IOMMU groups"""
        iommu_dir = Path("/sys/kernel/iommu_groups")
        if not iommu_dir.exists():
            return
        
        for group_dir in iommu_dir.iterdir():
            if group_dir.is_dir() and group_dir.name.isdigit():
                group_id = int(group_dir.name)
                devices_dir = group_dir / "devices"
                
                group_devices = []
                for device_link in devices_dir.iterdir():
                    pci_id = device_link.name
                    device = self.get_device_by_id(pci_id)
                    if device:
                        device.iommu_group = group_id
                        group_devices.append(device)
                
                if group_devices:
                    self.iommu_groups[group_id] = IOMMUGroup(group_id, group_devices)
    
    def _check_driver_bindings(self):
        """Check which devices are bound to which drivers"""
        for device in self.devices:
            driver_path = Path(f"/sys/bus/pci/devices/{device.pci_id}/driver")
            if driver_path.exists() and driver_path.is_symlink():
                driver_name = driver_path.resolve().name
                device.driver = driver_name
                device.bound_to_vfio = driver_name in ['vfio-pci']
    
    def get_device_by_id(self, pci_id: str) -> Optional[PCIDevice]:
        """Get device by PCI ID"""
        for device in self.devices:
            if device.pci_id == pci_id:
                return device
        return None
    
    def get_devices_by_type(self, device_type: DeviceType) -> List[PCIDevice]:
        """Get all devices of a specific type"""
        return [d for d in self.devices if d.device_type == device_type]
    
    def get_gpus(self) -> List[PCIDevice]:
        """Get all GPU devices"""
        return self.get_devices_by_type(DeviceType.GPU)
    
    def get_nvme_devices(self) -> List[PCIDevice]:
        """Get all NVMe devices"""
        return self.get_devices_by_type(DeviceType.NVME)
    
    def is_iommu_enabled(self) -> bool:
        """Check if IOMMU is enabled"""
        # Check kernel command line
        try:
            with open('/proc/cmdline', 'r') as f:
                cmdline = f.read()
            return 'iommu=on' in cmdline or 'intel_iommu=on' in cmdline or 'amd_iommu=on' in cmdline
        except:
            return False
    
    def is_vfio_available(self) -> bool:
        """Check if VFIO modules are loaded"""
        try:
            lsmod_output = self._run_command(['lsmod'])
            return 'vfio_pci' in lsmod_output
        except:
            return False
    
    def bind_device_to_vfio(self, device: PCIDevice) -> bool:
        """Bind device to vfio-pci driver"""
        try:
            # Unbind from current driver
            if device.driver and device.driver != 'vfio-pci':
                unbind_path = f"/sys/bus/pci/drivers/{device.driver}/unbind"
                with open(unbind_path, 'w') as f:
                    f.write(device.pci_id)
            
            # Bind to vfio-pci
            new_id_path = "/sys/bus/pci/drivers/vfio-pci/new_id"
            with open(new_id_path, 'w') as f:
                f.write(device.vendor_device_id)
            
            # Update device status
            self._check_driver_bindings()
            return device.bound_to_vfio
            
        except Exception as e:
            print(f"Failed to bind {device.pci_id} to vfio-pci: {e}")
            return False
    
    def unbind_device_from_vfio(self, device: PCIDevice) -> bool:
        """Unbind device from vfio-pci driver"""
        try:
            if device.bound_to_vfio:
                unbind_path = "/sys/bus/pci/drivers/vfio-pci/unbind"
                with open(unbind_path, 'w') as f:
                    f.write(device.pci_id)
            
            # Update device status
            self._check_driver_bindings()
            return not device.bound_to_vfio
            
        except Exception as e:
            print(f"Failed to unbind {device.pci_id} from vfio-pci: {e}")
            return False
    
    def validate_passthrough_readiness(self) -> Tuple[bool, List[str]]:
        """Validate system is ready for PCI passthrough"""
        issues = []
        
        # Check IOMMU
        if not self.is_iommu_enabled():
            issues.append("IOMMU is not enabled. Add intel_iommu=on or amd_iommu=on to kernel cmdline.")
        
        # Check VFIO
        if not self.is_vfio_available():
            issues.append("VFIO modules not loaded. Run: modprobe vfio-pci")
        
        # Check for IOMMU groups
        if not self.iommu_groups:
            issues.append("No IOMMU groups found. Check IOMMU support in BIOS/UEFI.")
        
        return len(issues) == 0, issues
    
    def generate_hostdev_xml(self, device: PCIDevice) -> str:
        """Generate libvirt hostdev XML for device passthrough"""
        # Parse PCI address
        match = re.match(r'(\w{4}):(\w{2}):(\w{2})\.(\w)', device.pci_id)
        if not match:
            raise ValueError(f"Invalid PCI ID format: {device.pci_id}")
        
        domain, bus, slot, function = match.groups()
        
        # Convert to decimal for XML
        domain_dec = str(int(domain, 16))
        bus_dec = str(int(bus, 16))  
        slot_dec = str(int(slot, 16))
        func_dec = str(int(function, 16))
        
        return f"""
            <hostdev mode='subsystem' type='pci' managed='yes'>
              <source>
                <address domain='0x{domain}' bus='0x{bus}' slot='0x{slot}' function='0x{function}'/>
              </source>
              <address type='pci' domain='0x0000' bus='0x00' slot='0x06' function='0x0'/>
            </hostdev>
        """.strip()
    
    def print_device_summary(self):
        """Print a summary of available devices"""
        print("PCI Passthrough Device Summary")
        print("=" * 50)
        
        # System status
        ready, issues = self.validate_passthrough_readiness()
        print(f"System Status: {'✅ Ready' if ready else '❌ Issues found'}")
        for issue in issues:
            print(f"  ⚠️  {issue}")
        print()
        
        # GPUs
        gpus = self.get_gpus()
        print(f"GPUs ({len(gpus)}):")
        for gpu in gpus:
            status = "🔒 VFIO" if gpu.bound_to_vfio else f"🔧 {gpu.driver or 'unbound'}"
            iommu = f"IOMMU:{gpu.iommu_group}" if gpu.iommu_group is not None else "No IOMMU"
            print(f"  {gpu.pci_id} - {gpu.device_name} [{status}] [{iommu}]")
        print()
        
        # NVMe devices
        nvmes = self.get_nvme_devices()
        print(f"NVMe Devices ({len(nvmes)}):")
        for nvme in nvmes:
            status = "🔒 VFIO" if nvme.bound_to_vfio else f"🔧 {nvme.driver or 'unbound'}"
            iommu = f"IOMMU:{nvme.iommu_group}" if nvme.iommu_group is not None else "No IOMMU"
            print(f"  {nvme.pci_id} - {nvme.device_name} [{status}] [{iommu}]")
        print()


# Convenience functions for common operations

def scan_system() -> PassthroughManager:
    """Scan system and return PassthroughManager"""
    return PassthroughManager()


def find_gpu(vendor: str = None, model: str = None) -> Optional[PCIDevice]:
    """Find GPU by vendor/model"""
    manager = PassthroughManager()
    gpus = manager.get_gpus()
    
    for gpu in gpus:
        if vendor and vendor.lower() not in gpu.vendor_name.lower():
            continue
        if model and model.lower() not in gpu.device_name.lower():
            continue
        return gpu
    
    return None


def find_nvme(model: str = None) -> Optional[PCIDevice]:
    """Find NVMe device by model"""
    manager = PassthroughManager()
    nvmes = manager.get_nvme_devices()
    
    for nvme in nvmes:
        if model and model.lower() not in nvme.device_name.lower():
            continue
        return nvme
    
    return nvmes[0] if nvmes else None
