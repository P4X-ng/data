#!/usr/bin/env python3
"""
VMKit CLI - Human-friendly VM management
"""

import click
import sys
import logging
import re
from pathlib import Path
from typing import Optional

from .core import SecureVM, VMError
from .images import CloudImage, ExistingDisk, detect_image_type
from .cloudinit import CloudInitConfig, quick_config, ssh_only_config
from .passthrough import PassthroughManager, PCIDevice, find_gpu, find_nvme
from .host import HostCapture, VirtualizedHost
from .storage import StorageManager, StorageRepository
from .network import NetworkManager

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def vmkit():
    """VMKit - Simple Secure Boot VM management"""
    # Configure logging when CLI starts
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    pass


def _validate_percentage(ctx, param, value):
    """Validate percentage values (1-100)"""
    if value is None:
        return None
    
    # Handle percentage strings like "50%" or just "50"
    if isinstance(value, str):
        value = value.rstrip('%')
        try:
            value = int(value)
        except ValueError:
            raise click.BadParameter(f"Invalid percentage: {value}. Must be 1-100.")
    
    if not 1 <= value <= 100:
        raise click.BadParameter(f"Percentage must be between 1-100, got {value}")
    
    param_name = getattr(param, 'name', 'unknown').replace('\n', '').replace('\r', '')
    logger.debug(f"Validated percentage for {param_name}: {value}%")
    return value


def _validate_storage_size(ctx, param, value):
    """Validate storage size strings like '100G', '512M', '1T'"""
    if value is None:
        return None
        
    match = re.match(r'^(\d+(?:\.\d+)?)([KMGT]?)B?$', str(value).upper(), re.IGNORECASE)
    
    if not match:
        raise click.BadParameter(f"Invalid storage size: {value}. Use format like 100G, 512M, 1T")
    
    size_num, unit = match.groups()
    size_num = float(size_num)
    
    # Convert to bytes
    multipliers = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
    size_bytes = int(size_num * multipliers.get(unit, 1))
    
    param_name = getattr(param, 'name', 'unknown').replace('\n', '').replace('\r', '')
    logger.debug(f"Validated storage size for {param_name}: {size_bytes} bytes")
    return size_bytes


@vmkit.command()
@click.argument('name')
@click.argument('image_path')
@click.option('--memory', '-m', default='4G', help='Memory size (e.g., 4G, 2048M)')
@click.option('--cpus', '-c', default=4, type=int, help='Number of vCPUs')
# Percentage-based resource allocation options
@click.option('--cpu-percent', type=int, callback=_validate_percentage,
              help='Allocate percentage of host CPU cores (1-100%)')
@click.option('--memory-percent', type=int, callback=_validate_percentage,
              help='Allocate percentage of host memory (1-100%)')
@click.option('--gpu-percent', type=int, callback=_validate_percentage,
              help='Allocate percentage of GPU resources (1-100%)')
@click.option('--network-percent', type=int, callback=_validate_percentage,
              help='Allocate percentage of network bandwidth (1-100%)')
@click.option('--storage-size', callback=_validate_storage_size,
              help='Dedicated storage allocation (e.g., 100G, 512M, 1T)')
# Hard attribute allocation flags
@click.option('--storage-from', help='Allocate storage from specific device (e.g., /dev/nvme0n1)')
@click.option('--memory-from', type=int, help='Allocate memory from specific NUMA node (0, 1, etc.)')
@click.option('--cpu-from', help='Allocate specific CPU cores (e.g., "0-3,8-11")')
@click.option('--gpu-from', help='Allocate specific GPU by PCI address (e.g., "0000:01:00.0")')
@click.option('--all-the-passthru', is_flag=True,
              help='🚀 ULTIMATE MODE: Pass through ALL available devices with optional % overrides')
# Traditional options
@click.option('--username', '-u', default='ubuntu', help='Cloud-init username')
@click.option('--password', '-p', help='Cloud-init password (use SSH keys instead)')
@click.option('--ssh-key', help='SSH public key file (auto-detected if not specified)')
@click.option('--packages', help='Comma-separated list of packages to install')
@click.option('--graphics', default='spice', type=click.Choice(['spice', 'none']), 
              help='Graphics type')
@click.option('--no-secure-boot', is_flag=True, help='Disable Secure Boot')
@click.option('--start', is_flag=True, help='Start VM after creation')
# Legacy passthrough options (for backward compatibility)
@click.option('--gpu', help='GPU passthrough (PCI ID or auto-detect)')
@click.option('--nvme', help='NVMe passthrough (PCI ID or auto-detect)')
@click.option('--passthrough', multiple=True, help='Generic PCI passthrough (PCI ID)')
def create(name, image_path, memory, cpus, cpu_percent, memory_percent, gpu_percent,
           network_percent, storage_size, storage_from, memory_from, cpu_from, gpu_from,
           all_the_passthru, username, password, ssh_key, packages, graphics, no_secure_boot, 
           start, gpu, nvme, passthrough):
    """Create a new VM from an image"""
    
    try:
        # Log the percentage-based allocation parameters
        logger.debug(f"Creating VM '{name}' with resource percentages:")
        logger.debug(f"  CPU: {cpu_percent}%, Memory: {memory_percent}%, GPU: {gpu_percent}%, Network: {network_percent}%")
        logger.debug(f"  Storage: {storage_size} bytes, All-passthru: {all_the_passthru}")
        
        # Detect and configure image
        image = detect_image_type(image_path)
        
        # Configure cloud-init for cloud images
        if isinstance(image, CloudImage):
            ssh_keys = []
            if ssh_key:
                ssh_keys = [Path(ssh_key).read_text().strip()]
            
            pkg_list = packages.split(',') if packages else None
            
            cloud_init = quick_config(
                vm_name=name,
                username=username,
                password=password,
                ssh_keys=ssh_keys,
                packages=pkg_list
            )
            image.cloud_init_config = cloud_init
        
        # Handle resource allocation and passthrough devices
        passthrough_devices = []
        computed_cpus = cpus
        computed_memory = memory
        
        # Import resource allocator (will be created next)
        try:
            from .resources import ResourceAllocator
            from .vfio import VFIODeviceManager
            
            # Initialize resource allocator
            allocator = ResourceAllocator()
            vfio_manager = VFIODeviceManager()
            
            # Handle --all-the-passthru flag
            if all_the_passthru:
                click.echo("🚀 ULTIMATE PASSTHROUGH MODE ACTIVATED!")
                click.echo("Detecting and binding all available devices...")
                
                # Get all available passthrough devices
                all_devices = vfio_manager.list_passthru_devices()
                
                # Apply percentage overrides if specified
                if gpu_percent:
                    gpu_devices = allocator.allocate_gpu(gpu_percent)
                    passthrough_devices.extend(gpu_devices)
                    click.echo(f"🎮 Allocated {gpu_percent}% of GPU resources: {len(gpu_devices)} devices")
                else:
                    # Full GPU passthrough
                    gpu_devices = [d for d in all_devices if 'VGA' in d.device_class or 'Display' in d.device_class]
                    passthrough_devices.extend(gpu_devices)
                    click.echo(f"🎮 Full GPU passthrough: {len(gpu_devices)} devices")
                
                # Network devices
                if network_percent:
                    net_allocation = allocator.allocate_network(network_percent)
                    click.echo(f"🌐 Allocated {network_percent}% network bandwidth: {net_allocation['bandwidth_mbps']}Mbps")
                
                # Storage devices
                storage_devices = [d for d in all_devices if 'NVMe' in d.device_name or 'SATA' in d.device_name]
                passthrough_devices.extend(storage_devices)
                click.echo(f"💾 Storage passthrough: {len(storage_devices)} devices")
                
                # Other devices (USB controllers, audio, etc.)
                other_devices = [d for d in all_devices if d not in passthrough_devices]
                passthrough_devices.extend(other_devices)
                click.echo(f"🔌 Other device passthrough: {len(other_devices)} devices")
                
                # Force headless mode for maximum compatibility
                graphics = 'none'
                click.echo("📺 Forced headless mode for maximum passthrough compatibility")
            
            else:
                # Handle individual percentage allocations
                if cpu_percent:
                    cpu_allocation = allocator.allocate_cpus(cpu_percent)
                    computed_cpus = cpu_allocation['allocated_cores']
                    click.echo(f"⚡ CPU: Allocated {cpu_percent}% = {computed_cpus} cores (pinned to {cpu_allocation['pinned_set']})")
                
                if memory_percent:
                    memory_allocation = allocator.allocate_memory(memory_percent)
                    computed_memory = f"{memory_allocation['allocated_mb']}M"
                    click.echo(f"🧠 Memory: Allocated {memory_percent}% = {memory_allocation['allocated_mb']}MB")
                
                if gpu_percent:
                    gpu_devices = allocator.allocate_gpu(gpu_percent)
                    passthrough_devices.extend(gpu_devices)
                    click.echo(f"🎮 GPU: Allocated {gpu_percent}% = {len(gpu_devices)} devices/slices")
                
                if network_percent:
                    net_allocation = allocator.allocate_network(network_percent)
                    click.echo(f"🌐 Network: Allocated {network_percent}% = {net_allocation['bandwidth_mbps']}Mbps bandwidth")
                
                if storage_size:
                    storage_allocation = allocator.allocate_storage(storage_size)
                    click.echo(f"💾 Storage: Allocated {storage_size // (1024**3)}GB = {storage_allocation['volume_path']}")
                
                # ===== HARD ATTRIBUTE ALLOCATIONS =====
                # Handle hard attribute allocations (user-specified exact resources)
                
                if cpu_from:
                    cpu_allocation = allocator.allocate_cpu_from(cpu_from)
                    computed_cpus = cpu_allocation['allocated_cores']
                    click.echo(f"⚡ CPU: Allocated specific cores {cpu_from} = {computed_cpus} cores")
                    click.echo(f"     NUMA nodes: {cpu_allocation['numa_nodes']}")
                    if cpu_allocation.get('busy_cores'):
                        click.echo(f"     ⚠️  Warning: Some cores are busy: {cpu_allocation['busy_cores']}")
                
                if memory_from is not None:
                    # Use --storage-size if specified, otherwise allocate entire NUMA node
                    memory_size_bytes = storage_size if storage_size else None
                    memory_allocation = allocator.allocate_memory_from(memory_from, memory_size_bytes)
                    computed_memory = f"{memory_allocation['allocated_mb']}M"
                    click.echo(f"🧠 Memory: Allocated from NUMA node {memory_from} = {memory_allocation['allocated_gb']}GB")
                    if memory_allocation.get('hugepage_support'):
                        click.echo(f"     🚀 Hugepage support available ({memory_allocation['hugepage_size_kb']}KB pages)")
                
                if storage_from:
                    # Use --storage-size if specified, otherwise allocate reasonable default
                    storage_bytes = storage_size if storage_size else 100 * 1024**3  # 100GB default
                    storage_allocation = allocator.allocate_storage_from(storage_from, storage_bytes)
                    click.echo(f"💾 Storage: Allocated {storage_allocation['size_gb']}GB from {storage_from}")
                    click.echo(f"     Volume: {storage_allocation['volume_path']}")
                    if not storage_allocation.get('supports_partitioning'):
                        click.echo(f"     ⚠️  Warning: Device may not support partitioning")
                
                if gpu_from:
                    gpu_allocation = allocator.allocate_gpu_from(gpu_from)
                    # Convert to format expected by passthrough_devices
                    from dataclasses import dataclass
                    @dataclass
                    class GPUDevice:
                        pci_id: str
                        device_name: str
                        vendor_name: str
                    
                    gpu_device = GPUDevice(
                        pci_id=gpu_allocation['pci_address'],
                        device_name=gpu_allocation['device_name'],
                        vendor_name=gpu_allocation['vendor_name']
                    )
                    passthrough_devices.append(gpu_device)
                    click.echo(f"🎮 GPU: Allocated {gpu_allocation['device_name']} ({gpu_allocation['pci_address']})")
                    if gpu_allocation['capabilities'].get('sriov_support'):
                        click.echo(f"     🚀 SR-IOV support available")
                    if gpu_allocation['capabilities'].get('pcie_speed'):
                        click.echo(f"     PCIe: {gpu_allocation['capabilities']['pcie_speed']} {gpu_allocation['capabilities'].get('pcie_width', '')}")
                
                # Legacy GPU passthrough (backward compatibility)
                if gpu:
                    if gpu == 'auto':
                        gpu_device = find_gpu()
                        if gpu_device:
                            passthrough_devices.append(gpu_device)
                            click.echo(f"Auto-detected GPU: {gpu_device.device_name} ({gpu_device.pci_id})")
                        else:
                            click.echo("No GPU found for auto-detection", err=True)
                    else:
                        manager = PassthroughManager()
                        gpu_device = manager.get_device_by_id(gpu)
                        if gpu_device:
                            passthrough_devices.append(gpu_device)
                        else:
                            click.echo(f"GPU device {gpu} not found", err=True)
                
                # Legacy NVMe passthrough
                if nvme:
                    if nvme == 'auto':
                        nvme_device = find_nvme()
                        if nvme_device:
                            passthrough_devices.append(nvme_device)
                            click.echo(f"Auto-detected NVMe: {nvme_device.device_name} ({nvme_device.pci_id})")
                        else:
                            click.echo("No NVMe device found for auto-detection", err=True)
                    else:
                        manager = PassthroughManager()
                        nvme_device = manager.get_device_by_id(nvme)
                        if nvme_device:
                            passthrough_devices.append(nvme_device)
                        else:
                            click.echo(f"NVMe device {nvme} not found", err=True)
                
                # Generic passthrough devices
                if passthrough:
                    manager = PassthroughManager()
                    for pci_id in passthrough:
                        device = manager.get_device_by_id(pci_id)
                        if device:
                            passthrough_devices.append(device)
                        else:
                            click.echo(f"PCI device {pci_id} not found", err=True)
            
        except ImportError:
            # Fallback to legacy behavior if new modules not available yet
            logger.warning("Resource allocator not available, falling back to legacy passthrough")
            
            # Legacy GPU passthrough
            if gpu:
                if gpu == 'auto':
                    gpu_device = find_gpu()
                    if gpu_device:
                        passthrough_devices.append(gpu_device)
                        click.echo(f"Auto-detected GPU: {gpu_device.device_name} ({gpu_device.pci_id})")
                    else:
                        click.echo("No GPU found for auto-detection", err=True)
                else:
                    manager = PassthroughManager()
                    gpu_device = manager.get_device_by_id(gpu)
                    if gpu_device:
                        passthrough_devices.append(gpu_device)
                    else:
                        click.echo(f"GPU device {gpu} not found", err=True)
            
            # Legacy NVMe passthrough  
            if nvme:
                if nvme == 'auto':
                    nvme_device = find_nvme()
                    if nvme_device:
                        passthrough_devices.append(nvme_device)
                        click.echo(f"Auto-detected NVMe: {nvme_device.device_name} ({nvme_device.pci_id})")
                    else:
                        click.echo("No NVMe device found for auto-detection", err=True)
                else:
                    manager = PassthroughManager()
                    nvme_device = manager.get_device_by_id(nvme)
                    if nvme_device:
                        passthrough_devices.append(nvme_device)
                    else:
                        click.echo(f"NVMe device {nvme} not found", err=True)
            
            # Generic passthrough devices
            if passthrough:
                manager = PassthroughManager()
                for pci_id in passthrough:
                    device = manager.get_device_by_id(pci_id)
                    if device:
                        passthrough_devices.append(device)
                    else:
                        click.echo(f"PCI device {pci_id} not found", err=True)
        
        # Create VM with computed resources
        vm = SecureVM(
            name=name,
            memory=computed_memory,
            cpus=computed_cpus,
            image=image,
            secure_boot=not no_secure_boot,
            graphics=graphics,
            passthrough_devices=passthrough_devices
        )
        
        click.echo(f"Creating VM '{name}' with optimized resource allocation...")
        click.echo(f"  Memory: {computed_memory}")
        click.echo(f"  CPUs: {computed_cpus}")
        click.echo(f"  Passthrough devices: {len(passthrough_devices)}")
        
        vm.create()
        click.echo("VM created successfully with advanced resource allocation!")
        
        if start:
            click.echo("Starting VM...")
            vm.start()
            click.echo("VM started successfully")
            
            if graphics == 'none':
                click.echo(f"Connect with: vmkit console {name}")
            else:
                click.echo("VM console should open automatically")
        
    except (VMError, ValueError, FileNotFoundError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.argument('name')
def start(name):
    """Start a VM"""
    try:
        vm = SecureVM(name)
        if vm.is_active():
            click.echo(f"VM '{name}' is already running")
            return
        
        vm.start()
        click.echo(f"VM '{name}' started")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.argument('name')
@click.option('--force', is_flag=True, help='Force stop (power off)')
def stop(name):
    """Stop a VM"""
    try:
        vm = SecureVM(name)
        if not vm.is_active():
            click.echo(f"VM '{name}' is not running")
            return
        
        if force:
            click.echo(f"Force stopping VM '{name}'...")
            vm.stop(force=True)
        else:
            click.echo(f"Gracefully stopping VM '{name}'...")
            vm.stop(force=False)
        
        click.echo(f"VM '{name}' stopped")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.argument('name')
@click.option('--force', is_flag=True, help='Skip confirmation')
def destroy(name, force):
    """Destroy (delete) a VM"""
    if not force:
        click.confirm(f"Are you sure you want to destroy VM '{name}'?", abort=True)
    
    try:
        vm = SecureVM(name)
        vm.destroy()
        click.echo(f"VM '{name}' destroyed")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.argument('name')
def console(name):
    """Connect to VM console"""
    try:
        vm = SecureVM(name)
        if not vm.is_defined():
            click.echo(f"VM '{name}' does not exist", err=True)
            sys.exit(1)
        
        if not vm.is_active():
            click.echo(f"VM '{name}' is not running", err=True)
            sys.exit(1)
        
        click.echo(f"Connecting to console of '{name}' (Ctrl+] to exit)...")
        vm.console()
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.argument('name')
@click.option('--user', '-u', help='SSH username')
def ssh(name):
    """SSH to a VM (requires VM to have SSH and network access)"""
    try:
        vm = SecureVM(name)
        if not vm.is_active():
            click.echo(f"VM '{name}' is not running", err=True)
            sys.exit(1)
        
        # This is a basic implementation - would need network introspection
        # to find the actual IP address
        click.echo(f"SSH to '{name}' - you'll need to find the IP address")
        click.echo("Try: virsh domifaddr " + name)
        
        # For now, just show the command
        user_part = f"{user}@" if user else ""
        click.echo(f"ssh {user_part}$(virsh domifaddr {name} | awk '/ipv4/ {{print $4}}' | cut -d'/' -f1)")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.option('--all', '-a', is_flag=True, help='Show all VMs (including inactive)')
def list(all):
    """List VMs"""
    try:
        import libvirt
        
        conn = libvirt.open("qemu:///system")
        if conn is None:
            click.echo("Error: Failed to connect to libvirt", err=True)
            sys.exit(1)
        if all:
            domains = conn.listAllDomains()
        else:
            domains = conn.listAllDomains(libvirt.VIR_CONNECT_LIST_DOMAINS_ACTIVE)
        
        if not domains:
            click.echo("No VMs found")
            return
        
        # Table header
        click.echo(f"{'Name':<20} {'State':<10} {'Memory':<8} {'vCPUs':<6}")
        click.echo("-" * 50)
        
        for domain in domains:
            name = domain.name()
            
            # Get state
            state_map = {
                libvirt.VIR_DOMAIN_NOSTATE: "no state",
                libvirt.VIR_DOMAIN_RUNNING: "running",
                libvirt.VIR_DOMAIN_BLOCKED: "blocked", 
                libvirt.VIR_DOMAIN_PAUSED: "paused",
                libvirt.VIR_DOMAIN_SHUTDOWN: "shutdown",
                libvirt.VIR_DOMAIN_SHUTOFF: "shutoff",
                libvirt.VIR_DOMAIN_CRASHED: "crashed",
            }
            
            state, _ = domain.state()
            state_name = state_map.get(state, f"unknown({state})")
            
            info = domain.info()
            memory_mb = info[1] // 1024
            vcpus = info[3]
            
            click.echo(f"{name:<20} {state_name:<10} {memory_mb}M{'':<3} {vcpus:<6}")
        
        conn.close()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.argument('name')
def info(name):
    """Show detailed VM information"""
    try:
        vm = SecureVM(name)
        info = vm.info()
        
        click.echo(f"VM Information: {name}")
        click.echo("-" * 30)
        
        for key, value in info.items():
            click.echo(f"{key.replace('_', ' ').title():<15}: {value}")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
def devices():
    """List available PCI devices for passthrough"""
    try:
        manager = PassthroughManager()
        manager.print_device_summary()
        
    except (VMError, Exception) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Snapshot management commands
@vmkit.command()
@click.argument('vm_name')
@click.argument('snapshot_name')
@click.option('--description', '-d', help='Description for the snapshot')
def snapshot(vm_name, snapshot_name, description):
    """Create a snapshot of a VM"""
    try:
        vm = SecureVM(vm_name)
        if not vm.is_defined():
            click.echo(f"VM '{vm_name}' does not exist", err=True)
            sys.exit(1)
        
        vm.create_snapshot(snapshot_name, description or "")
        click.echo(f"Created snapshot '{snapshot_name}' for VM '{vm_name}'")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.argument('vm_name')
def snapshots(vm_name):
    """List snapshots for a VM"""
    try:
        vm = SecureVM(vm_name)
        if not vm.is_defined():
            click.echo(f"VM '{vm_name}' does not exist", err=True)
            sys.exit(1)
        
        snapshot_list = vm.list_snapshots()
        
        if not snapshot_list:
            click.echo(f"No snapshots found for VM '{vm_name}'")
            return
        
        # Table header
        click.echo(f"{'Name':<20} {'State':<10} {'Creation Time':<20}")
        click.echo("-" * 50)
        
        for snap in snapshot_list:
            click.echo(f"{snap['name']:<20} {snap['state']:<10} {snap['creation_time']:<20}")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.argument('vm_name')
@click.argument('snapshot_name')
def revert(vm_name, snapshot_name):
    """Revert VM to a snapshot"""
    try:
        vm = SecureVM(vm_name)
        if not vm.is_defined():
            click.echo(f"VM '{vm_name}' does not exist", err=True)
            sys.exit(1)
        
        vm.revert_snapshot(snapshot_name)
        click.echo(f"Reverted VM '{vm_name}' to snapshot '{snapshot_name}'")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.command()
@click.argument('vm_name')
@click.argument('snapshot_name')
@click.option('--force', is_flag=True, help='Skip confirmation')
def delete_snapshot(vm_name, snapshot_name, force):
    """Delete a VM snapshot"""
    if not force:
        click.confirm(f"Are you sure you want to delete snapshot '{snapshot_name}' from VM '{vm_name}'?", abort=True)
    
    try:
        vm = SecureVM(vm_name)
        if not vm.is_defined():
            click.echo(f"VM '{vm_name}' does not exist", err=True)
            sys.exit(1)
        
        vm.delete_snapshot(snapshot_name)
        click.echo(f"Deleted snapshot '{snapshot_name}' from VM '{vm_name}'")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Host virtualization commands
@vmkit.group()
def host():
    """Host virtualization utilities"""
    pass


@host.command()
@click.argument('vm_name')
@click.option('--capture-disk', is_flag=True, help='Capture disk image (WARNING: Large and slow!)')
@click.option('--output-dir', '-o', help='Output directory for captured data')
@click.option('--dry-run', is_flag=True, help='Show what would be captured without doing it')
def capture(vm_name, capture_disk, output_dir, dry_run):
    """Capture current host system state for virtualization"""
    try:
        if dry_run:
            click.echo("DRY RUN: Would capture the following:")
            click.echo("- Hardware inventory (CPU, memory, storage, network)")
            click.echo("- Software inventory (packages, services, configuration)")
            click.echo("- Network configuration")
            if capture_disk:
                click.echo("- Boot disk image (WARNING: This can be very large!)")
            click.echo(f"Output directory: {output_dir or 'auto-generated temp directory'}")
            return
        
        # Create host capture instance
        host_capture = HostCapture(target_dir=output_dir)
        
        click.echo("Starting host system capture...")
        
        if capture_disk:
            click.confirm(
                "WARNING: Disk capture can take hours and use significant disk space. Continue?",
                abort=True
            )
        
        # Perform the capture
        summary = host_capture.full_capture(include_disk=capture_disk, boot_disk_only=True)
        
        click.echo("\nCapture completed successfully!")
        click.echo(f"Data stored in: {summary['target_directory']}")
        click.echo(f"Hardware info: {summary['hardware_file']}")
        click.echo(f"Software info: {summary['software_file']}")
        click.echo(f"Network info: {summary['network_file']}")
        
        if summary.get('disk_images'):
            click.echo("Disk images:")
            for img in summary['disk_images']:
                click.echo(f"  - {img}")
        
        click.echo(f"\nTo create a VM from this capture, run:")
        if summary.get('disk_images'):
            disk_path = summary['disk_images'][0]
            click.echo(f"vmkit host virtualize {vm_name} --capture-dir {summary['target_directory']} --disk-image {disk_path}")
        else:
            click.echo(f"vmkit host virtualize {vm_name} --capture-dir {summary['target_directory']} --disk-image <path-to-disk-image>")
        
    except (VMError, Exception) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@host.command()
@click.argument('vm_name')
@click.option('--capture-dir', required=True, help='Directory with host capture data')
@click.option('--disk-image', required=True, help='Path to disk image file')
@click.option('--memory', '-m', help='Memory size (auto-detected from host if not specified)')
@click.option('--cpus', '-c', type=int, help='Number of vCPUs (auto-detected from host if not specified)')
@click.option('--start', is_flag=True, help='Start VM after creation')
def virtualize(vm_name, capture_dir, disk_image, memory, cpus, start):
    """Create a VM from captured host system state"""
    try:
        # Load the host capture
        capture = HostCapture(target_dir=capture_dir)
        
        # Check if capture data exists
        capture_path = Path(capture_dir).resolve()
        if '..' in str(capture_path):
            click.echo("Error: Invalid capture directory path", err=True)
            sys.exit(1)
        
        capture_summary_file = capture_path / "capture_summary.json"
        if not capture_summary_file.exists():
            click.echo(f"Error: Capture data not found in {capture_dir}", err=True)
            click.echo("Run 'vmkit host capture' first to capture host state.")
            sys.exit(1)
        
        # Load existing hardware info if available
        try:
            hw_file = capture_path / "hardware.json"
            if hw_file.exists():
                import json
                with open(hw_file) as f:
                    capture.hardware_info = json.load(f)
            else:
                capture.capture_hardware()
        except Exception as e:
            logger.warning(f"Could not load hardware info: {e}")
            capture.capture_hardware()
        
        # Create VirtualizedHost VM
        vm_kwargs = {}
        if memory:
            vm_kwargs['memory'] = memory
        if cpus:
            vm_kwargs['cpus'] = cpus
        
        vm = VirtualizedHost(
            name=vm_name,
            host_capture=capture,
            disk_image_path=disk_image,
            **vm_kwargs
        )
        
        click.echo(f"Creating virtualized host VM '{vm_name}'...")
        vm.create_with_host_config()
        click.echo("VM created successfully with host optimizations")
        
        if start:
            click.echo("Starting VM...")
            vm.start()
            click.echo("VM started successfully")
            click.echo(f"Connect with: vmkit console {vm_name}")
        
        # Show VM info
        info = vm.info()
        click.echo(f"\nVM Configuration:")
        click.echo(f"  Memory: {info.get('memory_mb', 'unknown')}MB")
        click.echo(f"  vCPUs: {info.get('vcpus', 'unknown')}")
        click.echo(f"  Secure Boot: {info.get('secure_boot', 'unknown')}")
        click.echo(f"  Host capture: {info.get('host_capture_dir', 'unknown')}")
        
    except (VMError, Exception) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@host.command()
def info():
    """Show current host system information"""
    try:
        capture = HostCapture()
        
        click.echo("Capturing current host information...")
        hw_info = capture.capture_hardware()
        
        click.echo("\nHost System Information:")
        click.echo("=" * 40)
        
        # CPU info
        cpu = hw_info.get('cpu', {})
        click.echo(f"CPU Model: {cpu.get('model', 'Unknown')}")
        click.echo(f"CPU Cores: {cpu.get('cores', 'Unknown')}")
        click.echo(f"Virtualization: {'Supported' if cpu.get('virtualization_support') else 'Not supported'}")
        
        # Memory info  
        memory = hw_info.get('memory', {})
        memory_total_gb = memory.get('total', 0) // (1024**3)
        memory_available_gb = memory.get('available', 0) // (1024**3)
        click.echo(f"Memory: {memory_available_gb}GB available / {memory_total_gb}GB total")
        
        # Disk info
        disks = hw_info.get('disks', [])
        click.echo(f"\nDisk Usage:")
        for disk in disks:
            if disk['mountpoint'] == '/':
                disk_total_gb = disk['total'] // (1024**3)
                disk_free_gb = disk['free'] // (1024**3)
                click.echo(f"  Root filesystem: {disk_free_gb}GB free / {disk_total_gb}GB total")
        
        # Network interfaces
        interfaces = hw_info.get('network', [])
        click.echo(f"\nNetwork Interfaces: {len(interfaces)} found")
        for iface in interfaces:
            if iface['name'] != 'lo':  # Skip loopback
                click.echo(f"  - {iface['name']}")
        
        # Virtualization readiness
        click.echo(f"\nVirtualization Readiness:")
        if cpu.get('virtualization_support'):
            click.echo("  ✓ CPU supports hardware virtualization")
        else:
            click.echo("  ✗ CPU does not support hardware virtualization")
        
        if memory_total_gb >= 4:
            click.echo("  ✓ Sufficient memory for hosting VMs")
        else:
            click.echo("  ⚠ Limited memory for hosting VMs")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Storage management commands
@vmkit.group()
def storage():
    """Storage repository management"""
    pass


@storage.command()
@click.argument('name')
@click.argument('path')
@click.option('--autostart', is_flag=True, default=True, help='Auto-start repository')
def create_repo(name, path, autostart):
    """Create a storage repository"""
    try:
        manager = StorageManager()
        repo = manager.create_repository(name, path, auto_start=autostart)
        info = repo.info()
        
        click.echo(f"Created storage repository '{name}'")
        click.echo(f"  Path: {info['path']}")
        click.echo(f"  Status: {info['status']}")
        click.echo(f"  Autostart: {info.get('autostart', False)}")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@storage.command()
def list_repos():
    """List storage repositories"""
    try:
        manager = StorageManager()
        repos = manager.list_repositories()
        
        if not repos:
            click.echo("No storage repositories found")
            return
        
        # Table header
        click.echo(f"{'Name':<15} {'Status':<10} {'Path':<30} {'Capacity':<10}")
        click.echo("-" * 70)
        
        for repo in repos:
            capacity = repo.get('capacity', 0)
            if capacity > 0:
                capacity_str = f"{capacity // (1024**3)}GB"
            else:
                capacity_str = "N/A"
            
            click.echo(f"{repo['name']:<15} {repo['status']:<10} {repo.get('path', 'N/A'):<30} {capacity_str:<10}")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@storage.command()
@click.argument('name')
@click.option('--force', is_flag=True, help='Force removal even if repository contains volumes')
def remove_repo(name, force):
    """Remove a storage repository"""
    try:
        if not force:
            click.confirm(f"Are you sure you want to remove repository '{name}'?", abort=True)
        
        manager = StorageManager()
        manager.delete_repository(name, force=force)
        
        click.echo(f"Removed storage repository '{name}'")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@storage.command()
@click.argument('repo_name')
@click.argument('volume_name')
@click.argument('size')
@click.option('--format', default='qcow2', help='Volume format (qcow2, raw, etc.)')
def create_volume(repo_name, volume_name, size, format):
    """Create a volume in a repository"""
    try:
        manager = StorageManager()
        repo = manager.get_repository(repo_name)
        
        volume_info = repo.create_volume(volume_name, size, format)
        
        click.echo(f"Created volume '{volume_name}' in repository '{repo_name}'")
        click.echo(f"  Path: {volume_info['path']}")
        click.echo(f"  Size: {volume_info['capacity'] // (1024**3)}GB")
        click.echo(f"  Format: {volume_info['format']}")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@storage.command()
@click.argument('repo_name')
def list_volumes(repo_name):
    """List volumes in a repository"""
    try:
        manager = StorageManager()
        repo = manager.get_repository(repo_name)
        volumes = repo.list_volumes()
        
        if not volumes:
            click.echo(f"No volumes found in repository '{repo_name}'")
            return
        
        # Table header
        click.echo(f"{'Name':<20} {'Size':<8} {'Allocated':<10} {'Path':<40}")
        click.echo("-" * 85)
        
        for vol in volumes:
            size_gb = vol['capacity'] // (1024**3) if vol['capacity'] > 0 else 0
            alloc_gb = vol['allocation'] // (1024**3) if vol['allocation'] > 0 else 0
            
            click.echo(f"{vol['name']:<20} {size_gb}GB{'':<4} {alloc_gb}GB{'':<6} {vol['path']:<40}")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Network management commands
@vmkit.group()
def network():
    """Network management"""
    pass


@network.command()
def list_networks():
    """List networks"""
    try:
        manager = NetworkManager()
        networks = manager.list_networks()
        
        if not networks:
            click.echo("No networks found")
            return
        
        # Table header
        click.echo(f"{'Name':<15} {'Mode':<10} {'Status':<8} {'Address':<15} {'DHCP Range':<20}")
        click.echo("-" * 75)
        
        for net in networks:
            status = "active" if net.get('active') else "inactive"
            dhcp_range = ""
            if net.get('dhcp_start') and net.get('dhcp_end'):
                dhcp_range = f"{net['dhcp_start']} - {net['dhcp_end']}"
            
            click.echo(f"{net['name']:<15} {net.get('mode', 'N/A'):<10} {status:<8} {net.get('address', 'N/A'):<15} {dhcp_range:<20}")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@network.command()
@click.argument('name')
@click.option('--subnet', default='192.168.100.0/24', help='Network subnet in CIDR notation')
@click.option('--dhcp-start', help='DHCP range start (auto-calculated if not specified)')
@click.option('--dhcp-end', help='DHCP range end (auto-calculated if not specified)')
@click.option('--autostart', is_flag=True, default=True, help='Enable autostart')
def create_nat(name, subnet, dhcp_start, dhcp_end, autostart):
    """Create a NAT network"""
    try:
        manager = NetworkManager()
        net_info = manager.create_nat_network(
            name, subnet, dhcp_start, dhcp_end, autostart
        )
        
        click.echo(f"Created NAT network '{name}'")
        click.echo(f"  Subnet: {subnet}")
        click.echo(f"  Gateway: {net_info.get('address')}")
        if net_info.get('dhcp_start'):
            click.echo(f"  DHCP Range: {net_info['dhcp_start']} - {net_info['dhcp_end']}")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@network.command()
@click.argument('name')
@click.argument('bridge_interface')
@click.option('--autostart', is_flag=True, default=True, help='Enable autostart')
def create_bridge(name, bridge_interface, autostart):
    """Create a bridge network"""
    try:
        manager = NetworkManager()
        manager.create_bridge_network(name, bridge_interface, autostart)
        
        click.echo(f"Created bridge network '{name}'")
        click.echo(f"  Bridge interface: {bridge_interface}")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@network.command()
@click.argument('name')
@click.option('--force', is_flag=True, help='Force deletion even if VMs are connected')
def delete_network(name, force):
    """Delete a network"""
    try:
        if not force:
            click.confirm(f"Are you sure you want to delete network '{name}'?", abort=True)
        
        manager = NetworkManager()
        manager.delete_network(name, force=force)
        
        click.echo(f"Deleted network '{name}'")
        
    except VMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@vmkit.group()
def cloud():
    """Cloud-init utilities"""
    pass


@cloud.command()
@click.argument('vm_name')
@click.option('--username', '-u', default='ubuntu', help='Username')
@click.option('--password', '-p', help='Password')
@click.option('--ssh-key', help='SSH public key file')
@click.option('--packages', help='Comma-separated packages')
@click.option('--output', '-o', help='Output ISO path')
def seed(vm_name, username, password, ssh_key, packages, output):
    """Generate a cloud-init seed ISO"""
    try:
        ssh_keys = []
        if ssh_key:
            ssh_key_path = Path(ssh_key).resolve()
            if '..' in str(ssh_key_path) or not ssh_key_path.is_file():
                click.echo("Error: Invalid SSH key path", err=True)
                sys.exit(1)
            ssh_keys = [ssh_key_path.read_text().strip()]
        
        pkg_list = packages.split(',') if packages else None
        
        config = quick_config(
            vm_name=vm_name,
            username=username,
            password=password,
            ssh_keys=ssh_keys,
            packages=pkg_list
        )
        
        if not output:
            output = f"seed-{vm_name}.iso"
        
        iso_path = config.create_seed_iso(output)
        click.echo(f"Created cloud-init seed ISO: {iso_path}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    vmkit()
