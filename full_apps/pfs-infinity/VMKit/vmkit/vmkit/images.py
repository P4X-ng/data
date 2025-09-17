"""
Image abstraction for different VM image types
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any
import os


class BaseImage(ABC):
    """Base class for VM images"""
    
    def __init__(self, path: str, format: str = "qcow2"):
        self.path = Path(path).resolve()
        self.format = format
        
        if not self.path.exists():
            raise ValueError(f"Image file does not exist: {self.path}")
    
    @abstractmethod
    def get_disk_xml(self) -> str:
        """Generate libvirt disk XML for this image"""
        pass
    
    def size_gb(self) -> float:
        """Get image size in GB"""
        return self.path.stat().st_size / (1024**3)


class CloudImage(BaseImage):
    """
    Cloud image (e.g., Ubuntu cloud images) with cloud-init support
    
    Automatically attaches cloud-init NoCloud seed ISO if cloud_init_config is provided.
    """
    
    def __init__(
        self, 
        path: str, 
        format: str = "qcow2",
        cloud_init_config: Optional['CloudInitConfig'] = None
    ):
        super().__init__(path, format)
        self.cloud_init_config = cloud_init_config
        self._seed_iso_path = None
    
    def get_disk_xml(self) -> str:
        """Generate disk XML for cloud image + optional cloud-init seed"""
        # Main disk
        disk_xml = f"""
            <disk type='file' device='disk'>
              <driver name='qemu' type='{self.format}'/>
              <source file='{self.path}'/>
              <target dev='vda' bus='virtio'/>
            </disk>
        """
        
        # Cloud-init seed ISO if configured
        if self.cloud_init_config:
            if not self._seed_iso_path:
                # Generate persistent seed ISO path
                vm_name = self.cloud_init_config.instance_id or "vm"
                self._seed_iso_path = f"seed-{vm_name}.iso"
                self.cloud_init_config.create_seed_iso(self._seed_iso_path)
            disk_xml += f"""
            <disk type='file' device='cdrom'>
              <driver name='qemu' type='raw'/>
              <source file='{os.path.abspath(self._seed_iso_path)}'/>
              <target dev='sdb' bus='sata'/>
              <readonly/>
            </disk>
            """
        
        return disk_xml.strip()


class ISOImage(BaseImage):
    """
    Installation ISO image
    
    For traditional OS installation from ISO. Optionally create a target disk.
    """
    
    def __init__(
        self, 
        path: str, 
        target_disk_size: str = "40G",
        target_disk_format: str = "qcow2"
    ):
        super().__init__(path, format="raw")  # ISOs are raw
        self.target_disk_size = target_disk_size
        self.target_disk_format = target_disk_format
        self._target_disk_path = None
    
    def _create_target_disk(self, vm_name: str) -> Path:
        """Create target disk for installation"""
        if self._target_disk_path and self._target_disk_path.exists():
            return self._target_disk_path
        
        # Create disk in /var/lib/libvirt/images by default
        disk_dir = Path("/var/lib/libvirt/images")
        disk_dir.mkdir(parents=True, exist_ok=True)
        
        disk_path = disk_dir / f"{vm_name}.{self.target_disk_format}"
        
        # Use qemu-img to create the disk
        import subprocess
        cmd = [
            "qemu-img", "create", "-f", self.target_disk_format,
            str(disk_path), self.target_disk_size
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            self._target_disk_path = disk_path
            return disk_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create target disk: {e}")
    
    def get_disk_xml(self) -> str:
        """Generate disk XML for target disk + install ISO"""
        # We can't create the target disk without knowing the VM name
        # This is a limitation - we'll need the VM name passed in somehow
        # For now, assume the target disk will be created externally
        
        disk_xml = f"""
            <disk type='file' device='cdrom'>
              <driver name='qemu' type='raw'/>
              <source file='{self.path}'/>
              <target dev='sda' bus='sata'/>
              <readonly/>
            </disk>
        """
        
        # TODO: Add target disk creation logic
        # This needs VM name context which we don't have here
        
        return disk_xml.strip()


class ExistingDisk(BaseImage):
    """
    Existing disk image (qcow2, raw, etc.)
    
    For importing pre-existing VM disks.
    """
    
    def __init__(self, path: str, format: str = "qcow2", bus: str = "virtio"):
        super().__init__(path, format)
        self.bus = bus
    
    def get_disk_xml(self) -> str:
        """Generate disk XML for existing disk"""
        return f"""
            <disk type='file' device='disk'>
              <driver name='qemu' type='{self.format}'/>
              <source file='{self.path}'/>
              <target dev='vda' bus='{self.bus}'/>
            </disk>
        """.strip()


# Convenience functions for common cases

def detect_image_type(path: str) -> BaseImage:
    """Auto-detect image type based on file extension and content"""
    path_obj = Path(path)
    
    if not path_obj.exists():
        raise ValueError(f"Image file does not exist: {path}")
    
    suffix = path_obj.suffix.lower()
    
    if suffix == '.iso':
        return ISOImage(path)
    elif suffix in ['.qcow2', '.img']:
        # Try to detect if it's a cloud image by filename patterns
        name_lower = path_obj.name.lower()
        if any(pattern in name_lower for pattern in ['cloud', 'cloudimg']):
            return CloudImage(path)
        else:
            return ExistingDisk(path)
    else:
        # Default to existing disk
        return ExistingDisk(path, format="raw" if suffix == '.raw' else "qcow2")


def ubuntu_cloud_image(version: str = "22.04", arch: str = "amd64") -> str:
    """Get path to Ubuntu cloud image (assumes standard locations)"""
    # Common locations where Ubuntu cloud images might be stored
    search_paths = [
        f"/var/lib/libvirt/images/ubuntu-{version}-server-cloudimg-{arch}.img",
        f"/var/lib/libvirt/images/ubuntu-{version}-cloudimg-{arch}.img",
        f"/home/{os.environ.get('USER', 'user')}/images/ubuntu-{version}-server-cloudimg-{arch}.img",
        f"./ubuntu-{version}-server-cloudimg-{arch}.img",
    ]
    
    for path in search_paths:
        if Path(path).exists():
            return path
    
    raise FileNotFoundError(
        f"Ubuntu {version} cloud image not found. Download with:\n"
        f"wget https://cloud-images.ubuntu.com/{version}/current/"
        f"ubuntu-{version}-server-cloudimg-{arch}.img"
    )
