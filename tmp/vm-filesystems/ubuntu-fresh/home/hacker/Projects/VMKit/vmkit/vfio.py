"""
Advanced VFIO Device Manager for VMKit
======================================

Manages PCI device passthrough with VFIO, including device binding/unbinding,
IOMMU group validation, and GPU resource partitioning. Integrates with both
percentage-based and hard attribute allocation systems.
"""

import logging
import os
import subprocess
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

from .passthrough import PCIDevice, DeviceType, PassthroughManager

logger = logging.getLogger(__name__)


class VFIOError(Exception):
    """VFIO-specific errors"""
    pass


class DeviceState(Enum):
    """Device binding states"""
    UNBOUND = "unbound"
    NATIVE = "native"  # Bound to native driver
    VFIO = "vfio"      # Bound to vfio-pci
    RESERVED = "reserved"  # Reserved for VM
    ERROR = "error"


@dataclass
class VFIODevice:
    """Extended PCI device with VFIO-specific information"""
    pci_device: PCIDevice
    state: DeviceState
    reserved_by: Optional[str] = None  # VM name if reserved
    last_bind_time: Optional[float] = None
    bind_error: Optional[str] = None
    iommu_ready: bool = False
    
    @property
    def pci_id(self) -> str:
        return self.pci_device.pci_id
    
    @property
    def vendor_device_id(self) -> str:
        return self.pci_device.vendor_device_id
    
    @property
    def is_available(self) -> bool:
        """Check if device is available for allocation"""
        return self.state in [DeviceState.UNBOUND, DeviceState.NATIVE] and not self.reserved_by


class VFIODeviceManager:
    """
    Advanced VFIO device manager for VMKit.
    
    Features:
    - Device discovery and classification
    - VFIO driver binding/unbinding automation
    - GPU resource partitioning and SR-IOV support
    - IOMMU group validation and conflict detection
    - Device reservation system for VMs
    """
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize VFIO device manager.
        
        Args:
            dry_run: If True, don't actually bind/unbind devices
        """
        self.dry_run = dry_run
        self.passthrough_manager = PassthroughManager()
        self.devices: Dict[str, VFIODevice] = {}
        self.reservations: Dict[str, List[str]] = {}  # vm_name -> [pci_ids]
        
        # Initialize device discovery
        self._discover_devices()
        
        logger.info(f"VFIODeviceManager initialized (dry_run={dry_run})")
    
    def _discover_devices(self):
        """Discover and classify all PCI devices"""
        logger.debug("Discovering PCI devices for VFIO management...")
        
        self.devices = {}
        for pci_device in self.passthrough_manager.devices:
            # Determine current state
            state = self._determine_device_state(pci_device)
            
            # Check IOMMU readiness
            iommu_ready = self._check_iommu_readiness(pci_device)
            
            vfio_device = VFIODevice(
                pci_device=pci_device,
                state=state,
                iommu_ready=iommu_ready
            )
            
            self.devices[pci_device.pci_id] = vfio_device
        
        logger.info(f"Discovered {len(self.devices)} PCI devices for VFIO management")
    
    def _determine_device_state(self, device: PCIDevice) -> DeviceState:
        """Determine current binding state of a device"""
        if device.bound_to_vfio:
            return DeviceState.VFIO
        elif device.driver:
            return DeviceState.NATIVE
        else:
            return DeviceState.UNBOUND
    
    def _check_iommu_readiness(self, device: PCIDevice) -> bool:
        """Check if device is ready for IOMMU/VFIO passthrough"""
        if not self.passthrough_manager.is_iommu_enabled():
            return False
        
        if device.iommu_group is None:
            return False
        
        # Check if IOMMU group is isolated (safe for passthrough)
        if device.iommu_group in self.passthrough_manager.iommu_groups:
            group = self.passthrough_manager.iommu_groups[device.iommu_group]
            return group.is_isolated
        
        return False
    
    def list_devices(self, device_type: Optional[DeviceType] = None, 
                    available_only: bool = False) -> List[VFIODevice]:
        """
        List VFIO devices with optional filtering.
        
        Args:
            device_type: Filter by device type (GPU, NVME, etc.)
            available_only: Only return available devices
            
        Returns:
            List of VFIO devices
        """
        devices = list(self.devices.values())
        
        if device_type:
            devices = [d for d in devices if d.pci_device.device_type == device_type]
        
        if available_only:
            devices = [d for d in devices if d.is_available]
        
        logger.debug(f"Listed {len(devices)} devices (type={device_type}, available_only={available_only})")
        return devices
    
    def list_passthru_devices(self) -> List[PCIDevice]:
        """Get all devices suitable for passthrough (backward compatibility)"""
        suitable_devices = []
        for vfio_device in self.devices.values():
            if vfio_device.iommu_ready:
                suitable_devices.append(vfio_device.pci_device)
        return suitable_devices
    
    def get_device(self, pci_id: str) -> Optional[VFIODevice]:
        """Get VFIO device by PCI ID"""
        return self.devices.get(pci_id)
    
    def bind_to_vfio(self, pci_id: str) -> bool:
        """
        Bind device to vfio-pci driver.
        
        Args:
            pci_id: PCI device ID (e.g., "0000:01:00.0")
            
        Returns:
            True if successful
        """
        logger.info(f"Binding device {pci_id} to vfio-pci driver...")
        
        device = self.devices.get(pci_id)
        if not device:
            logger.error(f"Device {pci_id} not found")
            return False
        
        if device.state == DeviceState.VFIO:
            logger.info(f"Device {pci_id} already bound to vfio-pci")
            return True
        
        if not device.iommu_ready:
            logger.warning(f"Device {pci_id} is not IOMMU ready - binding may fail")
        
        if self.dry_run:
            logger.info(f"DRY RUN: Would bind {pci_id} to vfio-pci")
            device.state = DeviceState.VFIO
            device.last_bind_time = time.time()
            return True
        
        try:
            # Use passthrough manager to do the actual binding
            success = self.passthrough_manager.bind_device_to_vfio(device.pci_device)
            
            if success:
                device.state = DeviceState.VFIO
                device.last_bind_time = time.time()
                device.bind_error = None
                logger.info(f"Successfully bound {pci_id} to vfio-pci")
            else:
                device.state = DeviceState.ERROR
                device.bind_error = "Failed to bind to vfio-pci"
                logger.error(f"Failed to bind {pci_id} to vfio-pci")
            
            return success
            
        except Exception as e:
            device.state = DeviceState.ERROR
            device.bind_error = str(e)
            logger.error(f"Exception while binding {pci_id} to vfio-pci: {e}")
            return False
    
    def unbind_from_vfio(self, pci_id: str) -> bool:
        """
        Unbind device from vfio-pci driver.
        
        Args:
            pci_id: PCI device ID
            
        Returns:
            True if successful
        """
        logger.info(f"Unbinding device {pci_id} from vfio-pci driver...")
        
        device = self.devices.get(pci_id)
        if not device:
            logger.error(f"Device {pci_id} not found")
            return False
        
        if device.state != DeviceState.VFIO:
            logger.info(f"Device {pci_id} is not bound to vfio-pci")
            return True
        
        if self.dry_run:
            logger.info(f"DRY RUN: Would unbind {pci_id} from vfio-pci")
            device.state = DeviceState.UNBOUND
            return True
        
        try:
            success = self.passthrough_manager.unbind_device_from_vfio(device.pci_device)
            
            if success:
                device.state = DeviceState.UNBOUND
                device.bind_error = None
                logger.info(f"Successfully unbound {pci_id} from vfio-pci")
            else:
                device.state = DeviceState.ERROR
                device.bind_error = "Failed to unbind from vfio-pci"
                logger.error(f"Failed to unbind {pci_id} from vfio-pci")
            
            return success
            
        except Exception as e:
            device.state = DeviceState.ERROR
            device.bind_error = str(e)
            logger.error(f"Exception while unbinding {pci_id} from vfio-pci: {e}")
            return False
    
    def reserve_device(self, pci_id: str, vm_name: str) -> bool:
        """
        Reserve device for exclusive use by a VM.
        
        Args:
            pci_id: PCI device ID
            vm_name: Name of VM reserving the device
            
        Returns:
            True if successful
        """
        logger.info(f"Reserving device {pci_id} for VM '{vm_name}'")
        
        device = self.devices.get(pci_id)
        if not device:
            logger.error(f"Device {pci_id} not found")
            return False
        
        if not device.is_available:
            logger.error(f"Device {pci_id} is not available (state={device.state}, reserved_by={device.reserved_by})")
            return False
        
        # Reserve the device
        device.reserved_by = vm_name
        
        # Track reservation by VM
        if vm_name not in self.reservations:
            self.reservations[vm_name] = []
        self.reservations[vm_name].append(pci_id)
        
        logger.info(f"Device {pci_id} reserved for VM '{vm_name}'")
        return True
    
    def release_device(self, pci_id: str, vm_name: str) -> bool:
        """
        Release device reservation.
        
        Args:
            pci_id: PCI device ID
            vm_name: Name of VM releasing the device
            
        Returns:
            True if successful
        """
        logger.info(f"Releasing device {pci_id} from VM '{vm_name}'")
        
        device = self.devices.get(pci_id)
        if not device:
            logger.error(f"Device {pci_id} not found")
            return False
        
        if device.reserved_by != vm_name:
            logger.warning(f"Device {pci_id} not reserved by VM '{vm_name}' (reserved_by={device.reserved_by})")
            return False
        
        # Release reservation
        device.reserved_by = None
        
        # Remove from VM's reservation list
        if vm_name in self.reservations and pci_id in self.reservations[vm_name]:
            self.reservations[vm_name].remove(pci_id)
            if not self.reservations[vm_name]:
                del self.reservations[vm_name]
        
        logger.info(f"Device {pci_id} released from VM '{vm_name}'")
        return True
    
    def release_all_devices(self, vm_name: str) -> bool:
        """
        Release all devices reserved by a VM.
        
        Args:
            vm_name: Name of VM to release devices from
            
        Returns:
            True if all devices released successfully
        """
        if vm_name not in self.reservations:
            logger.info(f"No devices reserved by VM '{vm_name}'")
            return True
        
        pci_ids = self.reservations[vm_name].copy()
        success = True
        
        for pci_id in pci_ids:
            if not self.release_device(pci_id, vm_name):
                success = False
        
        logger.info(f"Released {len(pci_ids)} devices from VM '{vm_name}' (success={success})")
        return success
    
    def allocate_gpu(self, percent: int) -> List[PCIDevice]:
        """
        Allocate GPU resources based on percentage.
        
        Args:
            percent: Percentage of GPU resources to allocate
            
        Returns:
            List of allocated GPU devices
        """
        logger.info(f"Allocating {percent}% of GPU resources...")
        
        gpu_devices = self.list_devices(DeviceType.GPU, available_only=True)
        if not gpu_devices:
            logger.warning("No available GPU devices found")
            return []
        
        # Calculate number of GPUs to allocate
        total_gpus = len(gpu_devices)
        allocated_count = max(1, int(total_gpus * percent / 100))
        
        # Select best GPUs (prefer discrete over integrated)
        gpu_devices.sort(key=lambda d: d.pci_device.vendor_name, reverse=True)  # NVIDIA/AMD first
        selected_gpus = gpu_devices[:allocated_count]
        
        # Bind selected GPUs to VFIO
        allocated_devices = []
        for gpu_device in selected_gpus:
            if self.bind_to_vfio(gpu_device.pci_id):
                allocated_devices.append(gpu_device.pci_device)
        
        logger.info(f"GPU allocation: {len(allocated_devices)} devices ({percent}% of {total_gpus})")
        return allocated_devices
    
    def get_device_status(self) -> Dict[str, Any]:
        """Get comprehensive device status report"""
        status = {
            'total_devices': len(self.devices),
            'vfio_ready': self.passthrough_manager.is_vfio_available(),
            'iommu_enabled': self.passthrough_manager.is_iommu_enabled(),
            'devices_by_state': {},
            'devices_by_type': {},
            'reservations': dict(self.reservations),
            'devices': []
        }
        
        # Count by state
        for device in self.devices.values():
            state = device.state.value
            status['devices_by_state'][state] = status['devices_by_state'].get(state, 0) + 1
            
            # Count by type
            device_type = device.pci_device.device_type.value
            status['devices_by_type'][device_type] = status['devices_by_type'].get(device_type, 0) + 1
            
            # Device details
            status['devices'].append({
                'pci_id': device.pci_id,
                'vendor_name': device.pci_device.vendor_name,
                'device_name': device.pci_device.device_name,
                'device_type': device_type,
                'state': state,
                'reserved_by': device.reserved_by,
                'iommu_ready': device.iommu_ready,
                'iommu_group': device.pci_device.iommu_group,
                'bind_error': device.bind_error
            })
        
        return status
    
    def print_device_status(self):
        """Print comprehensive device status to console"""
        status = self.get_device_status()
        
        print("VFIO Device Manager Status")
        print("=" * 50)
        
        # System status
        print(f"System Status:")
        print(f"  IOMMU Enabled: {'✅' if status['iommu_enabled'] else '❌'}")
        print(f"  VFIO Available: {'✅' if status['vfio_ready'] else '❌'}")
        print(f"  Total Devices: {status['total_devices']}")
        print()
        
        # Devices by state
        print("Devices by State:")
        for state, count in status['devices_by_state'].items():
            print(f"  {state.title()}: {count}")
        print()
        
        # Devices by type
        print("Devices by Type:")
        for device_type, count in status['devices_by_type'].items():
            print(f"  {device_type.upper()}: {count}")
        print()
        
        # Reservations
        if status['reservations']:
            print("Active Reservations:")
            for vm_name, pci_ids in status['reservations'].items():
                print(f"  {vm_name}: {', '.join(pci_ids)}")
        else:
            print("No active reservations")
        print()
        
        # Device details
        print("Device Details:")
        print(f"{'PCI ID':<12} {'Type':<8} {'State':<8} {'Device Name':<30} {'Reserved':<15}")
        print("-" * 80)
        
        for device_info in status['devices']:
            reserved = device_info['reserved_by'] or '-'
            print(f"{device_info['pci_id']:<12} {device_info['device_type']:<8} "
                  f"{device_info['state']:<8} {device_info['device_name'][:29]:<30} {reserved:<15}")
    
    def validate_system_readiness(self) -> Tuple[bool, List[str]]:
        """
        Validate system is ready for VFIO operations.
        
        Returns:
            Tuple of (is_ready, list_of_issues)
        """
        return self.passthrough_manager.validate_passthrough_readiness()
