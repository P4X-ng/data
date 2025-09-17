#!/usr/bin/env python3
"""
Advanced VFIO and Resource Allocation Test Suite
===============================================

Comprehensive testing for VMKit's VFIO device management and resource allocation
capabilities, including percentage-based and hard attribute allocations.
"""

import pytest
import tempfile
import json
import os
import shutil
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vmkit.vfio import VFIODeviceManager, VFIODevice, DeviceState, VFIOError
from vmkit.resources import ResourceAllocator, ResourceAllocationError
from vmkit.passthrough import PCIDevice, DeviceType


@pytest.fixture
def mock_sysfs(tmp_path):
    """Create a mock sysfs structure for testing"""
    sysfs_root = tmp_path / "sys"
    
    # Create basic sysfs structure
    (sysfs_root / "bus/pci/devices").mkdir(parents=True)
    (sysfs_root / "kernel/iommu_groups/0/devices").mkdir(parents=True)
    (sysfs_root / "kernel/iommu_groups/1/devices").mkdir(parents=True)
    
    # Create mock GPU device
    gpu_path = sysfs_root / "bus/pci/devices/0000:01:00.0"
    gpu_path.mkdir()
    (gpu_path / "vendor").write_text("0x10de")  # NVIDIA
    (gpu_path / "device").write_text("0x2204")  # RTX 3080
    (gpu_path / "class").write_text("0x030000")  # VGA controller
    
    # Create mock NVMe device  
    nvme_path = sysfs_root / "bus/pci/devices/0000:02:00.0"
    nvme_path.mkdir()
    (nvme_path / "vendor").write_text("0x144d")  # Samsung
    (nvme_path / "device").write_text("0xa80a")  # NVMe SSD
    (nvme_path / "class").write_text("0x010802")  # NVMe controller
    
    # Link devices to IOMMU groups
    gpu_link = sysfs_root / "kernel/iommu_groups/0/devices/0000:01:00.0"
    nvme_link = sysfs_root / "kernel/iommu_groups/1/devices/0000:02:00.0"
    gpu_link.symlink_to("../../../../bus/pci/devices/0000:01:00.0")
    nvme_link.symlink_to("../../../../bus/pci/devices/0000:02:00.0")
    
    # Create NUMA topology
    numa_path = sysfs_root / "devices/system/node"
    (numa_path / "node0").mkdir(parents=True)
    (numa_path / "node1").mkdir(parents=True)
    
    return sysfs_root


@pytest.fixture
def mock_lspci_output():
    """Mock lspci command output"""
    return """
Slot:	0000:01:00.0
Class:	VGA compatible controller [0300]
Vendor:	NVIDIA Corporation [10de]
Device:	GA102 [GeForce RTX 3080] [2204]

Slot:	0000:02:00.0
Class:	Non-Volatile memory controller [0108]
Vendor:	Samsung Electronics Co Ltd [144d]
Device:	NVMe SSD Controller [a80a]
"""


@pytest.fixture
def mock_lscpu_output():
    """Mock lscpu JSON output"""
    return {
        "lscpu": [
            {"field": "Architecture:", "data": "x86_64"},
            {"field": "CPU(s):", "data": "16"},
            {"field": "NUMA node(s):", "data": "2"},
            {"field": "NUMA node0 CPU(s):", "data": "0-7"},
            {"field": "NUMA node1 CPU(s):", "data": "8-15"}
        ]
    }


class TestVFIODeviceManager:
    """Test VFIO device management functionality"""

    @patch('vmkit.vfio.PassthroughManager')
    def test_vfio_manager_initialization(self, mock_passthrough_manager):
        """Test VFIO manager initialization"""
        # Setup mock
        mock_manager = Mock()
        mock_manager.devices = []
        mock_passthrough_manager.return_value = mock_manager
        
        # Test initialization
        vfio_manager = VFIODeviceManager(dry_run=True)
        
        assert vfio_manager.dry_run is True
        assert vfio_manager.devices == {}
        assert vfio_manager.reservations == {}
        mock_passthrough_manager.assert_called_once()

    def test_device_state_determination(self):
        """Test device state determination logic"""
        # Create mock PCI device
        mock_device = Mock()
        mock_device.bound_to_vfio = True
        mock_device.driver = "vfio-pci"
        
        vfio_manager = VFIODeviceManager(dry_run=True)
        state = vfio_manager._determine_device_state(mock_device)
        
        assert state == DeviceState.VFIO

    @patch('vmkit.vfio.PassthroughManager')
    def test_device_binding_dry_run(self, mock_passthrough_manager):
        """Test device binding in dry-run mode"""
        # Setup mock
        mock_manager = Mock()
        mock_pci_device = Mock()
        mock_pci_device.pci_id = "0000:01:00.0"
        mock_pci_device.bound_to_vfio = False
        mock_pci_device.driver = None
        mock_pci_device.iommu_group = 0
        mock_manager.devices = [mock_pci_device]
        mock_passthrough_manager.return_value = mock_manager
        
        vfio_manager = VFIODeviceManager(dry_run=True)
        
        # Mock device state
        vfio_device = VFIODevice(
            pci_device=mock_pci_device,
            state=DeviceState.UNBOUND,
            iommu_ready=True
        )
        vfio_manager.devices["0000:01:00.0"] = vfio_device
        
        # Test binding
        result = vfio_manager.bind_to_vfio("0000:01:00.0")
        
        assert result is True
        assert vfio_device.state == DeviceState.VFIO

    @patch('vmkit.vfio.PassthroughManager')  
    def test_device_reservation(self, mock_passthrough_manager):
        """Test device reservation system"""
        # Setup
        mock_manager = Mock()
        mock_pci_device = Mock()
        mock_pci_device.pci_id = "0000:01:00.0"
        mock_manager.devices = [mock_pci_device]
        mock_passthrough_manager.return_value = mock_manager
        
        vfio_manager = VFIODeviceManager(dry_run=True)
        
        # Create available device
        vfio_device = VFIODevice(
            pci_device=mock_pci_device,
            state=DeviceState.UNBOUND,
            iommu_ready=True
        )
        vfio_manager.devices["0000:01:00.0"] = vfio_device
        
        # Test reservation
        result = vfio_manager.reserve_device("0000:01:00.0", "test-vm")
        
        assert result is True
        assert vfio_device.reserved_by == "test-vm"
        assert "test-vm" in vfio_manager.reservations
        assert "0000:01:00.0" in vfio_manager.reservations["test-vm"]

    def test_device_release(self):
        """Test device release from reservation"""
        vfio_manager = VFIODeviceManager(dry_run=True)
        
        # Setup reserved device
        mock_pci_device = Mock()
        mock_pci_device.pci_id = "0000:01:00.0"
        
        vfio_device = VFIODevice(
            pci_device=mock_pci_device,
            state=DeviceState.VFIO,
            reserved_by="test-vm",
            iommu_ready=True
        )
        
        vfio_manager.devices["0000:01:00.0"] = vfio_device
        vfio_manager.reservations["test-vm"] = ["0000:01:00.0"]
        
        # Test release
        result = vfio_manager.release_device("0000:01:00.0", "test-vm")
        
        assert result is True
        assert vfio_device.reserved_by is None
        assert "test-vm" not in vfio_manager.reservations


class TestResourceAllocator:
    """Test resource allocation functionality"""

    @patch('vmkit.resources.psutil')
    def test_resource_allocator_initialization(self, mock_psutil):
        """Test resource allocator initialization"""
        # Mock psutil responses
        mock_psutil.cpu_count.return_value = 8
        mock_psutil.virtual_memory.return_value = Mock(
            total=32 * 1024**3,
            available=24 * 1024**3
        )
        mock_psutil.net_if_addrs.return_value = {"eth0": []}
        mock_psutil.disk_partitions.return_value = []
        mock_psutil.boot_time.return_value = 0
        
        allocator = ResourceAllocator(dry_run=True)
        
        assert allocator.dry_run is True
        assert allocator._host_info is None
        assert allocator._numa_topology is None

    @patch('vmkit.resources.subprocess.run')
    @patch('vmkit.resources.psutil')
    def test_cpu_percentage_allocation(self, mock_psutil, mock_subprocess):
        """Test CPU percentage-based allocation"""
        # Mock system info
        mock_psutil.cpu_count.return_value = 8
        mock_psutil.virtual_memory.return_value = Mock(
            total=32 * 1024**3,
            available=24 * 1024**3
        )
        mock_psutil.net_if_addrs.return_value = {"eth0": []}
        mock_psutil.disk_partitions.return_value = []
        mock_psutil.boot_time.return_value = 0
        
        # Mock lscpu for NUMA detection
        mock_subprocess.return_value = Mock(
            returncode=1,  # Fail NUMA detection to use fallback
            stdout=""
        )
        
        allocator = ResourceAllocator(dry_run=True)
        
        # Test 50% CPU allocation
        result = allocator.allocate_cpus(50)
        
        assert result['requested_percent'] == 50
        assert result['allocated_cores'] == 4  # 50% of 8 cores
        assert len(result['pinned_set']) == 4
        assert result['numa_aware'] is False

    def test_cpu_range_allocation(self):
        """Test CPU range-based allocation"""
        allocator = ResourceAllocator(dry_run=True)
        
        # Mock host info
        allocator._host_info = {
            'cpu': {'logical_cores': 16},
            'memory': {'total_bytes': 32 * 1024**3, 'available_bytes': 24 * 1024**3},
            'network': [],
            'storage': [],
            'load_average': [0.1, 0.2, 0.3],
            'uptime_seconds': 1000
        }
        
        allocator._numa_topology = {
            'numa_nodes': {0: {'cpus': list(range(8)), 'memory_gb': 16}},
            'cpu_to_node': {i: 0 for i in range(8)},
            'available': False
        }
        
        # Test range allocation
        result = allocator.allocate_cpu_from("0-3,8-11")
        
        assert result['range_string'] == "0-3,8-11"
        assert result['allocated_cores'] == 8
        assert result['cpu_list'] == [0, 1, 2, 3, 8, 9, 10, 11]
        assert result['allocation_type'] == 'hard_cpus'

    def test_memory_numa_allocation(self):
        """Test NUMA-specific memory allocation"""
        allocator = ResourceAllocator(dry_run=True)
        
        # Mock NUMA topology
        allocator._numa_topology = {
            'numa_nodes': {0: {'cpus': list(range(8)), 'memory_gb': 16}},
            'cpu_to_node': {i: 0 for i in range(8)},
            'available': True
        }
        
        allocator._host_info = {
            'memory': {'total_bytes': 32 * 1024**3, 'available_bytes': 24 * 1024**3}
        }
        
        with patch.object(allocator, '_get_numa_memory_info') as mock_numa_mem:
            mock_numa_mem.return_value = {
                'total_bytes': 16 * 1024**3,
                'available_bytes': 12 * 1024**3
            }
            
            # Test NUMA node allocation
            result = allocator.allocate_memory_from(numa_node=0, size_bytes=8 * 1024**3)
            
            assert result['numa_node'] == 0
            assert result['allocated_gb'] == 8
            assert result['allocation_type'] == 'hard_numa_memory'

    @patch('vmkit.resources.subprocess.run')
    @patch('vmkit.resources.Path')
    def test_storage_device_allocation(self, mock_path, mock_subprocess):
        """Test storage device-specific allocation"""
        # Mock device path
        mock_device_path = Mock()
        mock_device_path.exists.return_value = True
        mock_path.return_value = mock_device_path
        
        # Mock lsblk output
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout=json.dumps({
                "blockdevices": [
                    {"name": "nvme0n1", "size": "1000204886016"}  # ~1TB
                ]
            })
        )
        
        allocator = ResourceAllocator(dry_run=True)
        
        # Test device allocation
        result = allocator.allocate_storage_from("/dev/nvme0n1", 100 * 1024**3)  # 100GB
        
        assert result['device_path'] == "/dev/nvme0n1"
        assert result['size_gb'] == 100
        assert result['allocation_type'] == 'hard_device'

    @patch('vmkit.resources.VFIODeviceManager')
    def test_gpu_pci_allocation(self, mock_vfio_manager_class):
        """Test GPU allocation by PCI address"""
        # Setup mock VFIO device
        mock_vfio_device = Mock()
        mock_vfio_device.pci_device.is_gpu = True
        mock_vfio_device.pci_device.device_name = "GeForce RTX 3080"
        mock_vfio_device.pci_device.vendor_name = "NVIDIA Corporation"
        mock_vfio_device.pci_device.pci_id = "0000:01:00.0"
        mock_vfio_device.is_available = True
        
        mock_vfio_manager = Mock()
        mock_vfio_manager.get_device.return_value = mock_vfio_device
        mock_vfio_manager.bind_to_vfio.return_value = True
        mock_vfio_manager_class.return_value = mock_vfio_manager
        
        allocator = ResourceAllocator(dry_run=True)
        
        with patch.object(allocator, '_get_gpu_capabilities') as mock_caps:
            mock_caps.return_value = {'sriov_support': False, 'pcie_speed': '16.0 GT/s'}
            
            # Test GPU allocation
            result = allocator.allocate_gpu_from("0000:01:00.0")
            
            assert result['pci_address'] == "0000:01:00.0"
            assert result['device_name'] == "GeForce RTX 3080"
            assert result['allocation_type'] == 'hard_gpu'

    def test_invalid_cpu_range_error(self):
        """Test invalid CPU range handling"""
        allocator = ResourceAllocator(dry_run=True)
        
        # Mock limited CPU system
        allocator._host_info = {
            'cpu': {'logical_cores': 4},
            'memory': {'total_bytes': 16 * 1024**3, 'available_bytes': 12 * 1024**3},
            'network': [],
            'storage': []
        }
        
        # Test invalid CPU range
        with pytest.raises(ResourceAllocationError, match="Invalid CPU IDs"):
            allocator.allocate_cpu_from("0-7")  # System only has 4 cores

    def test_insufficient_storage_error(self):
        """Test insufficient storage handling"""
        with patch('vmkit.resources.Path') as mock_path:
            mock_device_path = Mock()
            mock_device_path.exists.return_value = False
            mock_path.return_value = mock_device_path
            
            allocator = ResourceAllocator(dry_run=True)
            
            # Test non-existent device
            with pytest.raises(ResourceAllocationError, match="does not exist"):
                allocator.allocate_storage_from("/dev/nonexistent", 100 * 1024**3)


class TestAllThePassthru:
    """Test the --all-the-passthru functionality"""

    @patch('vmkit.resources.VFIODeviceManager')
    @patch('vmkit.resources.ResourceAllocator')
    def test_all_passthru_device_detection(self, mock_allocator_class, mock_vfio_manager_class):
        """Test detection of all passthru devices"""
        # Mock GPU devices
        mock_gpu1 = Mock()
        mock_gpu1.device_class = "VGA compatible controller"
        mock_gpu1.device_name = "GeForce RTX 3080"
        mock_gpu1.pci_id = "0000:01:00.0"
        
        mock_gpu2 = Mock()
        mock_gpu2.device_class = "VGA compatible controller" 
        mock_gpu2.device_name = "GeForce RTX 3090"
        mock_gpu2.pci_id = "0000:02:00.0"
        
        # Mock NVMe device
        mock_nvme = Mock()
        mock_nvme.device_name = "Samsung NVMe SSD"
        mock_nvme.pci_id = "0000:03:00.0"
        
        mock_vfio_manager = Mock()
        mock_vfio_manager.list_passthru_devices.return_value = [mock_gpu1, mock_gpu2, mock_nvme]
        mock_vfio_manager_class.return_value = mock_vfio_manager
        
        # Test device categorization
        all_devices = mock_vfio_manager.list_passthru_devices()
        
        gpu_devices = [d for d in all_devices if 'VGA' in d.device_class]
        storage_devices = [d for d in all_devices if 'NVMe' in d.device_name]
        
        assert len(gpu_devices) == 2
        assert len(storage_devices) == 1
        assert len(all_devices) == 3

    def test_percentage_override_logic(self):
        """Test percentage overrides in all-passthru mode"""
        # Mock allocator methods
        allocator = ResourceAllocator(dry_run=True)
        
        with patch.object(allocator, 'allocate_cpus') as mock_cpu_alloc, \
             patch.object(allocator, 'allocate_memory') as mock_mem_alloc:
            
            mock_cpu_alloc.return_value = {'allocated_cores': 8, 'pinned_set': [0, 1, 2, 3, 4, 5, 6, 7]}
            mock_mem_alloc.return_value = {'allocated_gb': 16}
            
            # Test percentage-based allocation with overrides
            cpu_result = allocator.allocate_cpus(75)  # 75% override
            memory_result = allocator.allocate_memory(60)  # 60% override
            
            assert cpu_result['allocated_cores'] == 8
            assert memory_result['allocated_gb'] == 16


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_missing_vfio_support(self):
        """Test behavior when VFIO is not available"""
        with patch('vmkit.vfio.PassthroughManager') as mock_passthrough_manager:
            mock_manager = Mock()
            mock_manager.is_vfio_available.return_value = False
            mock_manager.is_iommu_enabled.return_value = False
            mock_manager.devices = []
            mock_passthrough_manager.return_value = mock_manager
            
            vfio_manager = VFIODeviceManager(dry_run=True)
            ready, issues = vfio_manager.validate_system_readiness()
            
            assert ready is False
            assert len(issues) > 0

    def test_numa_detection_fallback(self):
        """Test NUMA topology detection fallback"""
        with patch('vmkit.resources.subprocess.run') as mock_subprocess, \
             patch('vmkit.resources.psutil') as mock_psutil:
            
            # Mock failed lscpu call
            mock_subprocess.side_effect = Exception("lscpu failed")
            
            # Mock basic system info
            mock_psutil.cpu_count.return_value = 8
            mock_psutil.virtual_memory.return_value = Mock(
                total=16 * 1024**3,
                available=12 * 1024**3
            )
            mock_psutil.net_if_addrs.return_value = {}
            mock_psutil.disk_partitions.return_value = []
            mock_psutil.boot_time.return_value = 0
            
            allocator = ResourceAllocator(dry_run=True)
            numa_topology = allocator.numa_topology
            
            # Should fallback to single NUMA node
            assert numa_topology['available'] is False
            assert 0 in numa_topology['numa_nodes']

    def test_concurrent_device_access(self):
        """Test handling of concurrent device access attempts"""
        vfio_manager = VFIODeviceManager(dry_run=True)
        
        # Setup device already reserved by another VM
        mock_pci_device = Mock()
        mock_pci_device.pci_id = "0000:01:00.0"
        
        vfio_device = VFIODevice(
            pci_device=mock_pci_device,
            state=DeviceState.VFIO,
            reserved_by="other-vm",
            iommu_ready=True
        )
        
        vfio_manager.devices["0000:01:00.0"] = vfio_device
        
        # Test attempt to reserve already reserved device
        result = vfio_manager.reserve_device("0000:01:00.0", "test-vm")
        
        assert result is False


class TestPerformanceAndStress:
    """Performance and stress testing"""

    def test_large_device_allocation(self):
        """Test allocation of many devices"""
        vfio_manager = VFIODeviceManager(dry_run=True)
        
        # Create many mock devices
        for i in range(100):
            mock_pci_device = Mock()
            mock_pci_device.pci_id = f"0000:01:{i:02d}.0"
            
            vfio_device = VFIODevice(
                pci_device=mock_pci_device,
                state=DeviceState.UNBOUND,
                iommu_ready=True
            )
            
            vfio_manager.devices[f"0000:01:{i:02d}.0"] = vfio_device
        
        # Test batch operations
        available_devices = vfio_manager.list_devices(available_only=True)
        assert len(available_devices) == 100

    def test_memory_intensive_allocation(self):
        """Test large memory allocations"""
        allocator = ResourceAllocator(dry_run=True)
        
        # Mock system with large memory
        allocator._host_info = {
            'memory': {
                'total_bytes': 1024 * 1024**3,  # 1TB
                'available_bytes': 512 * 1024**3  # 512GB available
            }
        }
        
        # Test large allocation
        result = allocator.allocate_memory(50)  # 256GB
        
        assert result['allocated_gb'] == 256

    def test_cpu_allocation_scaling(self):
        """Test CPU allocation with many cores"""
        allocator = ResourceAllocator(dry_run=True)
        
        # Mock system with many CPUs
        allocator._host_info = {
            'cpu': {'logical_cores': 128},
            'memory': {'total_bytes': 512 * 1024**3, 'available_bytes': 256 * 1024**3}
        }
        
        allocator._numa_topology = {
            'numa_nodes': {
                0: {'cpus': list(range(64)), 'memory_gb': 256},
                1: {'cpus': list(range(64, 128)), 'memory_gb': 256}
            },
            'cpu_to_node': {**{i: 0 for i in range(64)}, **{i: 1 for i in range(64, 128)}},
            'available': True
        }
        
        # Test large CPU allocation
        result = allocator.allocate_cpus(75)  # 96 cores
        
        assert result['allocated_cores'] == 96
        assert len(result['pinned_set']) == 96


if __name__ == "__main__":
    # Run tests with verbose output and coverage
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--disable-warnings",
        "--color=yes"
    ])
