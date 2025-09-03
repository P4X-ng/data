# VMKit - Advanced VM Management with Host Virtualization

A comprehensive Python toolkit for libvirt/KVM with built-in UEFI Secure Boot support, host virtualization capabilities, and intuitive storage/network management.

## New in This Version

✨ **Host Virtualization**: Capture and virtualize your current machine  
🗂️ **Storage Repositories**: Intuitive storage pool management  
🌐 **Advanced Networking**: NAT, bridge, and isolated networks with port forwarding  
📡 **Migration Support**: Live VM migration between hosts (planned)  
🔥 **Hot-plugging**: Runtime CPU, memory, and device management (planned)

## Features

- **Secure Boot by default** - Automatically configures UEFI with Microsoft keys
- **Cloud image support** - Works seamlessly with Ubuntu cloud images  
- **Simple API** - Clean Python classes and CLI commands
- **Auto-detection** - Automatically detects image types and OVMF paths
- **Cloud-init integration** - Generates NoCloud seed ISOs automatically

## Quick Start

### Installation

```bash
# System dependencies (Ubuntu/Debian)
sudo apt install -y qemu-kvm libvirt-daemon-system libvirt-clients ovmf \
                   cloud-image-utils python3-pip

# Add user to libvirt group
sudo usermod -aG libvirt $USER
newgrp libvirt

# Install VMKit
pip3 install -e .
```

### CLI Usage

```bash
# Create and start a VM from Ubuntu cloud image
vmkit create myvm ubuntu-22.04-server-cloudimg-amd64.img --start

# List VMs
vmkit list

# Connect to console
vmkit console myvm

# Stop and destroy
vmkit stop myvm
vmkit destroy myvm --force
```

### Python API Usage

```python
from vmkit import SecureVM, CloudImage, CloudInitConfig

# Configure cloud-init
cloud_init = CloudInitConfig(
    instance_id="myvm",
    hostname="myvm", 
    username="ubuntu",
    password_auth=False  # SSH keys only
)

# Create VM with cloud image
image = CloudImage("ubuntu-22.04-server-cloudimg-amd64.img", 
                   cloud_init_config=cloud_init)

vm = SecureVM(
    name="myvm",
    memory="4G", 
    cpus=4,
    image=image,
    secure_boot=True
)

# Lifecycle management
vm.create()
vm.start()

print(vm.info())

# When done
vm.stop()
vm.destroy()
```

## Command Reference

### VM Management
- `vmkit create <name> <image>` - Create VM from image
- `vmkit start <name>` - Start VM
- `vmkit stop <name>` - Stop VM gracefully
- `vmkit destroy <name>` - Delete VM permanently
- `vmkit list` - List VMs
- `vmkit info <name>` - Show VM details
- `vmkit console <name>` - Connect to console

### Host Virtualization 🆕
- `vmkit host info` - Show current host system information
- `vmkit host capture <vm_name> [--capture-disk] [--output-dir DIR]` - Capture host state
- `vmkit host virtualize <vm_name> --capture-dir DIR --disk-image PATH` - Create VM from host

### Storage Repository Management 🆕
- `vmkit storage list-repos` - List storage repositories
- `vmkit storage create-repo <name> <path>` - Create storage repository
- `vmkit storage remove-repo <name>` - Remove repository
- `vmkit storage create-volume <repo> <name> <size>` - Create volume
- `vmkit storage list-volumes <repo>` - List volumes in repository

### Network Management 🆕
- `vmkit network list-networks` - List networks
- `vmkit network create-nat <name> [--subnet CIDR]` - Create NAT network
- `vmkit network create-bridge <name> <interface>` - Create bridge network
- `vmkit network delete-network <name>` - Delete network

### Snapshot Management
- `vmkit snapshot <vm_name> <snapshot_name>` - Create a snapshot
- `vmkit snapshots <vm_name>` - List snapshots for a VM
- `vmkit revert <vm_name> <snapshot_name>` - Revert to a snapshot
- `vmkit delete-snapshot <vm_name> <snapshot_name>` - Delete a snapshot

### Cloud-init Utilities  
- `vmkit cloud seed <vm_name>` - Generate cloud-init ISO

### Common Options
- `--memory 4G` - Set RAM (e.g., 4G, 2048M)
- `--cpus 4` - Set vCPU count
- `--graphics none` - Headless mode
- `--no-secure-boot` - Disable Secure Boot
- `--start` - Start after creation

## Examples

### Basic Ubuntu Cloud VM
```bash
# Download Ubuntu cloud image
wget https://cloud-images.ubuntu.com/22.04/current/ubuntu-22.04-server-cloudimg-amd64.img

# Create and start VM with SSH key auth
vmkit create testvm ubuntu-22.04-server-cloudimg-amd64.img \
  --memory 2G --cpus 2 --start
```

### Custom Cloud-init Config
```bash
# Create with specific user and packages
vmkit create devvm ubuntu-22.04-server-cloudimg-amd64.img \
  --username developer \
  --packages "docker.io,nginx,git" \
  --start
```

### Headless Server VM
```bash
# Create headless VM (console only)
vmkit create server ubuntu-22.04-server-cloudimg-amd64.img \
  --graphics none --memory 8G --cpus 4 --start

# Connect via console
vmkit console server
```

### Working with Existing Disks
```python
from vmkit import SecureVM, ExistingDisk

# Import existing qcow2 disk
disk = ExistingDisk("/path/to/existing.qcow2")
vm = SecureVM("imported-vm", image=disk)
vm.create().start()
```

### VM Snapshots
```bash
# Create a snapshot while VM is running
vmkit snapshot myvm baseline "Fresh install snapshot"

# Install software, make changes...
# Create another snapshot
vmkit snapshot myvm dev-ready "Development environment configured"

# List all snapshots
vmkit snapshots myvm

# Revert to previous state
vmkit revert myvm baseline

# Delete old snapshots
vmkit delete-snapshot myvm dev-ready
```

```python
# Python API for snapshots
from vmkit import SecureVM

vm = SecureVM("myvm")

# Create snapshot
vm.create_snapshot("before-update", "Before system update")

# List snapshots
for snap in vm.list_snapshots():
    print(f"{snap['name']}: {snap['creation_time']}")

# Revert if needed
vm.revert_snapshot("before-update")
```

## Architecture

VMKit consists of several key components:

- **SecureVM** - Main VM class with OVMF Secure Boot support
- **Image Classes** - CloudImage, ISOImage, ExistingDisk abstractions  
- **CloudInitConfig** - NoCloud seed generation
- **CLI** - Click-based command interface

### Secure Boot Support

VMKit automatically:
- Detects OVMF firmware paths (`/usr/share/OVMF/OVMF_CODE_4M.secboot.fd`)
- Creates per-VM NVRAM files with Microsoft keys pre-enrolled
- Configures libvirt domain XML with SMM enabled
- Sets correct file ownership for libvirt-qemu

### Cloud-init Integration

For cloud images, VMKit generates NoCloud seed ISOs with:
- User accounts and SSH keys
- Package installation lists
- Custom scripts and files
- Network configuration

## System Requirements

- Ubuntu 20.04+ or Debian 11+ (other distros may work)
- QEMU/KVM with hardware virtualization support
- libvirt 7.0+
- OVMF firmware package
- Python 3.8+

## Troubleshooting

### Permission Issues
```bash
# Ensure user is in libvirt group
sudo usermod -aG libvirt $USER
newgrp libvirt

# Check libvirtd is running
sudo systemctl status libvirtd
```

### OVMF Not Found
```bash
# Install OVMF package
sudo apt install ovmf

# Check paths exist
ls -la /usr/share/OVMF/
```

### Network Issues
```bash
# Check default network is active
virsh net-list --all
virsh net-start default
virsh net-autostart default
```

### Secure Boot Verification
Inside a VM:
```bash
# Install mokutil
sudo apt install mokutil

# Check Secure Boot status  
mokutil --sb-state
# Should show: SecureBoot enabled
```

## Advanced Features 🆕

### Host Virtualization

Virtualize your current machine to create a backup VM or test environment:

```bash
# Check if your system supports virtualization
vmkit host info

# Capture current host state (without disk image)
vmkit host capture myhost-backup --dry-run  # Preview what will be captured
vmkit host capture myhost-backup  # Actually capture

# Capture with disk image (WARNING: Large and slow!)
vmkit host capture myhost-backup --capture-disk

# Create a VM from captured host state
vmkit host virtualize myhost-vm \
  --capture-dir /tmp/vmkit-host-*/  \
  --disk-image /path/to/boot_disk.qcow2 \
  --start
```

Python API:
```python
from vmkit import HostCapture, VirtualizedHost

# Capture host system
capture = HostCapture()
summary = capture.full_capture(include_disk=False)  # Just metadata

# Create a VM from host state (you'd need to provide disk image separately)
vm = VirtualizedHost(
    name="my-host-vm",
    host_capture=capture,
    disk_image_path="/path/to/disk.qcow2"
)

vm.create_with_host_config().start()
```

### Storage Repository Management

Manage storage more intuitively than raw libvirt pools:

```bash
# Create a storage repository
vmkit storage create-repo vm-storage /var/lib/vmkit/storage

# List all repositories
vmkit storage list-repos

# Create volumes in the repository
vmkit storage create-volume vm-storage web-server-disk 20G
vmkit storage create-volume vm-storage db-server-disk 50G --format raw

# List volumes
vmkit storage list-volumes vm-storage

# Use volume when creating VM
vmkit create webvm /var/lib/vmkit/storage/web-server-disk --start
```

Python API:
```python
from vmkit import StorageManager, StorageRepository

# Create and manage storage
manager = StorageManager()
repo = manager.create_repository("my-storage", "/data/vms")

# Create volumes
vol_info = repo.create_volume("test-disk", "10G", "qcow2")
print(f"Created volume at: {vol_info['path']}")

# List all volumes
for vol in repo.list_volumes():
    print(f"{vol['name']}: {vol['capacity']} bytes")
```

### Network Management

Create and manage networks with simple commands:

```bash
# List existing networks
vmkit network list-networks

# Create a NAT network for development
vmkit network create-nat dev-network --subnet 192.168.50.0/24

# Create a bridge network (requires existing bridge interface)
vmkit network create-bridge prod-network br0

# Create an isolated network (no internet access)
vmkit network create-isolated test-network --subnet 10.0.100.0/24

# Delete a network
vmkit network delete-network old-network
```

Python API:
```python
from vmkit import NetworkManager

manager = NetworkManager()

# Create NAT network
net_info = manager.create_nat_network(
    "dev-net", 
    subnet="192.168.100.0/24",
    dhcp_start="192.168.100.10",
    dhcp_end="192.168.100.100"
)

# List networks
for network in manager.list_networks():
    print(f"{network['name']}: {network['mode']} ({network['address']})")

# Set up port forwarding (NAT networks only)
manager.setup_port_forward(
    "dev-net", 
    host_port=8080, 
    guest_ip="192.168.100.50", 
    guest_port=80
)
```

### Advanced VM Configuration

Combine all features for complex setups:

```python
from vmkit import (
    SecureVM, CloudImage, StorageManager, NetworkManager,
    PassthroughManager, find_gpu
)

# Set up storage
storage = StorageManager()
repo = storage.get_default_repository()
vol_info = repo.create_volume("gaming-vm-disk", "100G")

# Set up networking
net_manager = NetworkManager()
gaming_net = net_manager.create_nat_network(
    "gaming-net", 
    "192.168.200.0/24"
)

# Find GPU for passthrough
gpu_device = find_gpu()

# Create high-performance VM
vm = SecureVM(
    name="gaming-vm",
    memory="16G",
    cpus=8,
    image=ExistingDisk(vol_info['path']),
    passthrough_devices=[gpu_device] if gpu_device else [],
    machine="q35",  # Modern machine type
    cpu_mode="host-passthrough"  # Maximum performance
)

vm.create().start()
```

### Integration with Existing virsh Workflows

VMKit is designed to work alongside existing virsh commands:

```bash
# Create VM with VMKit
vmkit create myvm ubuntu-22.04-server-cloudimg-amd64.img

# Use virsh for advanced operations
virsh dumpxml myvm  # View full XML configuration
virsh edit myvm     # Edit VM configuration
virsh domstats myvm # View detailed statistics

# VMKit commands work on virsh-created VMs too
vmkit info myvm
vmkit console myvm
vmkit snapshot myvm backup "Created with VMKit"
```

This hybrid approach gives you the simplicity of VMKit for common operations while preserving access to the full power of libvirt when needed.

## License

MIT License - see LICENSE file for details.
