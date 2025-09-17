"""
Core VM management with Secure Boot support
"""

import libvirt
import os
import shutil
import stat
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
import textwrap
import re


class VMError(Exception):
    """Base exception for VM operations"""
    pass


class SecureVM:
    """
    A Secure Boot-enabled VM with sensible defaults
    
    Automatically configures UEFI + Secure Boot using OVMF, handles
    per-VM NVRAM management, and provides simple lifecycle operations.
    """
    
    # Auto-detect OVMF paths (Ubuntu standard locations)
    OVMF_PATHS = {
        'code': '/usr/share/OVMF/OVMF_CODE_4M.secboot.fd',
        'vars_ms': '/usr/share/OVMF/OVMF_VARS_4M.ms.fd',  # Microsoft keys
        'vars_blank': '/usr/share/OVMF/OVMF_VARS_4M.fd',  # No keys
    }
    
    NVRAM_DIR = Path('/var/lib/libvirt/qemu/nvram')
    DEFAULT_POOL = 'default'
    DEFAULT_NETWORK = 'default'
    
    def __init__(
        self,
        name: str,
        memory: Union[str, int] = "4G",
        cpus: int = 4,
        image: Optional['BaseImage'] = None,
        secure_boot: bool = True,
        machine: str = "q35",
        cpu_mode: str = "host-passthrough",
        graphics: str = "spice",  # or "none" for headless
        passthrough_devices: Optional[List['PCIDevice']] = None,
        **kwargs
    ):
        self.name = name
        self.memory_mb = self._parse_memory(memory)
        self.cpus = cpus
        self.image = image
        self.secure_boot = secure_boot
        self.machine = machine
        self.cpu_mode = cpu_mode
        self.graphics = graphics
        self.passthrough_devices = passthrough_devices or []
        
        # Auto-detect OVMF paths with error handling
        try:
            self.ovmf_code = self._find_ovmf_code()
            self.ovmf_vars_template = self._find_ovmf_vars()
        except VMError as e:
            # Defer OVMF validation until VM creation
            self.ovmf_code = None
            self.ovmf_vars_template = None
        self.nvram_path = self.NVRAM_DIR / f"{name}_VARS.fd"
        
        # Libvirt connection (lazy)
        self._conn = None
        self._domain = None
    
    @property
    def conn(self) -> libvirt.virConnect:
        """Lazy libvirt connection"""
        if self._conn is None:
            try:
                self._conn = libvirt.open("qemu:///system")
                if self._conn is None:
                    raise VMError("Failed to connect to libvirt: connection returned None")
            except libvirt.libvirtError as e:
                raise VMError(f"Failed to connect to libvirt: {e}")
        return self._conn
    
    @property
    def domain(self) -> Optional[libvirt.virDomain]:
        """Get domain object if it exists"""
        if self._domain is None:
            try:
                self._domain = self.conn.lookupByName(self.name)
            except libvirt.libvirtError:
                return None
        return self._domain
    
    def _parse_memory(self, memory: Union[str, int]) -> int:
        """Parse memory string like '4G', '2048M' to MB"""
        if isinstance(memory, int):
            return memory
        
        memory = memory.upper().strip()
        if memory.endswith('G'):
            return int(memory[:-1]) * 1024
        elif memory.endswith('M'):
            return int(memory[:-1])
        else:
            return int(memory)  # Assume MB
    
    def _find_ovmf_code(self) -> str:
        """Find OVMF CODE file"""
        if os.path.exists(self.OVMF_PATHS['code']):
            return self.OVMF_PATHS['code']
        raise VMError(f"OVMF CODE not found at {self.OVMF_PATHS['code']}. Install ovmf package.")
    
    def _find_ovmf_vars(self) -> str:
        """Find OVMF VARS template (prefer Microsoft keys for Secure Boot)"""
        if self.secure_boot and os.path.exists(self.OVMF_PATHS['vars_ms']):
            return self.OVMF_PATHS['vars_ms']
        elif os.path.exists(self.OVMF_PATHS['vars_blank']):
            return self.OVMF_PATHS['vars_blank']
        raise VMError(f"OVMF VARS not found. Install ovmf package.")
    
    def _setup_nvram(self):
        """Create per-VM NVRAM file from template"""
        if self.nvram_path.exists():
            return  # Already exists
        
        # Ensure NVRAM directory exists
        self.NVRAM_DIR.mkdir(parents=True, exist_ok=True)
        
        # Copy template with correct ownership
        shutil.copy2(self.ovmf_vars_template, self.nvram_path)
        
        # Set libvirt ownership (libvirt-qemu:libvirt-qemu or libvirt-qemu:kvm)
        try:
            import pwd, grp
            uid = pwd.getpwnam('libvirt-qemu').pw_uid
            try:
                gid = grp.getgrnam('libvirt-qemu').gr_gid
            except KeyError:
                gid = grp.getgrnam('kvm').gr_gid
            
            os.chown(self.nvram_path, uid, gid)
            os.chmod(self.nvram_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        except (KeyError, PermissionError) as e:
            raise VMError(f"Failed to set NVRAM ownership: {e}. Run as root or check libvirt setup.")
    
    def _generate_domain_xml(self) -> str:
        """Generate libvirt domain XML"""
        if not self.image:
            raise VMError("No image specified. Use vm.image = CloudImage(...) or ISOImage(...)")
        
        # Graphics setup
        if self.graphics == "none":
            graphics_xml = "<!-- No graphics -->"
            console_xml = "<console type='pty'><target type='serial' port='0'/></console>"
        else:
            graphics_xml = f"<graphics type='{self.graphics}'/>"
            console_xml = "<console type='pty'/>"
        
        # OVMF/Secure Boot setup
        loader_xml = f"""
        <loader readonly='yes' type='pflash'>{self.ovmf_code}</loader>
        <nvram>{self.nvram_path}</nvram>
        """
        
        # Get disk XML from image
        disk_xml = self.image.get_disk_xml()
        
        # Generate passthrough device XML
        passthrough_xml = self._generate_passthrough_xml()
        
        # For passthrough VMs, we may need additional features
        features_parts = ["<acpi/>", "<apic/>", "<smm state='on'/>"]
        if self.passthrough_devices:
            # Enable IOMMU for passthrough
            features_parts.append("<ioapic driver='kvm'/>")
        features_xml = "".join(features_parts)
        
        xml = f"""
        <domain type='kvm'>
          <name>{self.name}</name>
          <memory unit='MiB'>{self.memory_mb}</memory>
          <vcpu>{self.cpus}</vcpu>
          <os>
            <type arch='x86_64' machine='{self.machine}'>hvm</type>
            {loader_xml.strip()}
          </os>
          <features>
            {features_xml}
          </features>
          <cpu mode='{self.cpu_mode}'>
            <topology sockets='1' dies='1' cores='{self.cpus}' threads='1'/>
          </cpu>
          <devices>
            {disk_xml}
            <interface type='network'>
              <source network='{self.DEFAULT_NETWORK}'/>
              <model type='virtio'/>
            </interface>
            {graphics_xml}
            {console_xml}
            <input type='tablet' bus='usb'/>
            <video><model type='virtio'/></video>
            {passthrough_xml}
          </devices>
        </domain>
        """
        
        return textwrap.dedent(xml).strip()
    
    def _generate_passthrough_xml(self) -> str:
        """Generate XML for passthrough devices"""
        if not self.passthrough_devices:
            return "<!-- No passthrough devices -->"
        
        from .passthrough import PassthroughManager
        manager = PassthroughManager()
        
        hostdev_xml = []
        for device in self.passthrough_devices:
            try:
                xml = manager.generate_hostdev_xml(device)
                hostdev_xml.append(xml)
            except Exception as e:
                raise VMError(f"Failed to generate XML for device {device.pci_id}: {e}")
        
        return "\n".join(hostdev_xml)
    
    def add_passthrough_device(self, device: 'PCIDevice'):
        """Add a passthrough device to the VM"""
        if device not in self.passthrough_devices:
            self.passthrough_devices.append(device)
    
    def remove_passthrough_device(self, device: 'PCIDevice'):
        """Remove a passthrough device from the VM"""
        if device in self.passthrough_devices:
            self.passthrough_devices.remove(device)
    
    def validate_passthrough(self) -> tuple[bool, list[str]]:
        """Validate passthrough device configuration"""
        if not self.passthrough_devices:
            return True, []
        
        from .passthrough import PassthroughManager
        manager = PassthroughManager()
        
        # Check system readiness
        ready, issues = manager.validate_passthrough_readiness()
        
        # Check device-specific issues
        for device in self.passthrough_devices:
            if device.iommu_group is None:
                issues.append(f"Device {device.pci_id} has no IOMMU group")
            
            if not device.bound_to_vfio:
                issues.append(f"Device {device.pci_id} not bound to vfio-pci driver")
        
        return len(issues) == 0, issues
    
    def create(self) -> 'SecureVM':
        """Create (define) the VM"""
        if self.domain:
            raise VMError(f"VM '{self.name}' already exists")
        
        # Setup NVRAM
        self._setup_nvram()
        
        # Generate and define domain
        xml = self._generate_domain_xml()
        
        try:
            self._domain = self.conn.defineXML(xml)
            return self
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to create VM: {e}")
    
    def start(self) -> 'SecureVM':
        """Start the VM"""
        domain = self.domain
        if not domain:
            raise VMError(f"VM '{self.name}' does not exist. Call create() first.")
        
        if domain.isActive():
            return self  # Already running
        
        try:
            domain.create()
            return self
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to start VM: {e}")
    
    def stop(self, force: bool = False) -> 'SecureVM':
        """Stop the VM (graceful or forced)"""
        domain = self.domain
        if not domain or not domain.isActive():
            return self  # Already stopped
        
        try:
            if force:
                domain.destroy()  # Force stop
            else:
                domain.shutdown()  # ACPI shutdown
            return self
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to stop VM: {e}")
    
    def destroy(self) -> 'SecureVM':
        """Destroy (undefine) the VM and clean up NVRAM"""
        domain = self.domain
        if domain:
            if domain.isActive():
                domain.destroy()
            
            # For NVRAM domains, we need to undefine with NVRAM flag
            try:
                domain.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
            except libvirt.libvirtError:
                # Fallback to regular undefine
                domain.undefine()
        
        # Clean up NVRAM (redundant but safe)
        if self.nvram_path.exists():
            self.nvram_path.unlink()
        
        self._domain = None
        return self
    
    def is_active(self) -> bool:
        """Check if VM is running"""
        domain = self.domain
        return domain.isActive() if domain else False
    
    def is_defined(self) -> bool:
        """Check if VM is defined"""
        return self.domain is not None
    
    def console(self):
        """Connect to VM console (spawns virsh console)"""
        if not self.domain:
            raise VMError(f"VM '{self.name}' does not exist")
        
        import subprocess
        subprocess.run(["virsh", "console", self.name], check=False)
    
    def info(self) -> Dict[str, Any]:
        """Get VM information"""
        domain = self.domain
        if not domain:
            return {"name": self.name, "state": "undefined"}
        
        # Use class-level state names
        if not hasattr(self.__class__, '_state_names'):
            self.__class__._state_names = {
                libvirt.VIR_DOMAIN_NOSTATE: "no state",
                libvirt.VIR_DOMAIN_RUNNING: "running",
                libvirt.VIR_DOMAIN_BLOCKED: "blocked",
                libvirt.VIR_DOMAIN_PAUSED: "paused",
                libvirt.VIR_DOMAIN_SHUTDOWN: "shutdown",
                libvirt.VIR_DOMAIN_SHUTOFF: "shutoff",
                libvirt.VIR_DOMAIN_CRASHED: "crashed",
            }
        state_names = self._state_names
        
        state, reason = domain.state()
        info = domain.info()
        
        return {
            "name": self.name,
            "state": state_names.get(state, f"unknown ({state})"),
            "memory_mb": info[1] // 1024,
            "vcpus": info[3],
            "cpu_time": info[4],
            "secure_boot": self.secure_boot,
            "nvram": str(self.nvram_path),
        }
    
    def create_snapshot(self, name: str, description: str = "") -> 'SecureVM':
        """Create a snapshot of the VM
        
        Args:
            name: Name for the snapshot
            description: Optional description for the snapshot
            
        Returns:
            Self for method chaining
            
        Raises:
            VMError: If snapshot creation fails
        """
        domain = self.domain
        if not domain:
            raise VMError(f"VM '{self.name}' does not exist")
        
        try:
            # Create snapshot using libvirt API with XML escaping
            import xml.sax.saxutils as xml_escape
            escaped_name = xml_escape.escape(name)
            escaped_desc = xml_escape.escape(description)
            
            domain.snapshotCreateXML(
                f"""<domainsnapshot>
                    <name>{escaped_name}</name>
                    <description>{escaped_desc}</description>
                </domainsnapshot>"""
            )
            return self
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to create snapshot '{name}': {e}")
    
    def list_snapshots(self) -> List[Dict[str, str]]:
        """List all snapshots for this VM
        
        Returns:
            List of dictionaries containing snapshot information
        """
        domain = self.domain
        if not domain:
            return []
        
        try:
            snapshots = domain.listAllSnapshots()
            snapshot_list = []
            
            for snap in snapshots:
                snap_info = {
                    "name": snap.getName(),
                    "state": "unknown",
                    "creation_time": "unknown"
                }
                
                try:
                    # Get snapshot XML to extract more info
                    xml_desc = snap.getXMLDesc()
                    # Use proper XML parsing
                    import xml.etree.ElementTree as ET
                    try:
                        root = ET.fromstring(xml_desc)
                        state_elem = root.find('state')
                        if state_elem is not None:
                            snap_info["state"] = state_elem.text
                        
                        time_elem = root.find('creationTime')
                        if time_elem is not None:
                            timestamp = int(time_elem.text)
                            import datetime
                            dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
                            snap_info["creation_time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except ET.ParseError:
                        pass  # Use defaults if XML parsing fails
                        
                except (ValueError, ET.ParseError, OSError):
                    # If we can't parse details, use defaults
                    pass
                
                snapshot_list.append(snap_info)
            
            return snapshot_list
            
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to list snapshots: {e}")
    
    def revert_snapshot(self, name: str) -> 'SecureVM':
        """Revert VM to a specific snapshot
        
        Args:
            name: Name of the snapshot to revert to
            
        Returns:
            Self for method chaining
            
        Raises:
            VMError: If snapshot revert fails
        """
        domain = self.domain
        if not domain:
            raise VMError(f"VM '{self.name}' does not exist")
        
        try:
            # Find the snapshot
            snapshot = domain.snapshotLookupByName(name)
            # Revert to snapshot
            domain.revertToSnapshot(snapshot)
            return self
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to revert to snapshot '{name}': {e}")
    
    def delete_snapshot(self, name: str) -> 'SecureVM':
        """Delete a specific snapshot
        
        Args:
            name: Name of the snapshot to delete
            
        Returns:
            Self for method chaining
            
        Raises:
            VMError: If snapshot deletion fails
        """
        domain = self.domain
        if not domain:
            raise VMError(f"VM '{self.name}' does not exist")
        
        try:
            # Find and delete the snapshot
            snapshot = domain.snapshotLookupByName(name)
            snapshot.delete(libvirt.VIR_DOMAIN_SNAPSHOT_DELETE_METADATA_ONLY)
            return self
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to delete snapshot '{name}': {e}")
    
    def __repr__(self):
        state = "undefined"
        if self.domain:
            state = "running" if self.is_active() else "defined"
        return f"SecureVM(name='{self.name}', state='{state}', memory={self.memory_mb}MB, cpus={self.cpus})"
