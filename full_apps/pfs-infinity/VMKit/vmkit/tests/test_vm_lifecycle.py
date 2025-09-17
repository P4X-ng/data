#!/usr/bin/env python3
"""
Test suite for basic VM lifecycle operations in VMKit.
"""

import pytest
import os
import time
from pathlib import Path
from vmkit.core import SecureVM, VMError
from vmkit.images import CloudImage

# Test VM configuration
TEST_VM_NAME = "vmkit-test-basic"
TEST_IMAGE = "/tmp/vmkit-test.qcow2"  # We'll create this in setup
TEST_VM_MEMORY = 2048  # 2GB in MB
TEST_VM_CPUS = 2

@pytest.fixture(scope="module")
def test_image():
    """Create a minimal test image."""
    if not Path(TEST_IMAGE).exists():
        # Create a small empty disk for testing
        os.system(f"qemu-img create -f qcow2 {TEST_IMAGE} 5G")
    yield TEST_IMAGE
    # Cleanup
    if Path(TEST_IMAGE).exists():
        os.remove(TEST_IMAGE)

@pytest.fixture(scope="function")
def vm():
    """Create a test VM and ensure cleanup."""
    try:
        vm = SecureVM(TEST_VM_NAME)
        yield vm
    finally:
        # Ensure VM is cleaned up after each test
        try:
            if vm.is_active():
                vm.stop(force=True)
            if vm.is_defined():
                vm.destroy()
        except Exception:
            pass

def test_vm_creation(test_image, vm):
    """Test creating a new VM."""
    # Set up and create VM
    vm.image = CloudImage(test_image)
    vm.create()
    
    # Verify VM exists
    assert vm.is_defined(), "VM should exist after creation"
    assert not vm.is_active(), "VM should not be running after creation"

    # Check VM info
    info = vm.info()
    assert info["name"] == TEST_VM_NAME
    assert info["memory_mb"] == int(TEST_VM_MEMORY.rstrip("G")) * 1024
    assert info["vcpus"] == TEST_VM_CPUS

def test_vm_start_stop(test_image, vm):
    """Test starting and stopping a VM."""
    # Set up and create VM
    vm.image = CloudImage(test_image)
    vm.create()
    
    # Test start
    vm.start()
    assert vm.is_active(), "VM should be running after start"
    
    # Give VM a moment to stabilize
    time.sleep(2)
    
    # Test graceful stop
    vm.stop(force=False)
    assert not vm.is_active(), "VM should not be running after stop"
    
    # Test force stop
    vm.start()
    assert vm.is_active()
    vm.stop(force=True)
    assert not vm.is_active()

def test_vm_destroy(test_image, vm):
    """Test destroying a VM."""
    # Set up and create VM
    vm.image = CloudImage(test_image)
    vm.create()
    
    # Destroy VM
    vm.destroy()
    assert not vm.is_defined(), "VM should not exist after destroy"

def test_multiple_vm_operations(test_image, vm):
    """Test multiple start/stop cycles."""
    # Set up and create VM
    vm.image = CloudImage(test_image)
    vm.create()
    
    # Multiple start/stop cycles
    for _ in range(3):
        vm.start()
        assert vm.is_active()
        time.sleep(2)
        vm.stop(force=True)
        assert not vm.is_active()
        time.sleep(1)

def test_invalid_operations(test_image, vm):
    """Test handling of invalid operations."""
    # Try operations on non-existent VM
    with pytest.raises(VMError):
        vm.start()
    
    with pytest.raises(VMError):
        vm.stop()
    
    # Set up and create VM
    vm.image = CloudImage(test_image)
    vm.create()
    
    # Try creating again (should fail)
    with pytest.raises(VMError):
        # Set image and create VM
        vm.image = CloudImage(test_image)
        vm.create()
    
    # Try stopping non-running VM
    with pytest.raises(VMError):
        vm.stop()

def test_vm_with_invalid_config(test_image):
    """Test VM creation with invalid configuration."""
    # Test with invalid memory
    with pytest.raises(VMError):
        vm = SecureVM("invalid-vm")
        # Set invalid memory
        vm.memory = "invalid"
        vm.image = CloudImage(test_image)
        vm.create()
    
    # Test with invalid CPU count
    with pytest.raises(ValueError):
        vm = SecureVM("invalid-vm")
        vm.cpus = -1
        vm.image = CloudImage(test_image)
        vm.create()
    
    # Test with non-existent image
    with pytest.raises(VMError):
        vm = SecureVM("invalid-vm")
        vm.image = CloudImage("/nonexistent/image.qcow2")
        vm.create()
