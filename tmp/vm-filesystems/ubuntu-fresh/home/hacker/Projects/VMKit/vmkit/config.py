"""
Configuration management for VMKit
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class VMTemplate:
    """VM template configuration"""
    memory: str = "4G"
    cpus: int = 4
    graphics: str = "spice"
    secure_boot: bool = True
    machine: str = "q35"
    cpu_mode: str = "host-passthrough"
    network: str = "default"
    storage_pool: str = "default"


@dataclass
class CloudInitDefaults:
    """Default cloud-init settings"""
    username: str = "ubuntu"
    password_auth: bool = False
    sudo: bool = True
    packages: list = field(default_factory=lambda: ["curl", "wget", "vim", "htop"])
    ssh_key_paths: list = field(default_factory=lambda: [
        "~/.ssh/id_ed25519.pub",
        "~/.ssh/id_rsa.pub",
        "~/.ssh/id_ecdsa.pub"
    ])


@dataclass
class OVMFPaths:
    """OVMF firmware paths"""
    code_secure: str = "/usr/share/OVMF/OVMF_CODE_4M.secboot.fd"
    vars_ms: str = "/usr/share/OVMF/OVMF_VARS_4M.ms.fd"
    vars_blank: str = "/usr/share/OVMF/OVMF_VARS_4M.fd"
    nvram_dir: str = "/var/lib/libvirt/qemu/nvram"


@dataclass
class LibvirtSettings:
    """Libvirt connection and storage settings"""
    uri: str = "qemu:///system"
    default_network: str = "default"
    default_pool: str = "default"
    images_dir: str = "/var/lib/libvirt/images"


@dataclass
class VMKitConfig:
    """Main VMKit configuration"""
    templates: Dict[str, VMTemplate] = field(default_factory=dict)
    cloudinit: CloudInitDefaults = field(default_factory=CloudInitDefaults)
    ovmf: OVMFPaths = field(default_factory=OVMFPaths)
    libvirt: LibvirtSettings = field(default_factory=LibvirtSettings)


class ConfigManager:
    """Manages VMKit configuration loading and saving"""
    
    DEFAULT_CONFIG_PATHS = [
        "~/.vmkit.yaml",
        "~/.config/vmkit/config.yaml",
        "/etc/vmkit/config.yaml",
        "./vmkit.yaml"
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = VMKitConfig()
        
        # Initialize default templates
        self._init_default_templates()
        
        # Load configuration
        self.load()
    
    def _init_default_templates(self):
        """Initialize default VM templates"""
        self.config.templates = {
            "small": VMTemplate(memory="2G", cpus=2),
            "medium": VMTemplate(memory="4G", cpus=4),
            "large": VMTemplate(memory="8G", cpus=8),
            "xlarge": VMTemplate(memory="16G", cpus=16),
            "server": VMTemplate(
                memory="4G", cpus=4, graphics="none", 
                machine="q35", cpu_mode="host-passthrough"
            ),
            "desktop": VMTemplate(
                memory="8G", cpus=4, graphics="spice",
                machine="q35", cpu_mode="host-passthrough"
            ),
            "secure": VMTemplate(
                memory="4G", cpus=4, secure_boot=True,
                graphics="none", machine="q35"
            )
        }
    
    def find_config_file(self) -> Optional[Path]:
        """Find first existing config file"""
        if self.config_path:
            path = Path(self.config_path).expanduser()
            if path.exists():
                return path
            return None
        
        for path_str in self.DEFAULT_CONFIG_PATHS:
            path = Path(path_str).expanduser()
            if path.exists():
                return path
        
        return None
    
    def load(self) -> bool:
        """Load configuration from file"""
        config_file = self.find_config_file()
        if not config_file:
            return False
        
        try:
            with open(config_file, 'r') as f:
                data = yaml.safe_load(f)
            
            if not data:
                return False
            
            # Load templates
            if 'templates' in data:
                for name, template_data in data['templates'].items():
                    template = VMTemplate(**template_data)
                    self.config.templates[name] = template
            
            # Load cloud-init defaults
            if 'cloudinit' in data:
                cloudinit_data = data['cloudinit']
                self.config.cloudinit = CloudInitDefaults(**cloudinit_data)
            
            # Load OVMF paths
            if 'ovmf' in data:
                ovmf_data = data['ovmf']
                self.config.ovmf = OVMFPaths(**ovmf_data)
            
            # Load libvirt settings
            if 'libvirt' in data:
                libvirt_data = data['libvirt']
                self.config.libvirt = LibvirtSettings(**libvirt_data)
            
            return True
            
        except Exception as e:
            print(f"Warning: Failed to load config from {config_file}: {e}")
            return False
    
    def save(self, path: Optional[str] = None) -> bool:
        """Save configuration to file"""
        if path:
            config_file = Path(path).expanduser()
        else:
            config_file = Path("~/.vmkit.yaml").expanduser()
        
        # Ensure directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = {
                'templates': {
                    name: {
                        'memory': t.memory,
                        'cpus': t.cpus,
                        'graphics': t.graphics,
                        'secure_boot': t.secure_boot,
                        'machine': t.machine,
                        'cpu_mode': t.cpu_mode,
                        'network': t.network,
                        'storage_pool': t.storage_pool,
                    }
                    for name, t in self.config.templates.items()
                },
                'cloudinit': {
                    'username': self.config.cloudinit.username,
                    'password_auth': self.config.cloudinit.password_auth,
                    'sudo': self.config.cloudinit.sudo,
                    'packages': self.config.cloudinit.packages,
                    'ssh_key_paths': self.config.cloudinit.ssh_key_paths,
                },
                'ovmf': {
                    'code_secure': self.config.ovmf.code_secure,
                    'vars_ms': self.config.ovmf.vars_ms,
                    'vars_blank': self.config.ovmf.vars_blank,
                    'nvram_dir': self.config.ovmf.nvram_dir,
                },
                'libvirt': {
                    'uri': self.config.libvirt.uri,
                    'default_network': self.config.libvirt.default_network,
                    'default_pool': self.config.libvirt.default_pool,
                    'images_dir': self.config.libvirt.images_dir,
                }
            }
            
            with open(config_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
            return True
            
        except Exception as e:
            print(f"Error: Failed to save config to {config_file}: {e}")
            return False
    
    def get_template(self, name: str) -> Optional[VMTemplate]:
        """Get template by name"""
        return self.config.templates.get(name)
    
    def list_templates(self) -> Dict[str, VMTemplate]:
        """List all available templates"""
        return self.config.templates.copy()
    
    def auto_detect_ovmf(self) -> bool:
        """Auto-detect OVMF paths and update config"""
        search_paths = {
            'code_secure': [
                "/usr/share/OVMF/OVMF_CODE_4M.secboot.fd",
                "/usr/share/OVMF/OVMF_CODE.secboot.fd",
                "/usr/share/edk2-ovmf/x64/OVMF_CODE.secboot.fd",
            ],
            'vars_ms': [
                "/usr/share/OVMF/OVMF_VARS_4M.ms.fd",
                "/usr/share/OVMF/OVMF_VARS.ms.fd", 
                "/usr/share/edk2-ovmf/x64/OVMF_VARS.ms.fd",
            ],
            'vars_blank': [
                "/usr/share/OVMF/OVMF_VARS_4M.fd",
                "/usr/share/OVMF/OVMF_VARS.fd",
                "/usr/share/edk2-ovmf/x64/OVMF_VARS.fd",
            ]
        }
        
        updated = False
        for key, paths in search_paths.items():
            for path in paths:
                if os.path.exists(path):
                    setattr(self.config.ovmf, key, path)
                    updated = True
                    break
        
        return updated
    
    def auto_detect_ssh_keys(self) -> list:
        """Auto-detect available SSH public keys"""
        found_keys = []
        ssh_dir = Path.home() / ".ssh"
        
        for key_path in self.config.cloudinit.ssh_key_paths:
            full_path = Path(key_path).expanduser()
            if full_path.exists():
                try:
                    key_content = full_path.read_text().strip()
                    found_keys.append(key_content)
                except Exception:
                    continue
        
        return found_keys


# Global config manager instance
_config_manager = None

def get_config() -> ConfigManager:
    """Get global config manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def load_config(config_path: Optional[str] = None) -> ConfigManager:
    """Load configuration from specific path"""
    global _config_manager
    _config_manager = ConfigManager(config_path)
    return _config_manager
