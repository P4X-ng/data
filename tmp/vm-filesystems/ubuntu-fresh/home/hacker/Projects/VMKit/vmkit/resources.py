"""
Resource Allocation Engine for VMKit
====================================

Advanced percentage-based resource allocation for CPU, memory, storage, and network.
Supports NUMA topology awareness, CPU pinning, and intelligent resource distribution.
"""

import logging
import os
import subprocess
import json
import psutil
import re
import time
from typing import Dict, List, Set, Optional, Tuple, Any, Union
from pathlib import Path

logger = logging.getLogger(__name__)


class ResourceAllocationError(Exception):
    """Resource allocation specific errors"""
    pass


class ResourceAllocator:
    """
    Intelligent resource allocator for VMs with percentage-based allocation.
    
    Features:
    - NUMA-aware CPU allocation and pinning
    - Memory allocation with hugepage support detection
    - Storage quota management with LVM thin provisioning
    - Network bandwidth allocation with TC traffic control
    """
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize the resource allocator.
        
        Args:
            dry_run: If True, only calculate allocations without making changes
        """
        self.dry_run = dry_run
        self._host_info = None
        self._numa_topology = None
        
        logger.info(f"ResourceAllocator initialized (dry_run={dry_run})")
    
    @property 
    def host_info(self) -> Dict[str, Any]:
        """Cached host information"""
        if self._host_info is None:
            self._host_info = self._gather_host_info()
        return self._host_info
    
    @property
    def numa_topology(self) -> Dict[str, Any]:
        """Cached NUMA topology information"""
        if self._numa_topology is None:
            self._numa_topology = self._detect_numa_topology()
        return self._numa_topology
    
    def _gather_host_info(self) -> Dict[str, Any]:
        """Gather comprehensive host system information"""
        logger.debug("Gathering host system information...")
        
        # CPU information
        cpu_info = {
            'physical_cores': psutil.cpu_count(logical=False),
            'logical_cores': psutil.cpu_count(logical=True),
            'current_freq': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            'max_freq': psutil.cpu_freq().max if psutil.cpu_freq() else 0,
        }
        
        # Memory information
        memory = psutil.virtual_memory()
        memory_info = {
            'total_bytes': memory.total,
            'available_bytes': memory.available,
            'total_mb': memory.total // (1024**2),
            'available_mb': memory.available // (1024**2),
            'total_gb': memory.total // (1024**3),
            'available_gb': memory.available // (1024**3),
        }
        
        # Network interfaces
        network_info = []
        for interface, addrs in psutil.net_if_addrs().items():
            if interface != 'lo':  # Skip loopback
                speed_info = self._get_interface_speed(interface)
                network_info.append({
                    'name': interface,
                    'addresses': [addr.address for addr in addrs],
                    'speed_mbps': speed_info['speed_mbps'],
                    'duplex': speed_info['duplex'],
                    'link_up': speed_info['link_up']
                })
        
        # Storage information
        storage_info = []
        for partition in psutil.disk_partitions():
            if partition.fstype and not partition.device.startswith('/dev/loop'):
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    storage_info.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'total_bytes': usage.total,
                        'free_bytes': usage.free,
                        'total_gb': usage.total // (1024**3),
                        'free_gb': usage.free // (1024**3)
                    })
                except PermissionError:
                    continue
        
        host_info = {
            'cpu': cpu_info,
            'memory': memory_info,
            'network': network_info,
            'storage': storage_info,
            'load_average': os.getloadavg(),
            'uptime_seconds': time.time() - psutil.boot_time() if 'time' in globals() else 0
        }
        
        logger.debug(f"Host info gathered: {cpu_info['logical_cores']} cores, {memory_info['total_gb']}GB RAM, {len(network_info)} network interfaces")
        return host_info
    
    def _get_interface_speed(self, interface: str) -> Dict[str, Any]:
        """Get network interface speed using ethtool"""
        try:
            result = subprocess.run(['ethtool', interface], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse ethtool output
                speed_match = re.search(r'Speed: (\d+)Mb/s', result.stdout)
                duplex_match = re.search(r'Duplex: (\w+)', result.stdout)
                link_match = re.search(r'Link detected: (\w+)', result.stdout)
                
                return {
                    'speed_mbps': int(speed_match.group(1)) if speed_match else 1000,
                    'duplex': duplex_match.group(1) if duplex_match else 'Full',
                    'link_up': link_match.group(1) == 'yes' if link_match else True
                }
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Fallback to default values
        return {'speed_mbps': 1000, 'duplex': 'Full', 'link_up': True}
    
    def _detect_numa_topology(self) -> Dict[str, Any]:
        """Detect NUMA topology for optimal CPU and memory allocation"""
        logger.debug("Detecting NUMA topology...")
        
        try:
            # Try to get NUMA info from /proc/cpuinfo and lscpu
            result = subprocess.run(['lscpu', '-J'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lscpu_data = json.loads(result.stdout)
                
                numa_nodes = {}
                cpu_mapping = {}
                
                # Parse lscpu JSON output
                for field in lscpu_data.get('lscpu', []):
                    if field['field'].startswith('NUMA node'):
                        node_match = re.match(r'NUMA node(\d+) CPU\(s\):', field['field'])
                        if node_match:
                            node_id = int(node_match.group(1))
                            cpu_list = self._parse_cpu_list(field['data'])
                            numa_nodes[node_id] = {
                                'cpus': cpu_list,
                                'memory_gb': 0  # Will be filled if available
                            }
                            
                            for cpu in cpu_list:
                                cpu_mapping[cpu] = node_id
                
                return {
                    'numa_nodes': numa_nodes,
                    'cpu_to_node': cpu_mapping,
                    'available': len(numa_nodes) > 1
                }
                
        except (subprocess.SubprocessError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Failed to detect NUMA topology: {e}")
        
        # Fallback: assume single NUMA node
        total_cpus = self.host_info['cpu']['logical_cores']
        return {
            'numa_nodes': {0: {'cpus': list(range(total_cpus)), 'memory_gb': 0}},
            'cpu_to_node': {i: 0 for i in range(total_cpus)},
            'available': False
        }
    
    def _parse_cpu_list(self, cpu_str: str) -> List[int]:
        """Parse CPU list string like '0-3,8-11' into list of integers"""
        cpus = []
        for part in cpu_str.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                cpus.extend(range(start, end + 1))
            else:
                cpus.append(int(part))
        return sorted(cpus)
    
    def allocate_cpus(self, percent: int) -> Dict[str, Any]:
        """
        Allocate CPU cores based on percentage with NUMA awareness.
        
        Args:
            percent: Percentage of CPU cores to allocate (1-100)
            
        Returns:
            Dict containing allocation details
        """
        logger.info(f"Allocating {percent}% of CPU resources...")
        
        if not 1 <= percent <= 100:
            raise ResourceAllocationError(f"CPU percentage must be 1-100, got {percent}")
        
        total_cores = self.host_info['cpu']['logical_cores']
        allocated_cores = max(1, int(total_cores * percent / 100))
        
        # NUMA-aware allocation
        if self.numa_topology['available']:
            # Prefer allocating from a single NUMA node if possible
            pinned_set = self._allocate_numa_aware_cpus(allocated_cores)
            preferred_node = self._get_preferred_numa_node(pinned_set)
        else:
            # Simple sequential allocation
            pinned_set = list(range(allocated_cores))
            preferred_node = 0
        
        allocation = {
            'requested_percent': percent,
            'total_host_cores': total_cores,
            'allocated_cores': allocated_cores,
            'pinned_set': pinned_set,
            'numa_node': preferred_node,
            'numa_aware': self.numa_topology['available'],
            'cpu_mask': self._create_cpu_mask(pinned_set)
        }
        
        logger.info(f"CPU allocation: {allocated_cores} cores ({pinned_set}) on NUMA node {preferred_node}")
        return allocation
    
    def _allocate_numa_aware_cpus(self, count: int) -> List[int]:
        """Allocate CPUs with NUMA node affinity"""
        numa_nodes = self.numa_topology['numa_nodes']
        
        # Find the NUMA node with the most available CPUs
        best_node = max(numa_nodes.keys(), key=lambda n: len(numa_nodes[n]['cpus']))
        node_cpus = numa_nodes[best_node]['cpus']
        
        if len(node_cpus) >= count:
            # Allocate from single node
            return node_cpus[:count]
        else:
            # Spread across nodes
            allocated = []
            for node_id, node_info in numa_nodes.items():
                needed = min(count - len(allocated), len(node_info['cpus']))
                allocated.extend(node_info['cpus'][:needed])
                if len(allocated) >= count:
                    break
            return allocated[:count]
    
    def _get_preferred_numa_node(self, cpu_set: List[int]) -> int:
        """Determine the preferred NUMA node for a CPU set"""
        cpu_to_node = self.numa_topology['cpu_to_node']
        node_counts = {}
        
        for cpu in cpu_set:
            node = cpu_to_node.get(cpu, 0)
            node_counts[node] = node_counts.get(node, 0) + 1
        
        return max(node_counts, key=node_counts.get) if node_counts else 0
    
    def _create_cpu_mask(self, cpu_set: List[int]) -> str:
        """Create CPU affinity mask from CPU set"""
        mask = 0
        for cpu in cpu_set:
            mask |= (1 << cpu)
        return hex(mask)
    
    def allocate_memory(self, percent: int) -> Dict[str, Any]:
        """
        Allocate memory based on percentage of available system memory.
        
        Args:
            percent: Percentage of total memory to allocate (1-100)
            
        Returns:
            Dict containing allocation details
        """
        logger.info(f"Allocating {percent}% of memory resources...")
        
        if not 1 <= percent <= 100:
            raise ResourceAllocationError(f"Memory percentage must be 1-100, got {percent}")
        
        memory_info = self.host_info['memory']
        
        # Use available memory for calculation to avoid overcommit
        base_memory = memory_info['available_bytes']
        allocated_bytes = int(base_memory * percent / 100)
        allocated_mb = allocated_bytes // (1024**2)
        allocated_gb = allocated_bytes // (1024**3)
        
        # Check for hugepage support
        hugepage_info = self._check_hugepage_support()
        
        allocation = {
            'requested_percent': percent,
            'total_memory_gb': memory_info['total_gb'],
            'available_memory_gb': memory_info['available_gb'],
            'allocated_bytes': allocated_bytes,
            'allocated_mb': allocated_mb,
            'allocated_gb': allocated_gb,
            'hugepage_support': hugepage_info['available'],
            'hugepage_size_kb': hugepage_info['size_kb'],
            'recommended_hugepages': hugepage_info['recommended_pages'] if hugepage_info['available'] else 0
        }
        
        logger.info(f"Memory allocation: {allocated_gb}GB ({allocated_mb}MB) from {memory_info['available_gb']}GB available")
        return allocation
    
    def _check_hugepage_support(self) -> Dict[str, Any]:
        """Check system hugepage support"""
        try:
            hugepage_path = Path('/sys/kernel/mm/hugepages')
            if hugepage_path.exists():
                # Look for 2MB hugepages (most common)
                for hugepage_dir in hugepage_path.iterdir():
                    if 'hugepages-2048kB' in hugepage_dir.name:
                        nr_hugepages = int((hugepage_dir / 'nr_hugepages').read_text().strip())
                        free_hugepages = int((hugepage_dir / 'free_hugepages').read_text().strip())
                        
                        return {
                            'available': True,
                            'size_kb': 2048,
                            'total_pages': nr_hugepages,
                            'free_pages': free_hugepages,
                            'recommended_pages': max(512, nr_hugepages // 4)  # 25% of available
                        }
        except (OSError, ValueError):
            pass
        
        return {'available': False, 'size_kb': 0, 'recommended_pages': 0}
    
    def allocate_storage(self, size_bytes: int) -> Dict[str, Any]:
        """
        Allocate storage volume with specified size.
        
        Args:
            size_bytes: Storage size in bytes
            
        Returns:
            Dict containing allocation details
        """
        logger.info(f"Allocating {size_bytes // (1024**3)}GB storage...")
        
        if size_bytes <= 0:
            raise ResourceAllocationError(f"Storage size must be positive, got {size_bytes}")
        
        # Find best storage device with sufficient space
        storage_info = self.host_info['storage']
        suitable_devices = [
            dev for dev in storage_info 
            if dev['free_bytes'] >= size_bytes and dev['mountpoint'] in ['/', '/home', '/var']
        ]
        
        if not suitable_devices:
            raise ResourceAllocationError(f"No storage device has {size_bytes // (1024**3)}GB free space")
        
        # Prefer root filesystem
        best_device = None
        for dev in suitable_devices:
            if dev['mountpoint'] == '/':
                best_device = dev
                break
        
        if not best_device:
            best_device = max(suitable_devices, key=lambda d: d['free_bytes'])
        
        # Try to use VMKit storage manager if available
        try:
            from .storage import StorageManager
            
            if not self.dry_run:
                storage_manager = StorageManager()
                
                # Create a volume name
                volume_name = f"vmkit-vol-{int(size_bytes // (1024**3))}gb"
                
                # Try to get default repository, create if needed
                try:
                    repo = storage_manager.get_repository('default')
                except:
                    # Create default repository
                    default_path = Path(best_device['mountpoint']) / 'vmkit-storage'
                    repo = storage_manager.create_repository('default', str(default_path))
                
                # Create volume
                volume_info = repo.create_volume(volume_name, f"{size_bytes // (1024**3)}G", 'qcow2')
                volume_path = volume_info['path']
            else:
                volume_path = f"/tmp/dry-run-volume-{size_bytes // (1024**3)}gb.qcow2"
        
        except ImportError:
            # Fallback: create simple volume path
            volume_path = Path(best_device['mountpoint']) / 'vmkit-volumes' / f"volume-{size_bytes // (1024**3)}gb.qcow2"
        
        allocation = {
            'size_bytes': size_bytes,
            'size_gb': size_bytes // (1024**3),
            'target_device': best_device['device'],
            'target_mountpoint': best_device['mountpoint'],
            'free_space_gb': best_device['free_gb'],
            'volume_path': str(volume_path),
            'format': 'qcow2',
            'thin_provisioned': True
        }
        
        logger.info(f"Storage allocation: {allocation['size_gb']}GB at {volume_path} on {best_device['device']}")
        return allocation
    
    def allocate_network(self, percent: int) -> Dict[str, Any]:
        """
        Allocate network bandwidth based on percentage of interface capacity.
        
        Args:
            percent: Percentage of network bandwidth to allocate (1-100)
            
        Returns:
            Dict containing allocation details  
        """
        logger.info(f"Allocating {percent}% of network bandwidth...")
        
        if not 1 <= percent <= 100:
            raise ResourceAllocationError(f"Network percentage must be 1-100, got {percent}")
        
        network_info = self.host_info['network']
        
        # Find the fastest active interface
        active_interfaces = [iface for iface in network_info if iface['link_up']]
        if not active_interfaces:
            raise ResourceAllocationError("No active network interfaces found")
        
        best_interface = max(active_interfaces, key=lambda i: i['speed_mbps'])
        allocated_mbps = int(best_interface['speed_mbps'] * percent / 100)
        
        # Generate TC (Traffic Control) configuration for bandwidth limiting
        tc_config = self._generate_tc_config(best_interface['name'], allocated_mbps)
        
        allocation = {
            'requested_percent': percent,
            'interface_name': best_interface['name'],
            'interface_speed_mbps': best_interface['speed_mbps'],
            'allocated_bandwidth_mbps': allocated_mbps,
            'tc_config': tc_config,
            'duplex': best_interface['duplex']
        }
        
        logger.info(f"Network allocation: {allocated_mbps}Mbps on {best_interface['name']} ({percent}% of {best_interface['speed_mbps']}Mbps)")
        return allocation
    
    def _generate_tc_config(self, interface: str, bandwidth_mbps: int) -> Dict[str, str]:
        """Generate Traffic Control configuration for bandwidth limiting"""
        # Convert Mbps to Kbits for tc
        bandwidth_kbit = bandwidth_mbps * 1000
        
        return {
            'qdisc_add': f"tc qdisc add dev {interface} root handle 1: htb default 30",
            'class_add': f"tc class add dev {interface} parent 1: classid 1:1 htb rate {bandwidth_kbit}kbit",
            'filter_add': f"tc filter add dev {interface} protocol ip parent 1:0 prio 1 handle 10 fw flowid 1:1",
            'qdisc_del': f"tc qdisc del dev {interface} root",  # For cleanup
        }
    
    def get_allocation_summary(self) -> Dict[str, Any]:
        """Get summary of current host resources available for allocation"""
        return {
            'cpu': {
                'total_cores': self.host_info['cpu']['logical_cores'],
                'numa_nodes': len(self.numa_topology['numa_nodes']),
                'numa_available': self.numa_topology['available']
            },
            'memory': {
                'total_gb': self.host_info['memory']['total_gb'],
                'available_gb': self.host_info['memory']['available_gb'],
                'hugepage_support': self._check_hugepage_support()['available']
            },
            'network': [
                {
                    'name': iface['name'],
                    'speed_mbps': iface['speed_mbps'],
                    'link_up': iface['link_up']
                }
                for iface in self.host_info['network']
            ],
            'storage': [
                {
                    'device': dev['device'],
                    'mountpoint': dev['mountpoint'],
                    'free_gb': dev['free_gb'],
                    'total_gb': dev['total_gb']
                }
                for dev in self.host_info['storage']
            ]
        }


    def allocate_storage_from(self, device_path: str, size_bytes: int) -> Dict[str, Any]:
        """
        Allocate storage from a specific device with specified size.
        
        Args:
            device_path: Storage device path (e.g., '/dev/nvme0n1', '/dev/sda')
            size_bytes: Size in bytes to allocate
            
        Returns:
            Dict containing allocation details
        """
        logger.info(f"Allocating {size_bytes // (1024**3)}GB from device {device_path}...")
        
        if size_bytes <= 0:
            raise ResourceAllocationError(f"Storage size must be positive, got {size_bytes}")
        
        # Validate device exists and is a block device
        device_path_obj = Path(device_path)
        if not device_path_obj.exists():
            raise ResourceAllocationError(f"Device {device_path} does not exist")
        
        # Get device information using lsblk
        try:
            result = subprocess.run(
                ['lsblk', '-J', '-b', device_path], 
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lsblk_data = json.loads(result.stdout)
                device_info = lsblk_data['blockdevices'][0]
                
                total_size = int(device_info['size'])
                if size_bytes > total_size:
                    raise ResourceAllocationError(
                        f"Requested size {size_bytes // (1024**3)}GB exceeds device capacity {total_size // (1024**3)}GB"
                    )
            else:
                # Fallback: assume device is valid
                total_size = size_bytes * 2  # Conservative estimate
        
        except (subprocess.SubprocessError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Could not get device info for {device_path}: {e}")
            total_size = size_bytes * 2  # Conservative estimate
        
        # Create partition/volume path
        if 'nvme' in device_path:
            volume_path = f"{device_path}p_vmkit_{size_bytes // (1024**3)}gb"
        else:
            volume_path = f"{device_path}_vmkit_{size_bytes // (1024**3)}gb"
        
        # Check if device supports partitioning
        supports_partitioning = self._check_device_partitioning(device_path)
        
        allocation = {
            'device_path': device_path,
            'size_bytes': size_bytes,
            'size_gb': size_bytes // (1024**3),
            'total_device_size': total_size,
            'total_device_gb': total_size // (1024**3),
            'volume_path': volume_path,
            'supports_partitioning': supports_partitioning,
            'raw_device': True,
            'allocation_type': 'hard_device'
        }
        
        logger.info(f"Storage allocation: {allocation['size_gb']}GB from {device_path} -> {volume_path}")
        return allocation
    
    def _check_device_partitioning(self, device_path: str) -> bool:
        """Check if device supports partitioning"""
        try:
            result = subprocess.run(
                ['fdisk', '-l', device_path], 
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False
    
    def allocate_cpu_from(self, range_str: str) -> Dict[str, Any]:
        """
        Allocate specific CPU cores from a range string.
        
        Args:
            range_str: CPU range string (e.g., '0-3', '0,2,4-7', '0-7,16-23')
            
        Returns:
            Dict containing allocation details
        """
        logger.info(f"Allocating CPUs from range: {range_str}")
        
        try:
            cpu_list = self._parse_cpu_list(range_str)
        except ValueError as e:
            raise ResourceAllocationError(f"Invalid CPU range '{range_str}': {e}")
        
        # Validate CPUs exist on system
        total_cpus = self.host_info['cpu']['logical_cores']
        invalid_cpus = [cpu for cpu in cpu_list if cpu >= total_cpus]
        if invalid_cpus:
            raise ResourceAllocationError(
                f"Invalid CPU IDs {invalid_cpus}. System has {total_cpus} cores (0-{total_cpus-1})"
            )
        
        # Check if CPUs are currently available (not heavily loaded)
        cpu_usage = self._get_cpu_usage_per_core()
        busy_cpus = [cpu for cpu in cpu_list if cpu_usage.get(cpu, 0) > 80]
        
        # Determine NUMA affinity
        numa_nodes = set()
        for cpu in cpu_list:
            node = self.numa_topology['cpu_to_node'].get(cpu, 0)
            numa_nodes.add(node)
        
        preferred_node = list(numa_nodes)[0] if len(numa_nodes) == 1 else None
        
        allocation = {
            'range_string': range_str,
            'allocated_cores': len(cpu_list),
            'cpu_list': cpu_list,
            'pinned_set': cpu_list,
            'numa_nodes': list(numa_nodes),
            'preferred_numa_node': preferred_node,
            'numa_aware': len(numa_nodes) == 1,
            'busy_cores': busy_cpus,
            'cpu_mask': self._create_cpu_mask(cpu_list),
            'allocation_type': 'hard_cpus'
        }
        
        logger.info(f"CPU allocation: {len(cpu_list)} cores {cpu_list} (NUMA nodes: {list(numa_nodes)})")
        if busy_cpus:
            logger.warning(f"Some allocated CPUs are busy: {busy_cpus}")
        
        return allocation
    
    def _get_cpu_usage_per_core(self) -> Dict[int, float]:
        """Get CPU usage percentage per core"""
        try:
            import psutil
            # Get per-CPU usage (requires a brief sampling period)
            cpu_percentages = psutil.cpu_percent(interval=0.1, percpu=True)
            return {i: usage for i, usage in enumerate(cpu_percentages)}
        except ImportError:
            logger.warning("psutil not available for per-core CPU usage")
            return {}
    
    def allocate_memory_from(self, numa_node: int, size_bytes: Optional[int] = None) -> Dict[str, Any]:
        """
        Allocate memory from a specific NUMA node.
        
        Args:
            numa_node: NUMA node ID (0-based)
            size_bytes: Size in bytes to allocate (None for entire node)
            
        Returns:
            Dict containing allocation details
        """
        logger.info(f"Allocating memory from NUMA node {numa_node}...")
        
        # Validate NUMA node exists
        if numa_node not in self.numa_topology['numa_nodes']:
            available_nodes = list(self.numa_topology['numa_nodes'].keys())
            raise ResourceAllocationError(
                f"NUMA node {numa_node} does not exist. Available nodes: {available_nodes}"
            )
        
        # Get NUMA node memory information
        node_info = self._get_numa_memory_info(numa_node)
        
        if size_bytes is None:
            # Allocate entire node
            allocated_bytes = node_info['total_bytes']
        else:
            if size_bytes <= 0:
                raise ResourceAllocationError(f"Memory size must be positive, got {size_bytes}")
            
            if size_bytes > node_info['available_bytes']:
                raise ResourceAllocationError(
                    f"Requested {size_bytes // (1024**3)}GB exceeds available {node_info['available_bytes'] // (1024**3)}GB on NUMA node {numa_node}"
                )
            
            allocated_bytes = size_bytes
        
        # Check for hugepage support on this NUMA node
        hugepage_info = self._check_numa_hugepage_support(numa_node)
        
        allocation = {
            'numa_node': numa_node,
            'node_total_bytes': node_info['total_bytes'],
            'node_available_bytes': node_info['available_bytes'],
            'allocated_bytes': allocated_bytes,
            'allocated_mb': allocated_bytes // (1024**2),
            'allocated_gb': allocated_bytes // (1024**3),
            'node_total_gb': node_info['total_bytes'] // (1024**3),
            'node_available_gb': node_info['available_bytes'] // (1024**3),
            'hugepage_support': hugepage_info['available'],
            'hugepage_size_kb': hugepage_info['size_kb'],
            'recommended_hugepages': hugepage_info.get('recommended_pages', 0),
            'allocation_type': 'hard_numa_memory'
        }
        
        logger.info(f"Memory allocation: {allocation['allocated_gb']}GB from NUMA node {numa_node} ({node_info['available_bytes'] // (1024**3)}GB available)")
        return allocation
    
    def _get_numa_memory_info(self, numa_node: int) -> Dict[str, Any]:
        """Get memory information for a specific NUMA node"""
        try:
            # Try to get NUMA memory info from /sys/devices/system/node
            meminfo_path = Path(f"/sys/devices/system/node/node{numa_node}/meminfo")
            if meminfo_path.exists():
                meminfo = meminfo_path.read_text()
                
                # Parse meminfo
                total_match = re.search(r'MemTotal:\s+(\d+)\s+kB', meminfo)
                free_match = re.search(r'MemFree:\s+(\d+)\s+kB', meminfo)
                
                if total_match and free_match:
                    total_kb = int(total_match.group(1))
                    free_kb = int(free_match.group(1))
                    
                    return {
                        'total_bytes': total_kb * 1024,
                        'available_bytes': free_kb * 1024
                    }
        
        except (OSError, ValueError) as e:
            logger.warning(f"Could not get NUMA node {numa_node} memory info: {e}")
        
        # Fallback: assume equal distribution across NUMA nodes
        total_memory = self.host_info['memory']['total_bytes']
        available_memory = self.host_info['memory']['available_bytes']
        numa_count = len(self.numa_topology['numa_nodes'])
        
        return {
            'total_bytes': total_memory // numa_count,
            'available_bytes': available_memory // numa_count
        }
    
    def _check_numa_hugepage_support(self, numa_node: int) -> Dict[str, Any]:
        """Check hugepage support for specific NUMA node"""
        try:
            hugepage_path = Path(f"/sys/devices/system/node/node{numa_node}/hugepages")
            if hugepage_path.exists():
                # Look for 2MB hugepages
                for hugepage_dir in hugepage_path.iterdir():
                    if 'hugepages-2048kB' in hugepage_dir.name:
                        nr_hugepages = int((hugepage_dir / 'nr_hugepages').read_text().strip())
                        free_hugepages = int((hugepage_dir / 'free_hugepages').read_text().strip())
                        
                        return {
                            'available': True,
                            'size_kb': 2048,
                            'total_pages': nr_hugepages,
                            'free_pages': free_hugepages,
                            'recommended_pages': max(128, free_hugepages // 4)
                        }
        except (OSError, ValueError):
            pass
        
        return self._check_hugepage_support()  # Fallback to system-wide check
    
    def allocate_gpu_from(self, pci_address: str) -> Dict[str, Any]:
        """
        Allocate a specific GPU device by PCI address.
        
        Args:
            pci_address: PCI address (e.g., '0000:01:00.0')
            
        Returns:
            Dict containing allocation details
        """
        logger.info(f"Allocating GPU from PCI address: {pci_address}")
        
        # Import VFIODeviceManager (avoid circular imports)
        try:
            from .vfio import VFIODeviceManager
            
            # Initialize VFIO manager
            vfio_manager = VFIODeviceManager(dry_run=self.dry_run)
            
            # Get device information
            vfio_device = vfio_manager.get_device(pci_address)
            if not vfio_device:
                raise ResourceAllocationError(f"PCI device {pci_address} not found")
            
            # Verify it's a GPU
            if not vfio_device.pci_device.is_gpu:
                raise ResourceAllocationError(f"Device {pci_address} is not a GPU (type: {vfio_device.pci_device.device_type})")
            
            # Check if device is available
            if not vfio_device.is_available:
                raise ResourceAllocationError(
                    f"GPU {pci_address} is not available (state: {vfio_device.state}, reserved_by: {vfio_device.reserved_by})"
                )
            
            # Bind to VFIO if not already bound
            if not vfio_manager.bind_to_vfio(pci_address):
                raise ResourceAllocationError(f"Failed to bind GPU {pci_address} to vfio-pci")
            
            # Get GPU capabilities
            gpu_caps = self._get_gpu_capabilities(vfio_device.pci_device)
            
            allocation = {
                'pci_address': pci_address,
                'vendor_name': vfio_device.pci_device.vendor_name,
                'device_name': vfio_device.pci_device.device_name,
                'vendor_id': vfio_device.pci_device.vendor_id,
                'device_id': vfio_device.pci_device.device_id,
                'iommu_group': vfio_device.pci_device.iommu_group,
                'bound_to_vfio': True,
                'capabilities': gpu_caps,
                'allocation_type': 'hard_gpu'
            }
            
            logger.info(f"GPU allocation: {vfio_device.pci_device.device_name} ({pci_address}) bound to vfio-pci")
            return allocation
            
        except ImportError as e:
            raise ResourceAllocationError(f"VFIO manager not available: {e}")
    
    def _get_gpu_capabilities(self, pci_device) -> Dict[str, Any]:
        """Get GPU capabilities and specifications"""
        capabilities = {
            'sriov_support': False,
            'vram_size': 'unknown',
            'compute_units': 'unknown',
            'pcie_generation': 'unknown'
        }
        
        try:
            # Try to get GPU information from various sources
            
            # Check for SR-IOV support
            sriov_path = Path(f"/sys/bus/pci/devices/{pci_device.pci_id}/sriov_totalvfs")
            if sriov_path.exists():
                total_vfs = int(sriov_path.read_text().strip())
                capabilities['sriov_support'] = total_vfs > 0
                capabilities['max_virtual_functions'] = total_vfs
            
            # Try to get additional info from lspci
            result = subprocess.run(
                ['lspci', '-v', '-s', pci_device.pci_id],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                lspci_output = result.stdout
                
                # Extract PCIe generation/width
                pcie_match = re.search(r'LnkSta:\s+Speed\s+([^,]+),\s+Width\s+x(\d+)', lspci_output)
                if pcie_match:
                    capabilities['pcie_speed'] = pcie_match.group(1)
                    capabilities['pcie_width'] = f"x{pcie_match.group(2)}"
        
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            logger.debug(f"Could not get GPU capabilities for {pci_device.pci_id}: {e}")
        
        return capabilities
