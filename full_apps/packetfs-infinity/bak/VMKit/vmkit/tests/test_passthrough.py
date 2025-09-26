#!/usr/bin/env python3
"""
Test suite for VMKit device passthrough capabilities.
Tests GPU, NVMe, and other PCI device passthrough features.
"""

import pytest
import os
import time
from pathlib import Path
from vmkit.core import SecureVM, VMError
from vmkit.passthrough import PassthroughManager, PCIDevice, find_gpu, find_nvme
from vmkit.resources import ResourceAllocator, AllocationError

# Test VM configuration
TEST_VM_NAME = "vmkit-test-passthrough"
TEST_IMAGE = "/tmp/vmkit-test.qcow2"

@pytest.fixture(scope="module")
def test_image():
    """Create a minimal test image."""
    if not Path(TEST_IMAGE).exists():
        os.system(f"qemu-img create -f qcow2 {TEST_IMAGE} 5G")
    yield TEST_IMAGE
    if Path(TEST_IMAGE).exists():
        os.remove(TEST_IMAGE)

@pytest.fixture(scope="module")
def passthrough_manager():
    """Get a PassthroughManager instance."""
    return PassthroughManager()

@pytest.fixture(scope="function")
def vm():
    """Create a test VM and ensure cleanup."""
    try:
        vm = SecureVM(TEST_VM_NAME)
        yield vm
    finally:
        try:
            if vm.is_active():
                vm.stop(force=True)
            if vm.is_defined():
                vm.destroy()
        except Exception:
            pass

def test_list_available_devices(passthrough_manager):
    """Test listing available PCI devices."""
    devices = passthrough_manager.list_devices()
    assert isinstance(devices, list)
    for device in devices:
        assert isinstance(device, PCIDevice)
        assert device.pci_id is not None
        assert device.device_name is not None

def test_gpu_detection():
    """Test GPU auto-detection."""
    gpu = find_gpu()
    if gpu:
        assert isinstance(gpu, PCIDevice)
        assert gpu.pci_id is not None
        assert gpu.device_name is not None
        assert "VGA" in gpu.device_class or "Display" in gpu.device_class
    else:
        pytest.skip("No GPU available for testing")

def test_nvme_detection():
    """Test NVMe device auto-detection."""
    nvme = find_nvme()
    if nvme:
        assert isinstance(nvme, PCIDevice)
        assert nvme.pci_id is not None
        assert nvme.device_name is not None
        assert "NVMe" in nvme.device_name
    else:
        pytest.skip("No NVMe device available for testing")

def test_device_info(passthrough_manager):
    """Test retrieving detailed device information."""
    devices = passthrough_manager.list_devices()
    if not devices:
        pytest.skip("No PCI devices available for testing")
    
    device = devices[0]
    info = passthrough_manager.get_device_info(device.pci_id)
    
    assert info["pci_id"] == device.pci_id
    assert "vendor_id" in info
    assert "device_id" in info
    assert "subsystem_vendor_id" in info
    assert "subsystem_device_id" in info

def test_device_status(passthrough_manager):
    """Test device status checking."""
    devices = passthrough_manager.list_devices()
    if not devices:
        pytest.skip("No PCI devices available for testing")
    
    device = devices[0]
    status = passthrough_manager.get_device_status(device.pci_id)
    
    assert "bound_driver" in status
    assert "iommu_group" in status
    assert "is_bound_to_vfio" in status

def test_gpu_passthrough(test_image, vm, passthrough_manager):
    """Test GPU passthrough if available."""
    gpu = find_gpu()
    if not gpu:
        pytest.skip("No GPU available for testing")
    
    try:
        # Create VM with GPU passthrough
        vm.create_from_image(
            image_path=test_image,
            memory="4G",
            cpus=2,
            passthrough_devices=[gpu]
        )
        
        # Verify GPU is attached
        devices = vm.get_passthrough_devices()
        assert any(d.pci_id == gpu.pci_id for d in devices)
        
        # Test VM startup with GPU
        vm.start()
        assert vm.is_active()
        
        # Give VM time to initialize
        time.sleep(5)
        
        # Verify GPU is still properly attached
        assert vm.is_device_attached(gpu.pci_id)
        
    except VMError as e:
        if "VFIO driver not available" in str(e):
            pytest.skip("VFIO support not available")
        raise

def test_nvme_passthrough(test_image, vm, passthrough_manager):
    """Test NVMe passthrough if available."""
    nvme = find_nvme()
    if not nvme:
        pytest.skip("No NVMe device available for testing")
    
    try:
        # Create VM with NVMe passthrough
        vm.create_from_image(
            image_path=test_image,
            memory="4G",
            cpus=2,
            passthrough_devices=[nvme]
        )
        
        # Verify NVMe is attached
        devices = vm.get_passthrough_devices()
        assert any(d.pci_id == nvme.pci_id for d in devices)
        
        # Test VM startup with NVMe
        vm.start()
        assert vm.is_active()
        
        # Give VM time to initialize
        time.sleep(5)
        
        # Verify NVMe is still properly attached
        assert vm.is_device_attached(nvme.pci_id)
        
    except VMError as e:
        if "VFIO driver not available" in str(e):
            pytest.skip("VFIO support not available")
        raise

def test_multiple_device_passthrough(test_image, vm, passthrough_manager):
    """Test passing through multiple devices."""
    devices = []
    
    # Try to get GPU
    gpu = find_gpu()
    if gpu:
        devices.append(gpu)
    
    # Try to get NVMe
    nvme = find_nvme()
    if nvme:
        devices.append(nvme)
    
    if not devices:
        pytest.skip("No devices available for passthrough testing")
    
    try:
        # Create VM with multiple devices
        vm.create_from_image(
            image_path=test_image,
            memory="4G",
            cpus=2,
            passthrough_devices=devices
        )
        
        # Verify all devices are attached
        attached_devices = vm.get_passthrough_devices()
        for device in devices:
            assert any(d.pci_id == device.pci_id for d in attached_devices)
        
        # Test VM startup
        vm.start()
        assert vm.is_active()
        
        # Give VM time to initialize
        time.sleep(5)
        
        # Verify all devices are still properly attached
        for device in devices:
            assert vm.is_device_attached(device.pci_id)
            
    except VMError as e:
        if "VFIO driver not available" in str(e):
            pytest.skip("VFIO support not available")
        raise

def test_device_hotplug(test_image, vm, passthrough_manager):
    """Test hot-plugging PCI devices if supported."""
    devices = passthrough_manager.list_devices()
    if not devices or not passthrough_manager.supports_hotplug():
        pytest.skip("No devices available or hotplug not supported")
    
    try:
        # Create VM without devices
        vm.create_from_image(
            image_path=test_image,
            memory="4G",
            cpus=2
        )
        
        # Start VM
        vm.start()
        assert vm.is_active()
        
        # Give VM time to initialize
        time.sleep(5)
        
        # Try to hot-plug first available device
        device = devices[0]
        vm.attach_device(device)
        
        # Verify device is attached
        assert vm.is_device_attached(device.pci_id)
        
        # Try to hot-unplug
        vm.detach_device(device)
        
        # Verify device is detached
        assert not vm.is_device_attached(device.pci_id)
        
    except VMError as e:
        if "hot-plug not supported" in str(e):
            pytest.skip("Device hot-plug not supported")
        raise

def test_iommu_group_isolation(passthrough_manager):
    """Test IOMMU group isolation checks."""
    devices = passthrough_manager.list_devices()
    if not devices:
        pytest.skip("No devices available for testing")
    
    device = devices[0]
    group_devices = passthrough_manager.get_iommu_group_devices(device.pci_id)
    
    assert isinstance(group_devices, list)
    assert device.pci_id in [d.pci_id for d in group_devices]

def test_vfio_binding(passthrough_manager):
    """Test VFIO driver binding operations."""
    devices = passthrough_manager.list_devices()
    if not devices:
        pytest.skip("No devices available for testing")
    
    try:
        device = devices[0]
        
        # Try to bind to VFIO
        passthrough_manager.bind_to_vfio(device.pci_id)
        assert passthrough_manager.is_bound_to_vfio(device.pci_id)
        
        # Try to unbind
        passthrough_manager.unbind_from_vfio(device.pci_id)
        assert not passthrough_manager.is_bound_to_vfio(device.pci_id)
        
    except Exception as e:
        if "VFIO not available" in str(e):
            pytest.skip("VFIO support not available")
        raise

def test_error_handling(test_image, vm, passthrough_manager):
    """Test error handling for invalid operations."""
    # Test invalid PCI ID
    with pytest.raises(VMError):
        vm.create_from_image(
            image_path=test_image,
            memory="4G",
            cpus=2,
            passthrough_devices=[PCIDevice("invalid_id", "Invalid Device")]
        )
    
    # Test non-existent device
    with pytest.raises(ValueError):
        passthrough_manager.get_device_info("0000:ff:00.0")
    
    # Test invalid IOMMU group
    with pytest.raises(ValueError):
        passthrough_manager.get_iommu_group_devices("invalid_id")
