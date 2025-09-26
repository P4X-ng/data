#!/usr/bin/env python3
"""
Test suite for VMKit network management features.
Tests NAT and bridge network creation, configuration, and management.
"""

import pytest
import os
import time
import ipaddress
from pathlib import Path
from vmkit.core import SecureVM, VMError
from vmkit.network import NetworkManager, NetworkError
from vmkit.resources import ResourceAllocator

# Test configuration
TEST_VM_NAME = "vmkit-test-network"
TEST_IMAGE = "/tmp/vmkit-test.qcow2"
TEST_NET_NAME = "vmkit-test-net"
TEST_BRIDGE_NAME = "vmkit-test-br0"

@pytest.fixture(scope="module")
def test_image():
    """Create a minimal test image."""
    if not Path(TEST_IMAGE).exists():
        os.system(f"qemu-img create -f qcow2 {TEST_IMAGE} 5G")
    yield TEST_IMAGE
    if Path(TEST_IMAGE).exists():
        os.remove(TEST_IMAGE)

@pytest.fixture(scope="module")
def network_manager():
    """Get a NetworkManager instance."""
    return NetworkManager()

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

def test_list_networks(network_manager):
    """Test listing available networks."""
    networks = network_manager.list_networks()
    assert isinstance(networks, list)
    
    # Check network properties
    for net in networks:
        assert "name" in net
        assert "mode" in net
        assert isinstance(net.get("active"), bool)
        if "address" in net:
            # Validate IP address format
            ipaddress.ip_network(net["address"])

def test_nat_network_creation(network_manager):
    """Test creating a NAT network."""
    try:
        # Create NAT network
        net_info = network_manager.create_nat_network(
            TEST_NET_NAME,
            subnet="192.168.200.0/24",
            dhcp_start="192.168.200.100",
            dhcp_end="192.168.200.200",
            autostart=True
        )
        
        # Verify network properties
        assert net_info["name"] == TEST_NET_NAME
        assert net_info["mode"] == "nat"
        assert ipaddress.ip_network(net_info["address"])
        assert net_info.get("dhcp_start") == "192.168.200.100"
        assert net_info.get("dhcp_end") == "192.168.200.200"
        
        # Check network is active
        networks = network_manager.list_networks()
        test_net = next((n for n in networks if n["name"] == TEST_NET_NAME), None)
        assert test_net is not None
        assert test_net["active"]
        
    finally:
        # Cleanup
        try:
            network_manager.delete_network(TEST_NET_NAME)
        except Exception:
            pass

def test_bridge_network_creation(network_manager):
    """Test creating a bridge network."""
    # Find a suitable interface for bridging
    try:
        bridges = network_manager.list_bridge_interfaces()
        if not bridges:
            pytest.skip("No bridge interfaces available for testing")
        
        bridge_interface = bridges[0]
        
        # Create bridge network
        net_info = network_manager.create_bridge_network(
            TEST_BRIDGE_NAME,
            bridge_interface,
            autostart=True
        )
        
        # Verify network properties
        assert net_info["name"] == TEST_BRIDGE_NAME
        assert net_info["mode"] == "bridge"
        assert net_info["bridge_interface"] == bridge_interface
        
        # Check network is active
        networks = network_manager.list_networks()
        test_net = next((n for n in networks if n["name"] == TEST_BRIDGE_NAME), None)
        assert test_net is not None
        assert test_net["active"]
        
    finally:
        # Cleanup
        try:
            network_manager.delete_network(TEST_BRIDGE_NAME)
        except Exception:
            pass

def test_network_deletion(network_manager):
    """Test network deletion."""
    # Create a test network
    net_info = network_manager.create_nat_network(
        TEST_NET_NAME,
        subnet="192.168.200.0/24"
    )
    
    # Verify network exists
    networks = network_manager.list_networks()
    assert any(n["name"] == TEST_NET_NAME for n in networks)
    
    # Delete network
    network_manager.delete_network(TEST_NET_NAME)
    
    # Verify network is gone
    networks = network_manager.list_networks()
    assert not any(n["name"] == TEST_NET_NAME for n in networks)

def test_vm_network_attachment(test_image, vm, network_manager):
    """Test attaching a VM to a network."""
    try:
        # Create test network
        net_info = network_manager.create_nat_network(
            TEST_NET_NAME,
            subnet="192.168.200.0/24"
        )
        
        # Create VM with network
        vm.create_from_image(
            image_path=test_image,
            memory="2G",
            cpus=2,
            networks=[{"name": TEST_NET_NAME}]
        )
        
        # Verify network attachment
        vm_networks = vm.get_networks()
        assert any(n["name"] == TEST_NET_NAME for n in vm_networks)
        
        # Start VM and check network is connected
        vm.start()
        assert vm.is_active()
        
        # Give VM time to initialize
        time.sleep(5)
        
        # Verify network is still attached
        vm_networks = vm.get_networks()
        assert any(n["name"] == TEST_NET_NAME and n["connected"] for n in vm_networks)
        
    finally:
        # Cleanup
        try:
            network_manager.delete_network(TEST_NET_NAME)
        except Exception:
            pass

def test_network_bandwidth_control(test_image, vm, network_manager):
    """Test network bandwidth control features."""
    try:
        # Create network with bandwidth limits
        net_info = network_manager.create_nat_network(
            TEST_NET_NAME,
            subnet="192.168.200.0/24",
            bandwidth_inbound="100",  # 100 Mbps
            bandwidth_outbound="100"
        )
        
        # Create VM with network bandwidth limits
        vm.create_from_image(
            image_path=test_image,
            memory="2G",
            cpus=2,
            networks=[{
                "name": TEST_NET_NAME,
                "bandwidth_inbound": "50",  # 50 Mbps
                "bandwidth_outbound": "50"
            }]
        )
        
        # Verify bandwidth settings
        vm_networks = vm.get_networks()
        net = next(n for n in vm_networks if n["name"] == TEST_NET_NAME)
        assert net["bandwidth_inbound"] == "50"
        assert net["bandwidth_outbound"] == "50"
        
    finally:
        # Cleanup
        try:
            network_manager.delete_network(TEST_NET_NAME)
        except Exception:
            pass

def test_multiple_networks(test_image, vm, network_manager):
    """Test VM with multiple networks."""
    networks = []
    try:
        # Create two test networks
        for i in range(2):
            net_name = f"{TEST_NET_NAME}-{i}"
            net_info = network_manager.create_nat_network(
                net_name,
                subnet=f"192.168.{200+i}.0/24"
            )
            networks.append(net_name)
        
        # Create VM with both networks
        vm.create_from_image(
            image_path=test_image,
            memory="2G",
            cpus=2,
            networks=[{"name": name} for name in networks]
        )
        
        # Verify both networks are attached
        vm_networks = vm.get_networks()
        for net_name in networks:
            assert any(n["name"] == net_name for n in vm_networks)
        
        # Start VM and check networks
        vm.start()
        assert vm.is_active()
        
        # Give VM time to initialize
        time.sleep(5)
        
        # Verify both networks are still connected
        vm_networks = vm.get_networks()
        for net_name in networks:
            assert any(n["name"] == net_name and n["connected"] for n in vm_networks)
            
    finally:
        # Cleanup
        for net_name in networks:
            try:
                network_manager.delete_network(net_name)
            except Exception:
                pass

def test_network_error_handling(network_manager):
    """Test error handling for network operations."""
    # Test duplicate network creation
    net_info = network_manager.create_nat_network(
        TEST_NET_NAME,
        subnet="192.168.200.0/24"
    )
    
    with pytest.raises(NetworkError):
        network_manager.create_nat_network(
            TEST_NET_NAME,
            subnet="192.168.201.0/24"
        )
    
    # Test invalid subnet
    with pytest.raises(ValueError):
        network_manager.create_nat_network(
            "invalid-net",
            subnet="invalid-subnet"
        )
    
    # Test deleting non-existent network
    with pytest.raises(NetworkError):
        network_manager.delete_network("non-existent-net")
    
    # Cleanup
    try:
        network_manager.delete_network(TEST_NET_NAME)
    except Exception:
        pass

def test_network_persistence(network_manager):
    """Test network persistence across service restarts."""
    try:
        # Create network with autostart
        net_info = network_manager.create_nat_network(
            TEST_NET_NAME,
            subnet="192.168.200.0/24",
            autostart=True
        )
        
        # Simulate service restart
        network_manager.restart_service()
        
        # Verify network still exists and is active
        networks = network_manager.list_networks()
        test_net = next((n for n in networks if n["name"] == TEST_NET_NAME), None)
        assert test_net is not None
        assert test_net["active"]
        
    finally:
        # Cleanup
        try:
            network_manager.delete_network(TEST_NET_NAME)
        except Exception:
            pass

def test_network_xml_configuration(network_manager):
    """Test network XML configuration features."""
    try:
        # Create network with custom XML settings
        net_info = network_manager.create_nat_network(
            TEST_NET_NAME,
            subnet="192.168.200.0/24",
            xml_customization={
                "forward": {"nat": {"port_mapping": True}},
                "dns": {
                    "forwarders": ["8.8.8.8"],
                    "txt": [{"name": "test", "value": "value"}]
                }
            }
        )
        
        # Get network XML
        xml_config = network_manager.get_network_xml(TEST_NET_NAME)
        
        # Verify custom settings
        assert "8.8.8.8" in xml_config
        assert "port_mapping" in xml_config
        assert "test" in xml_config
        
    finally:
        # Cleanup
        try:
            network_manager.delete_network(TEST_NET_NAME)
        except Exception:
            pass
