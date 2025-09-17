#!/usr/bin/env python3
"""
Advanced network management for VMs

Provides intuitive network management including bridge networks,
NAT networks, port forwarding, and network isolation.
"""

import json
import libvirt
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging

from .core import VMError

logger = logging.getLogger(__name__)


class NetworkManager:
    """
    Manages libvirt networks with simplified, intuitive interface
    """
    
    def __init__(self):
        self._conn = None
    
    @property
    def conn(self) -> libvirt.virConnect:
        """Lazy libvirt connection"""
        if self._conn is None:
            try:
                self._conn = libvirt.open("qemu:///system")
            except libvirt.libvirtError as e:
                raise VMError(f"Failed to connect to libvirt: {e}")
        return self._conn
    
    def list_networks(self, include_inactive: bool = True) -> List[Dict]:
        """List all networks"""
        try:
            if include_inactive:
                networks = self.conn.listAllNetworks()
            else:
                networks = self.conn.listAllNetworks(libvirt.VIR_CONNECT_LIST_NETWORKS_ACTIVE)
            
            network_list = []
            for net in networks:
                try:
                    info = self._get_network_info(net)
                    network_list.append(info)
                except Exception as e:
                    logger.error(f"Error getting info for network {net.name()}: {e}")
            
            return network_list
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to list networks: {e}")
    
    def _get_network_info(self, network: libvirt.virNetwork) -> Dict:
        """Get detailed network information"""
        try:
            xml_desc = network.XMLDesc(0)
            root = ET.fromstring(xml_desc)
            
            # Basic info
            info = {
                'name': network.name(),
                'uuid': network.UUIDString(),
                'active': network.isActive(),
                'persistent': network.isPersistent(),
                'autostart': network.autostart() if network.isPersistent() else False
            }
            
            # Network details from XML
            forward_elem = root.find('forward')
            if forward_elem is not None:
                info['mode'] = forward_elem.get('mode', 'nat')
            else:
                info['mode'] = 'isolated'
            
            # IP configuration
            ip_elem = root.find('ip')
            if ip_elem is not None:
                info['address'] = ip_elem.get('address')
                info['netmask'] = ip_elem.get('netmask')
                info['prefix'] = ip_elem.get('prefix')
                
                # DHCP range
                dhcp_elem = ip_elem.find('dhcp')
                if dhcp_elem is not None:
                    range_elem = dhcp_elem.find('range')
                    if range_elem is not None:
                        info['dhcp_start'] = range_elem.get('start')
                        info['dhcp_end'] = range_elem.get('end')
            
            # Bridge interface
            bridge_elem = root.find('bridge')
            if bridge_elem is not None:
                info['bridge'] = bridge_elem.get('name')
            
            return info
            
        except Exception as e:
            logger.error(f"Error parsing network XML: {e}")
            return {
                'name': network.name(),
                'active': network.isActive(),
                'error': str(e)
            }
    
    def get_network(self, name: str) -> libvirt.virNetwork:
        """Get a network by name"""
        try:
            return self.conn.networkLookupByName(name)
        except libvirt.libvirtError as e:
            raise VMError(f"Network '{name}' not found: {e}")
    
    def create_nat_network(self, name: str, subnet: str = "192.168.100.0/24", 
                          dhcp_start: Optional[str] = None, dhcp_end: Optional[str] = None,
                          autostart: bool = True) -> Dict:
        """
        Create a NAT network
        
        Args:
            name: Network name
            subnet: Network subnet in CIDR notation
            dhcp_start: DHCP range start (auto-calculated if not provided)
            dhcp_end: DHCP range end (auto-calculated if not provided)
            autostart: Enable autostart
        """
        if self._network_exists(name):
            raise VMError(f"Network '{name}' already exists")
        
        # Parse subnet
        import ipaddress
        network = ipaddress.IPv4Network(subnet, strict=False)
        gateway = str(network.network_address + 1)
        netmask = str(network.netmask)
        
        # Auto-calculate DHCP range if not provided
        if not dhcp_start:
            dhcp_start = str(network.network_address + 10)
        if not dhcp_end:
            dhcp_end = str(network.network_address + 100)
        
        xml = f"""
        <network>
          <name>{name}</name>
          <forward mode='nat'>
            <nat>
              <port start='1024' end='65535'/>
            </nat>
          </forward>
          <bridge name='{name}' stp='on' delay='0'/>
          <ip address='{gateway}' netmask='{netmask}'>
            <dhcp>
              <range start='{dhcp_start}' end='{dhcp_end}'/>
            </dhcp>
          </ip>
        </network>
        """.strip()
        
        try:
            # Define the network
            net = self.conn.networkDefineXML(xml)
            
            # Start and set autostart
            net.create()
            if autostart:
                net.setAutostart(1)
            
            logger.info(f"Created NAT network '{name}' with subnet {subnet}")
            return self._get_network_info(net)
            
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to create NAT network: {e}")
    
    def create_bridge_network(self, name: str, bridge_interface: str,
                            autostart: bool = True) -> Dict:
        """
        Create a bridged network
        
        Args:
            name: Network name
            bridge_interface: Host bridge interface to use (e.g., 'br0')
            autostart: Enable autostart
        """
        if self._network_exists(name):
            raise VMError(f"Network '{name}' already exists")
        
        xml = f"""
        <network>
          <name>{name}</name>
          <forward mode='bridge'/>
          <bridge name='{bridge_interface}'/>
        </network>
        """.strip()
        
        try:
            # Define the network
            net = self.conn.networkDefineXML(xml)
            
            # Start and set autostart
            net.create()
            if autostart:
                net.setAutostart(1)
            
            logger.info(f"Created bridge network '{name}' using {bridge_interface}")
            return self._get_network_info(net)
            
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to create bridge network: {e}")
    
    def create_isolated_network(self, name: str, subnet: str = "192.168.200.0/24",
                              dhcp_enabled: bool = True, autostart: bool = True) -> Dict:
        """
        Create an isolated network (no internet access)
        
        Args:
            name: Network name
            subnet: Network subnet in CIDR notation
            dhcp_enabled: Whether to enable DHCP
            autostart: Enable autostart
        """
        if self._network_exists(name):
            raise VMError(f"Network '{name}' already exists")
        
        # Parse subnet
        import ipaddress
        network = ipaddress.IPv4Network(subnet, strict=False)
        gateway = str(network.network_address + 1)
        netmask = str(network.netmask)
        
        # Build XML
        dhcp_xml = ""
        if dhcp_enabled:
            dhcp_start = str(network.network_address + 10)
            dhcp_end = str(network.network_address + 100)
            dhcp_xml = f"""
            <dhcp>
              <range start='{dhcp_start}' end='{dhcp_end}'/>
            </dhcp>
            """
        
        xml = f"""
        <network>
          <name>{name}</name>
          <bridge name='{name}' stp='on' delay='0'/>
          <ip address='{gateway}' netmask='{netmask}'>
            {dhcp_xml.strip()}
          </ip>
        </network>
        """.strip()
        
        try:
            # Define the network
            net = self.conn.networkDefineXML(xml)
            
            # Start and set autostart
            net.create()
            if autostart:
                net.setAutostart(1)
            
            logger.info(f"Created isolated network '{name}' with subnet {subnet}")
            return self._get_network_info(net)
            
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to create isolated network: {e}")
    
    def delete_network(self, name: str, force: bool = False) -> None:
        """
        Delete a network
        
        Args:
            name: Network name
            force: Force deletion even if VMs are connected
        """
        try:
            net = self.get_network(name)
            
            # Check if network is in use (unless forcing)
            if not force:
                connected_vms = self.get_connected_vms(name)
                if connected_vms:
                    raise VMError(f"Network '{name}' is in use by VMs: {connected_vms}. "
                                f"Use force=True to delete anyway.")
            
            # Stop if active
            if net.isActive():
                net.destroy()
            
            # Undefine if persistent
            if net.isPersistent():
                net.undefine()
            
            logger.info(f"Deleted network '{name}'")
            
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to delete network: {e}")
    
    def start_network(self, name: str) -> None:
        """Start a network"""
        try:
            net = self.get_network(name)
            if not net.isActive():
                net.create()
                logger.info(f"Started network '{name}'")
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to start network: {e}")
    
    def stop_network(self, name: str) -> None:
        """Stop a network"""
        try:
            net = self.get_network(name)
            if net.isActive():
                net.destroy()
                logger.info(f"Stopped network '{name}'")
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to stop network: {e}")
    
    def set_autostart(self, name: str, enabled: bool) -> None:
        """Set network autostart"""
        try:
            net = self.get_network(name)
            if net.isPersistent():
                net.setAutostart(1 if enabled else 0)
                logger.info(f"Set autostart for network '{name}' to {enabled}")
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to set autostart: {e}")
    
    def get_connected_vms(self, network_name: str) -> List[str]:
        """Get VMs connected to a network"""
        connected_vms = []
        
        try:
            domains = self.conn.listAllDomains()
            for domain in domains:
                try:
                    xml_desc = domain.XMLDesc(0)
                    if f"<source network='{network_name}'/>" in xml_desc:
                        connected_vms.append(domain.name())
                except Exception as e:
                    logger.debug(f"Error checking VM {domain.name()}: {e}")
        except libvirt.libvirtError as e:
            logger.error(f"Failed to list VMs: {e}")
        
        return connected_vms
    
    def get_dhcp_leases(self, network_name: str) -> List[Dict]:
        """Get DHCP leases for a network"""
        try:
            net = self.get_network(network_name)
            if not net.isActive():
                return []
            
            leases = net.DHCPLeases()
            lease_list = []
            
            for lease in leases:
                lease_list.append({
                    'mac': lease.get('mac'),
                    'ip': lease.get('ipaddr'),
                    'hostname': lease.get('hostname', ''),
                    'expiry': lease.get('expirytime', 0)
                })
            
            return lease_list
            
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to get DHCP leases: {e}")
    
    def setup_port_forward(self, network_name: str, host_port: int, 
                          guest_ip: str, guest_port: int, protocol: str = 'tcp') -> None:
        """
        Set up port forwarding for a NAT network
        
        This adds iptables rules to forward traffic from host to guest.
        Note: This is a basic implementation and may need adjustment based on firewall setup.
        """
        try:
            net = self.get_network(network_name)
            net_info = self._get_network_info(net)
            
            if net_info.get('mode') != 'nat':
                raise VMError(f"Port forwarding only supported for NAT networks")
            
            bridge_name = net_info.get('bridge')
            if not bridge_name:
                raise VMError(f"Could not determine bridge name for network")
            
            # Add iptables rules
            # DNAT rule for incoming connections
            dnat_cmd = [
                'iptables', '-t', 'nat', '-A', 'OUTPUT',
                '-p', protocol, '--dport', str(host_port),
                '-j', 'DNAT', '--to-destination', f"{guest_ip}:{guest_port}"
            ]
            
            # Forward rule
            forward_cmd = [
                'iptables', '-A', 'FORWARD',
                '-p', protocol, '-d', guest_ip, '--dport', str(guest_port),
                '-j', 'ACCEPT'
            ]
            
            # Execute rules (requires root permissions)
            try:
                subprocess.run(dnat_cmd, check=True, capture_output=True)
                subprocess.run(forward_cmd, check=True, capture_output=True)
                
                logger.info(f"Set up port forward: {host_port} -> {guest_ip}:{guest_port}")
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to set up iptables rules: {e}")
                raise VMError(f"Port forwarding setup failed. May need root permissions.")
                
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to set up port forwarding: {e}")
    
    def remove_port_forward(self, network_name: str, host_port: int,
                           guest_ip: str, guest_port: int, protocol: str = 'tcp') -> None:
        """Remove port forwarding rules"""
        try:
            # Remove iptables rules (change -A to -D)
            dnat_cmd = [
                'iptables', '-t', 'nat', '-D', 'OUTPUT',
                '-p', protocol, '--dport', str(host_port),
                '-j', 'DNAT', '--to-destination', f"{guest_ip}:{guest_port}"
            ]
            
            forward_cmd = [
                'iptables', '-D', 'FORWARD',
                '-p', protocol, '-d', guest_ip, '--dport', str(guest_port),
                '-j', 'ACCEPT'
            ]
            
            try:
                subprocess.run(dnat_cmd, check=True, capture_output=True)
                subprocess.run(forward_cmd, check=True, capture_output=True)
                
                logger.info(f"Removed port forward: {host_port} -> {guest_ip}:{guest_port}")
                
            except subprocess.CalledProcessError as e:
                logger.warning(f"Some iptables rules may not have been removed: {e}")
                
        except Exception as e:
            logger.error(f"Error removing port forwarding: {e}")
    
    def get_network_info(self, name: str) -> Dict:
        """Get detailed network information"""
        net = self.get_network(name)
        return self._get_network_info(net)
    
    def _network_exists(self, name: str) -> bool:
        """Check if a network exists"""
        try:
            self.conn.networkLookupByName(name)
            return True
        except libvirt.libvirtError:
            return False
    
    def get_default_network(self) -> Dict:
        """Get or create the default network"""
        try:
            net = self.get_network("default")
            return self._get_network_info(net)
        except VMError:
            # Default network doesn't exist, check if we can create it
            logger.info("Default network not found - this is unusual for libvirt")
            return {
                'name': 'default',
                'status': 'missing',
                'message': 'Default network not found. You may need to create it manually.'
            }
    
    def create_host_bridge(self, bridge_name: str, interface: str) -> None:
        """
        Create a bridge interface on the host
        
        This is a helper to create Linux bridge interfaces that can be used
        by libvirt bridge networks.
        """
        try:
            # Check if bridge already exists
            result = subprocess.run(['ip', 'link', 'show', bridge_name], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Bridge {bridge_name} already exists")
                return
            
            # Create bridge
            subprocess.run(['ip', 'link', 'add', bridge_name, 'type', 'bridge'], 
                          check=True, capture_output=True)
            
            # Add interface to bridge if specified
            if interface:
                subprocess.run(['ip', 'link', 'set', interface, 'master', bridge_name], 
                              check=True, capture_output=True)
            
            # Bring bridge up
            subprocess.run(['ip', 'link', 'set', bridge_name, 'up'], 
                          check=True, capture_output=True)
            
            logger.info(f"Created bridge {bridge_name}")
            
        except subprocess.CalledProcessError as e:
            raise VMError(f"Failed to create bridge: {e}")
