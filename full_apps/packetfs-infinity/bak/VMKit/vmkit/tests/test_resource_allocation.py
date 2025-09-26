#!/usr/bin/env python3
"""
Test suite for VMKit resource allocation features.
Tests both percentage-based and explicit resource allocation.
"""

import pytest
import os
import time
from pathlib import Path
from vmkit.core import SecureVM, VMError
from vmkit.resources import ResourceAllocator, AllocationError

# Test VM configuration
TEST_VM_NAME = "vmkit-test-resources"
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
def resource_allocator():
    """Get a ResourceAllocator instance."""
    return ResourceAllocator()

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

def test_cpu_percentage_allocation(test_image, vm, resource_allocator):
    """Test percentage-based CPU allocation."""
    # Try different CPU percentages
    for cpu_percent in [25, 50, 75]:
        # Get allocation
        cpu_allocation = resource_allocator.allocate_cpus(cpu_percent)
        
        # Create VM with allocated CPUs
        vm.create_from_image(
            image_path=test_image,
            cpus=cpu_allocation['allocated_cores'],
            memory="2G"  # Fixed memory for this test
        )
        
        # Verify allocation
        info = vm.info()
        assert info["vcpus"] == cpu_allocation['allocated_cores']
        
        # Cleanup for next iteration
        vm.destroy()
        time.sleep(1)

def test_memory_percentage_allocation(test_image, vm, resource_allocator):
    """Test percentage-based memory allocation."""
    # Try different memory percentages
    for memory_percent in [20, 40, 60]:
        # Get allocation
        memory_allocation = resource_allocator.allocate_memory(memory_percent)
        memory_str = f"{memory_allocation['allocated_mb']}M"
        
        # Create VM with allocated memory
        vm.create_from_image(
            image_path=test_image,
            memory=memory_str,
            cpus=2  # Fixed CPUs for this test
        )
        
        # Verify allocation
        info = vm.info()
        assert abs(info["memory_mb"] - memory_allocation['allocated_mb']) <= 1
        
        # Cleanup for next iteration
        vm.destroy()
        time.sleep(1)

def test_storage_allocation(test_image, vm, resource_allocator):
    """Test storage allocation."""
    # Try different storage sizes
    for size_gb in [10, 20, 50]:
        size_bytes = size_gb * 1024**3
        
        # Allocate storage
        storage_allocation = resource_allocator.allocate_storage(size_bytes)
        
        assert storage_allocation['volume_path'].exists()
        assert storage_allocation['size_gb'] == size_gb
        
        # Cleanup
        if storage_allocation['volume_path'].exists():
            os.remove(storage_allocation['volume_path'])

def test_gpu_allocation(resource_allocator):
    """Test GPU allocation if available."""
    try:
        # Try to allocate all GPU resources
        gpu_devices = resource_allocator.allocate_gpu(100)
        if gpu_devices:
            assert len(gpu_devices) > 0
            for device in gpu_devices:
                assert device.pci_id is not None
                assert device.device_name is not None
    except AllocationError:
        pytest.skip("No GPU available for testing")

def test_network_allocation(resource_allocator):
    """Test network bandwidth allocation."""
    # Try different bandwidth percentages
    for net_percent in [25, 50, 75]:
        net_allocation = resource_allocator.allocate_network(net_percent)
        assert net_allocation['bandwidth_mbps'] > 0
        # Could add more specific checks based on known network capabilities

def test_explicit_cpu_allocation(test_image, vm, resource_allocator):
    """Test explicit CPU core allocation."""
    try:
        # Try to allocate specific CPU cores
        cpu_list = "0-1"  # Adjust based on your system
        cpu_allocation = resource_allocator.allocate_cpu_from(cpu_list)
        
        vm.create_from_image(
            image_path=test_image,
            cpus=cpu_allocation['allocated_cores'],
            memory="2G"
        )
        
        # Verify allocation
        info = vm.info()
        assert info["vcpus"] == cpu_allocation['allocated_cores']
        
    except AllocationError as e:
        pytest.skip(f"CPU allocation not available: {e}")

def test_explicit_memory_allocation(test_image, vm, resource_allocator):
    """Test explicit memory allocation from NUMA nodes."""
    try:
        # Try to allocate from NUMA node 0
        memory_allocation = resource_allocator.allocate_memory_from(0, 2 * 1024**3)  # 2GB
        
        vm.create_from_image(
            image_path=test_image,
            memory=f"{memory_allocation['allocated_mb']}M",
            cpus=2
        )
        
        # Verify allocation
        info = vm.info()
        assert abs(info["memory_mb"] - memory_allocation['allocated_mb']) <= 1
        
    except AllocationError as e:
        pytest.skip(f"NUMA memory allocation not available: {e}")

def test_combined_resource_allocation(test_image, vm, resource_allocator):
    """Test allocating multiple resources together."""
    try:
        # Allocate CPU, memory, and network
        cpu_allocation = resource_allocator.allocate_cpus(50)
        memory_allocation = resource_allocator.allocate_memory(50)
        net_allocation = resource_allocator.allocate_network(50)
        
        vm.create_from_image(
            image_path=test_image,
            cpus=cpu_allocation['allocated_cores'],
            memory=f"{memory_allocation['allocated_mb']}M"
        )
        
        # Verify allocations
        info = vm.info()
        assert info["vcpus"] == cpu_allocation['allocated_cores']
        assert abs(info["memory_mb"] - memory_allocation['allocated_mb']) <= 1
        assert net_allocation['bandwidth_mbps'] > 0
        
    except AllocationError as e:
        pytest.skip(f"Combined resource allocation not available: {e}")

def test_allocation_limits(resource_allocator):
    """Test resource allocation limits and error handling."""
    # Test over-allocation
    with pytest.raises(AllocationError):
        resource_allocator.allocate_cpus(150)  # Over 100%
    
    with pytest.raises(AllocationError):
        resource_allocator.allocate_memory(120)  # Over 100%
    
    # Test invalid values
    with pytest.raises(ValueError):
        resource_allocator.allocate_cpus(0)  # Zero percent
    
    with pytest.raises(ValueError):
        resource_allocator.allocate_memory(-10)  # Negative percent

def test_allocation_release(resource_allocator):
    """Test releasing allocated resources."""
    # Allocate some resources
    cpu_allocation = resource_allocator.allocate_cpus(25)
    memory_allocation = resource_allocator.allocate_memory(25)
    
    # Release resources
    assert resource_allocator.release_cpus(cpu_allocation['allocated_cores'])
    assert resource_allocator.release_memory(memory_allocation['allocated_mb'])

def test_concurrent_allocations(test_image, resource_allocator):
    """Test multiple concurrent resource allocations."""
    # Create multiple VMs with resources
    vms = []
    try:
        for i in range(3):  # Try to create 3 VMs
            try:
                # Allocate resources for each VM
                cpu_alloc = resource_allocator.allocate_cpus(25)
                mem_alloc = resource_allocator.allocate_memory(25)
                
                vm = SecureVM(f"{TEST_VM_NAME}-{i}")
                vm.create_from_image(
                    image_path=test_image,
                    cpus=cpu_alloc['allocated_cores'],
                    memory=f"{mem_alloc['allocated_mb']}M"
                )
                vms.append(vm)
                
            except (VMError, AllocationError) as e:
                print(f"Failed to allocate for VM {i}: {e}")
                break
        
        # Verify we can create multiple VMs
        assert len(vms) > 0, "Should be able to create at least one VM"
        
    finally:
        # Cleanup
        for vm in vms:
            try:
                if vm.is_active():
                    vm.stop(force=True)
                if vm.is_defined():
                    vm.destroy()
            except Exception:
                pass
