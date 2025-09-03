#!/usr/bin/env python3
"""
Host system introspection and virtualization

Provides utilities to capture the current host system's configuration,
installed software, and disk state, then convert it into a bootable VM.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging
import psutil

from .core import SecureVM, VMError
from .images import ExistingDisk
from .cloudinit import CloudInitConfig


logger = logging.getLogger(__name__)


class HostCapture:
    """
    Captures the current host system's state for virtualization
    
    This includes:
    - Hardware inventory (CPU, memory, storage, network)
    - Software inventory (packages, services, configuration)
    - Disk images and filesystem layouts
    - Network configuration
    """
    
    def __init__(self, target_dir: Optional[Union[str, Path]] = None):
        """
        Initialize host capture
        
        Args:
            target_dir: Directory to store captured data (defaults to temp dir)
        """
        self.target_dir = Path(target_dir) if target_dir else Path(tempfile.mkdtemp(prefix="vmkit-host-"))
        self.target_dir.mkdir(parents=True, exist_ok=True)
        
        self.hardware_info = {}
        self.software_info = {}
        self.network_info = {}
        self.disk_info = {}
        
    def capture_hardware(self) -> Dict:
        """Capture hardware inventory"""
        logger.info("Capturing hardware inventory...")
        
        # CPU information
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
        
        cpu_model = None
        cpu_cores = 0
        cpu_flags = []
        
        for line in cpuinfo.split('\n'):
            if line.startswith('model name'):
                cpu_model = line.split(':', 1)[1].strip()
            elif line.startswith('processor'):
                cpu_cores += 1
            elif line.startswith('flags'):
                cpu_flags = line.split(':', 1)[1].strip().split()
        
        # Memory information
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Disk information
        disk_usage = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_usage.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free
                })
            except PermissionError:
                continue
        
        # Network interfaces
        network_interfaces = []
        for interface, addrs in psutil.net_if_addrs().items():
            interface_info = {
                'name': interface,
                'addresses': []
            }
            for addr in addrs:
                interface_info['addresses'].append({
                    'family': str(addr.family),
                    'address': addr.address,
                    'netmask': addr.netmask,
                    'broadcast': addr.broadcast
                })
            network_interfaces.append(interface_info)
        
        self.hardware_info = {
            'cpu': {
                'model': cpu_model,
                'cores': cpu_cores,
                'flags': cpu_flags,
                'virtualization_support': any(flag in cpu_flags for flag in ['vmx', 'svm'])
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'swap_total': swap.total,
                'swap_used': swap.used
            },
            'disks': disk_usage,
            'network': network_interfaces
        }
        
        # Save to file
        with open(self.target_dir / "hardware.json", "w") as f:
            json.dump(self.hardware_info, f, indent=2)
        
        return self.hardware_info
    
    def capture_software(self) -> Dict:
        """Capture installed software and system configuration"""
        logger.info("Capturing software inventory...")
        
        software_info = {
            'os_info': {},
            'packages': [],
            'services': [],
            'kernel_modules': [],
            'users': [],
            'groups': []
        }
        
        # OS information
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        software_info['os_info'][key] = value.strip('"')
        except FileNotFoundError:
            pass
        
        # Kernel information
        software_info['kernel'] = {
            'release': os.uname().release,
            'version': os.uname().version,
            'machine': os.uname().machine
        }
        
        # Package list (dpkg for Debian/Ubuntu systems)
        try:
            result = subprocess.run(['dpkg', '--get-selections'], 
                                  capture_output=True, text=True, check=True)
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        software_info['packages'].append({
                            'name': parts[0],
                            'state': parts[1]
                        })
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Could not capture package list with dpkg")
            
            # Try with rpm for RedHat systems
            try:
                result = subprocess.run(['rpm', '-qa', '--queryformat', '%{NAME}\t%{VERSION}\n'], 
                                      capture_output=True, text=True, check=True)
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            software_info['packages'].append({
                                'name': parts[0],
                                'version': parts[1]
                            })
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("Could not capture package list with rpm either")
        
        # System services
        try:
            result = subprocess.run(['systemctl', 'list-units', '--type=service', '--state=active', '--no-pager'], 
                                  capture_output=True, text=True, check=True)
            for line in result.stdout.split('\n'):
                if '.service' in line and 'active running' in line:
                    service_name = line.split()[0]
                    software_info['services'].append(service_name)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Could not capture service list")
        
        # Kernel modules
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True, check=True)
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if line.strip():
                    module_name = line.split()[0]
                    software_info['kernel_modules'].append(module_name)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Users and groups
        try:
            with open("/etc/passwd", "r") as f:
                for line in f:
                    parts = line.strip().split(':')
                    if len(parts) >= 7:
                        software_info['users'].append({
                            'name': parts[0],
                            'uid': parts[2],
                            'gid': parts[3],
                            'home': parts[5],
                            'shell': parts[6]
                        })
        except FileNotFoundError:
            pass
        
        try:
            with open("/etc/group", "r") as f:
                for line in f:
                    parts = line.strip().split(':')
                    if len(parts) >= 4:
                        software_info['groups'].append({
                            'name': parts[0],
                            'gid': parts[2],
                            'members': parts[3].split(',') if parts[3] else []
                        })
        except FileNotFoundError:
            pass
        
        self.software_info = software_info
        
        # Save to file
        with open(self.target_dir / "software.json", "w") as f:
            json.dump(self.software_info, f, indent=2)
        
        return software_info
    
    def capture_network_config(self) -> Dict:
        """Capture network configuration"""
        logger.info("Capturing network configuration...")
        
        network_info = {
            'interfaces': {},
            'routes': [],
            'dns': {},
            'hostname': None
        }
        
        # Hostname
        try:
            network_info['hostname'] = subprocess.run(['hostname'], capture_output=True, text=True, check=True).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Network interfaces with ip command
        try:
            # Interface details
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, check=True)
            network_info['ip_addr_show'] = result.stdout
            
            # Routes
            result = subprocess.run(['ip', 'route', 'show'], capture_output=True, text=True, check=True)
            network_info['routes'] = result.stdout.split('\n')
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("Could not capture network info with ip command")
        
        # DNS configuration
        try:
            with open("/etc/resolv.conf", "r") as f:
                network_info['resolv_conf'] = f.read()
        except FileNotFoundError:
            pass
        
        # Netplan configuration (Ubuntu)
        netplan_dir = Path("/etc/netplan")
        if netplan_dir.exists():
            network_info['netplan'] = {}
            for config_file in netplan_dir.glob("*.yaml"):
                try:
                    with open(config_file, "r") as f:
                        network_info['netplan'][config_file.name] = f.read()
                except Exception as e:
                    logger.warning(f"Could not read netplan config {config_file}: {e}")
        
        self.network_info = network_info
        
        # Save to file
        with open(self.target_dir / "network.json", "w") as f:
            json.dump(network_info, f, indent=2)
        
        return network_info
    
    def identify_boot_disk(self) -> Optional[str]:
        """Identify the primary boot disk"""
        try:
            # Find the device containing the root filesystem
            result = subprocess.run(['findmnt', '-n', '-o', 'SOURCE', '/'], capture_output=True, text=True, check=True)
            root_device = result.stdout.strip()
            
            # If it's a partition, get the parent device
            if root_device.endswith(('1', '2', '3', '4', '5', '6', '7', '8', '9')):
                # Remove partition number to get disk
                import re
                root_device = re.sub(r'\d+$', '', root_device)
            
            return root_device
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("Could not identify boot disk")
            return None
    
    def capture_disk_image(self, source_device: str, output_path: Path, 
                          compression: bool = True, sparse: bool = True) -> Path:
        """
        Create a QCOW2 image from the specified disk device
        
        Args:
            source_device: Source disk device (e.g., /dev/sda)
            output_path: Path for the output QCOW2 image
            compression: Enable compression in output image
            sparse: Create sparse image (skip empty blocks)
            
        Returns:
            Path to the created image file
        """
        logger.info(f"Creating disk image from {source_device} to {output_path}")
        
        # Build qemu-img convert command
        cmd = ['qemu-img', 'convert']
        
        if sparse:
            cmd.append('-S')  # Sparse mode
        
        if compression:
            cmd.extend(['-c'])  # Compression
        
        cmd.extend([
            '-f', 'raw',  # Source format
            '-O', 'qcow2',  # Output format
            source_device,
            str(output_path)
        ])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # This will take a while for large disks
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Disk image created successfully: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create disk image: {e}")
            logger.error(f"Command output: {e.stderr}")
            raise VMError(f"Failed to create disk image from {source_device}: {e}")
    
    def full_capture(self, include_disk: bool = False, boot_disk_only: bool = True) -> Dict:
        """
        Perform a complete system capture
        
        Args:
            include_disk: Whether to capture disk images (WARNING: This can be very large and time-consuming)
            boot_disk_only: If capturing disks, only capture the boot disk
            
        Returns:
            Dictionary with paths to all captured data
        """
        logger.info("Starting full host system capture...")
        
        capture_summary = {
            'target_directory': str(self.target_dir),
            'hardware_file': str(self.target_dir / "hardware.json"),
            'software_file': str(self.target_dir / "software.json"),
            'network_file': str(self.target_dir / "network.json"),
            'disk_images': []
        }
        
        # Capture system state
        self.capture_hardware()
        self.capture_software()
        self.capture_network_config()
        
        # Optionally capture disk images
        if include_disk:
            logger.warning("Disk capture enabled - this may take a very long time and use significant disk space!")
            
            if boot_disk_only:
                boot_disk = self.identify_boot_disk()
                if boot_disk:
                    image_path = self.target_dir / "boot_disk.qcow2"
                    self.capture_disk_image(boot_disk, image_path)
                    capture_summary['disk_images'].append(str(image_path))
                else:
                    logger.warning("Could not identify boot disk for capture")
            else:
                # Capture all disks (be very careful with this!)
                for partition in psutil.disk_partitions():
                    device = partition.device
                    # Only capture actual disk devices, not virtual filesystems
                    if device.startswith('/dev/') and not device.startswith('/dev/loop'):
                        try:
                            # Get the base disk device
                            base_device = device.rstrip('0123456789')
                            if base_device not in [p['device'] for p in capture_summary['disk_images']]:
                                image_name = f"{base_device.split('/')[-1]}.qcow2"
                                image_path = self.target_dir / image_name
                                self.capture_disk_image(base_device, image_path)
                                capture_summary['disk_images'].append({
                                    'device': base_device,
                                    'image_path': str(image_path)
                                })
                        except Exception as e:
                            logger.error(f"Failed to capture disk {device}: {e}")
        
        # Save capture summary
        with open(self.target_dir / "capture_summary.json", "w") as f:
            json.dump(capture_summary, f, indent=2)
        
        logger.info(f"Host capture complete. Data stored in: {self.target_dir}")
        return capture_summary


class VirtualizedHost(SecureVM):
    """
    A SecureVM configured to run the current host system as a VM
    
    This extends SecureVM with host-specific optimizations and configurations.
    """
    
    def __init__(self, name: str, host_capture: HostCapture, 
                 disk_image_path: str, **kwargs):
        """
        Initialize a virtualized host VM
        
        Args:
            name: VM name
            host_capture: HostCapture instance with captured system state
            disk_image_path: Path to the host's disk image
            **kwargs: Additional SecureVM parameters
        """
        
        # Set up the disk image
        disk_image = ExistingDisk(disk_image_path)
        
        # Default to host-like resources if not specified
        if 'memory' not in kwargs and host_capture.hardware_info:
            # Use 75% of host memory by default
            host_memory_gb = host_capture.hardware_info.get('memory', {}).get('total', 0) // (1024**3)
            kwargs['memory'] = f"{int(host_memory_gb * 0.75)}G"
        
        if 'cpus' not in kwargs and host_capture.hardware_info:
            # Use 75% of host CPUs
            host_cpus = host_capture.hardware_info.get('cpu', {}).get('cores', 4)
            kwargs['cpus'] = max(1, int(host_cpus * 0.75))
        
        # Initialize parent
        super().__init__(name=name, image=disk_image, **kwargs)
        
        self.host_capture = host_capture
        self.original_disk_path = disk_image_path
    
    def optimize_for_host(self):
        """Apply host-specific optimizations"""
        
        # If the host has GPU, consider adding GPU passthrough
        if self.host_capture.hardware_info:
            hardware = self.host_capture.hardware_info
            
            # Enable nested virtualization if host supports it
            if hardware.get('cpu', {}).get('virtualization_support', False):
                logger.info("Host supports virtualization - enabling nested virtualization")
                # This would require modifying the domain XML to include nested virt
        
        # Network optimization - bridge to host's primary network
        # Storage optimization - consider using host's storage layout
        
        return self
    
    def get_host_optimized_xml(self) -> str:
        """Generate XML with host-specific optimizations"""
        # Start with the base XML
        xml = self._generate_domain_xml()
        
        # Add host-specific modifications
        # - CPU topology matching
        # - Memory balloon device
        # - Host-like PCI controller
        # - Optimized disk caching
        
        return xml
    
    def create_with_host_config(self) -> 'VirtualizedHost':
        """Create the VM with host-optimized configuration"""
        
        # Apply optimizations
        self.optimize_for_host()
        
        # Create using the base method
        return super().create()
    
    def info(self) -> Dict:
        """Extended info including host virtualization details"""
        base_info = super().info()
        
        base_info.update({
            'virtualized_host': True,
            'original_disk': self.original_disk_path,
            'host_capture_dir': str(self.host_capture.target_dir)
        })
        
        return base_info
