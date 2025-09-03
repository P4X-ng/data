"""
Cloud-init NoCloud seed generation
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import yaml
import crypt
import secrets


class CloudInitConfig:
    """
    Cloud-init configuration with NoCloud seed ISO generation
    
    Handles user creation, SSH keys, passwords, and basic system setup.
    """
    
    def __init__(
        self,
        instance_id: Optional[str] = None,
        hostname: Optional[str] = None,
        username: str = "ubuntu",
        ssh_keys: Optional[List[str]] = None,
        password: Optional[str] = None,
        password_auth: bool = False,
        sudo: bool = True,
        packages: Optional[List[str]] = None,
        runcmd: Optional[List[Union[str, List[str]]]] = None,
        write_files: Optional[List[Dict[str, Any]]] = None,
        **cloud_config_extras
    ):
        self.instance_id = instance_id
        self.hostname = hostname
        self.username = username
        self.ssh_keys = ssh_keys or []
        self.password = password
        self.password_auth = password_auth
        self.sudo = sudo
        self.packages = packages or []
        self.runcmd = runcmd or []
        self.write_files = write_files or []
        self.cloud_config_extras = cloud_config_extras
        
        # Auto-load SSH keys if none provided
        if not self.ssh_keys:
            self.ssh_keys = self._auto_load_ssh_keys()
    
    def _auto_load_ssh_keys(self) -> List[str]:
        """Auto-load SSH public keys from standard locations"""
        keys = []
        ssh_dir = Path.home() / ".ssh"
        
        for key_file in ["id_ed25519.pub", "id_rsa.pub", "id_ecdsa.pub"]:
            key_path = ssh_dir / key_file
            if key_path.exists():
                try:
                    keys.append(key_path.read_text().strip())
                    break  # Use first found key
                except Exception:
                    continue
        
        return keys
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-512 with random salt"""
        # Generate a random salt
        salt = crypt.mksalt(crypt.METHOD_SHA512)
        return crypt.crypt(password, salt)
    
    def generate_user_data(self) -> str:
        """Generate cloud-init user-data YAML"""
        config = {
            "#cloud-config": None,  # Marker comment
        }
        
        # User configuration
        users = []
        user_config = {
            "name": self.username,
            "groups": ["sudo"] if self.sudo else [],
            "sudo": "ALL=(ALL) NOPASSWD:ALL" if self.sudo else None,
            "lock_passwd": not self.password_auth,
        }
        
        if self.ssh_keys:
            user_config["ssh_authorized_keys"] = self.ssh_keys
        
        if self.password:
            # Check if password is already hashed (starts with $)
            if self.password.startswith('$'):
                # Already hashed, use passwd field
                user_config['passwd'] = self.password
            else:
                # Hash the plain text password using SHA-512
                user_config['passwd'] = self._hash_password(self.password)
        
        # Remove None values
        user_config = {k: v for k, v in user_config.items() if v is not None}
        users.append(user_config)
        config["users"] = users
        
        # SSH configuration
        config["ssh_pwauth"] = self.password_auth
        
        # Package installation
        if self.packages:
            config["packages"] = self.packages
        
        # Commands to run
        if self.runcmd:
            config["runcmd"] = self.runcmd
        
        # Files to write
        if self.write_files:
            config["write_files"] = self.write_files
        
        # Package update
        config["package_update"] = True
        
        # Add any extra cloud-config options
        config.update(self.cloud_config_extras)
        
        # Convert to YAML
        yaml_data = yaml.dump(config, default_flow_style=False, sort_keys=False)
        
        # Fix the header comment
        yaml_data = yaml_data.replace("'#cloud-config': null\n", "", 1)
        yaml_data = "#cloud-config\n" + yaml_data
        
        return yaml_data
    
    def generate_meta_data(self) -> str:
        """Generate cloud-init meta-data YAML"""
        config = {}
        
        if self.instance_id:
            config["instance-id"] = self.instance_id
        
        if self.hostname:
            config["local-hostname"] = self.hostname
        
        return yaml.dump(config, default_flow_style=False)
    
    def create_seed_iso(self, output_path: Optional[str] = None) -> str:
        """
        Create NoCloud seed ISO with user-data and meta-data
        
        Returns path to created ISO file.
        """
        if output_path is None:
            # Create temporary file
            fd, output_path = tempfile.mkstemp(suffix=".iso", prefix="seed-")
            os.close(fd)
        
        # Generate cloud-init data
        user_data = self.generate_user_data()
        meta_data = self.generate_meta_data()
        
        # Create temporary directory for files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Write user-data and meta-data
            (tmpdir_path / "user-data").write_text(user_data)
            (tmpdir_path / "meta-data").write_text(meta_data)
            
            # Create ISO using genisoimage/xorrisofs/cloud-localds
            self._create_iso(tmpdir_path, output_path)
        
        return output_path
    
    def _create_iso(self, source_dir: Path, output_path: str):
        """Create ISO from source directory using available tools"""
        
        # Try cloud-localds first (most compatible)
        if self._command_exists("cloud-localds"):
            cmd = [
                "cloud-localds", output_path,
                str(source_dir / "user-data"),
                str(source_dir / "meta-data")
            ]
            subprocess.run(cmd, check=True)
            return
        
        # Try genisoimage
        if self._command_exists("genisoimage"):
            cmd = [
                "genisoimage", "-output", output_path,
                "-volid", "cidata", "-joliet", "-rock",
                str(source_dir)
            ]
            subprocess.run(cmd, check=True)
            return
        
        # Try xorrisofs
        if self._command_exists("xorrisofs"):
            cmd = [
                "xorrisofs", "-output", output_path,
                "-volid", "cidata", "-joliet", "-rock",
                str(source_dir)
            ]
            subprocess.run(cmd, check=True)
            return
        
        # Fallback to Python pycdlib if available
        try:
            self._create_iso_pycdlib(source_dir, output_path)
            return
        except ImportError:
            pass
        
        raise RuntimeError(
            "No ISO creation tool found. Install one of: "
            "cloud-image-utils, genisoimage, xorriso, or python3-pycdlib"
        )
    
    def _create_iso_pycdlib(self, source_dir: Path, output_path: str):
        """Create ISO using pycdlib (pure Python)"""
        try:
            from pycdlib import PyCdlib
        except ImportError:
            raise ImportError("pycdlib not available. Install with: pip install pycdlib")
        
        iso = PyCdlib()
        iso.new(joliet=3, vol_ident="cidata")
        
        # Add files
        for file_path in source_dir.iterdir():
            if file_path.is_file():
                iso.add_file(
                    str(file_path),
                    joliet_path=f"/{file_path.name}"
                )
        
        iso.write(output_path)
        iso.close()
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run([command, "--help"], 
                         capture_output=True, 
                         check=False)
            return True
        except FileNotFoundError:
            return False


# Convenience functions

def quick_config(
    vm_name: str,
    username: str = "ubuntu", 
    password: Optional[str] = None,
    ssh_keys: Optional[List[str]] = None,
    packages: Optional[List[str]] = None
) -> CloudInitConfig:
    """Create a quick cloud-init config with sensible defaults"""
    return CloudInitConfig(
        instance_id=vm_name,
        hostname=vm_name,
        username=username,
        password=password,
        password_auth=password is not None,
        ssh_keys=ssh_keys,
        packages=packages or ["curl", "wget", "vim", "htop"]
    )


def ssh_only_config(vm_name: str, username: str = "ubuntu") -> CloudInitConfig:
    """Create SSH-only config (no password auth)"""
    return CloudInitConfig(
        instance_id=vm_name,
        hostname=vm_name,
        username=username,
        password_auth=False,
        packages=["curl", "wget", "vim", "htop"]
    )


def hash_password(password: str) -> str:
    """Hash a password using SHA-512 with random salt
    
    This can be used to pre-hash passwords before passing them to CloudInitConfig.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password string that can be used in passwd field
        
    Example:
        hashed = hash_password("mypassword")
        config = CloudInitConfig(password=hashed)
    """
    salt = crypt.mksalt(crypt.METHOD_SHA512)
    return crypt.crypt(password, salt)
