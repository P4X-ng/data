#!/usr/bin/env python3
"""
Storage repository management

Provides intuitive storage management for VM disks and volumes,
wrapping libvirt storage pools with a more user-friendly interface.
"""

import json
import libvirt
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging

from .core import VMError

logger = logging.getLogger(__name__)


class StorageRepository:
    """
    A storage repository for VM disks and images
    
    This wraps libvirt storage pools but uses more intuitive terminology.
    A repository is simply a managed directory for storing VM-related files.
    """
    
    def __init__(self, name: str, path: Optional[Union[str, Path]] = None, 
                 pool_type: str = "dir"):
        """
        Initialize a storage repository
        
        Args:
            name: Repository name
            path: Directory path for the repository (auto-created if needed)
            pool_type: Libvirt pool type (usually "dir" for directory)
        """
        self.name = name
        self.pool_type = pool_type
        
        if path:
            self.path = Path(path).resolve()
        else:
            # Default to /var/lib/vmkit/repos/<name>
            self.path = Path("/var/lib/vmkit/repos") / name
        
        self._conn = None
        self._pool = None
    
    @property
    def conn(self) -> libvirt.virConnect:
        """Lazy libvirt connection"""
        if self._conn is None:
            try:
                self._conn = libvirt.open("qemu:///system")
            except libvirt.libvirtError as e:
                raise VMError(f"Failed to connect to libvirt: {e}")
        return self._conn
    
    @property
    def pool(self) -> Optional[libvirt.virStoragePool]:
        """Get storage pool object if it exists"""
        if self._pool is None:
            try:
                self._pool = self.conn.storagePoolLookupByName(self.name)
            except libvirt.libvirtError:
                return None
        return self._pool
    
    def exists(self) -> bool:
        """Check if the repository exists"""
        return self.pool is not None
    
    def is_active(self) -> bool:
        """Check if repository is active"""
        pool = self.pool
        return pool.isActive() if pool else False
    
    def create(self, auto_start: bool = True) -> 'StorageRepository':
        """
        Create the storage repository
        
        Args:
            auto_start: Whether to automatically start the repository after creation
        """
        if self.exists():
            raise VMError(f"Repository '{self.name}' already exists")
        
        # Ensure directory exists
        self.path.mkdir(parents=True, exist_ok=True)
        
        # Generate libvirt pool XML
        xml = f"""
        <pool type='{self.pool_type}'>
          <name>{self.name}</name>
          <target>
            <path>{self.path}</path>
          </target>
        </pool>
        """.strip()
        
        try:
            # Define the pool
            self._pool = self.conn.storagePoolDefineXML(xml, 0)
            
            if auto_start:
                self.start()
                self.set_autostart(True)
                
            logger.info(f"Created storage repository '{self.name}' at {self.path}")
            return self
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to create storage repository: {e}")
    
    def start(self) -> 'StorageRepository':
        """Start the repository"""
        pool = self.pool
        if not pool:
            raise VMError(f"Repository '{self.name}' does not exist")
        
        if not pool.isActive():
            try:
                pool.create(0)
                logger.info(f"Started repository '{self.name}'")
            except libvirt.libvirtError as e:
                raise VMError(f"Failed to start repository: {e}")
        
        return self
    
    def stop(self) -> 'StorageRepository':
        """Stop the repository"""
        pool = self.pool
        if pool and pool.isActive():
            try:
                pool.destroy()
                logger.info(f"Stopped repository '{self.name}'")
            except libvirt.libvirtError as e:
                raise VMError(f"Failed to stop repository: {e}")
        
        return self
    
    def delete(self, force: bool = False) -> None:
        """
        Delete the repository
        
        Args:
            force: Force deletion even if repository contains volumes
        """
        pool = self.pool
        if not pool:
            return
        
        # Check for volumes if not forcing
        if not force:
            try:
                volumes = pool.listAllVolumes()
                if volumes:
                    volume_names = [vol.name() for vol in volumes]
                    raise VMError(f"Repository '{self.name}' contains volumes: {volume_names}. "
                                f"Use force=True to delete anyway.")
            except libvirt.libvirtError as e:
                logger.warning(f"Could not check volumes in repository: {e}")
        
        # Stop if active
        if pool.isActive():
            pool.destroy()
        
        # Undefine the pool
        try:
            pool.undefine()
            logger.info(f"Deleted repository '{self.name}'")
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to delete repository: {e}")
        
        self._pool = None
    
    def set_autostart(self, enabled: bool) -> 'StorageRepository':
        """Set repository to start automatically"""
        pool = self.pool
        if not pool:
            raise VMError(f"Repository '{self.name}' does not exist")
        
        try:
            pool.setAutostart(1 if enabled else 0)
            logger.info(f"Set autostart for repository '{self.name}' to {enabled}")
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to set autostart: {e}")
        
        return self
    
    def refresh(self) -> 'StorageRepository':
        """Refresh repository to detect new volumes"""
        pool = self.pool
        if pool and pool.isActive():
            try:
                pool.refresh(0)
                logger.debug(f"Refreshed repository '{self.name}'")
            except libvirt.libvirtError as e:
                raise VMError(f"Failed to refresh repository: {e}")
        
        return self
    
    def info(self) -> Dict:
        """Get repository information"""
        pool = self.pool
        if not pool:
            return {
                'name': self.name,
                'path': str(self.path),
                'status': 'undefined'
            }
        
        try:
            info = pool.info()
            return {
                'name': self.name,
                'path': str(self.path),
                'status': 'active' if pool.isActive() else 'inactive',
                'capacity': info[1],
                'allocation': info[2],
                'available': info[3],
                'autostart': pool.autostart()
            }
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to get repository info: {e}")
    
    def list_volumes(self) -> List[Dict]:
        """List volumes in the repository"""
        pool = self.pool
        if not pool or not pool.isActive():
            return []
        
        try:
            volumes = []
            for vol in pool.listAllVolumes():
                vol_info = vol.info()
                volumes.append({
                    'name': vol.name(),
                    'path': vol.path(),
                    'capacity': vol_info[1],
                    'allocation': vol_info[2],
                    'type': vol_info[0]
                })
            return volumes
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to list volumes: {e}")
    
    def create_volume(self, name: str, size: str, format: str = "qcow2") -> Dict:
        """
        Create a new volume in the repository
        
        Args:
            name: Volume name
            size: Volume size (e.g., "10G", "1024M")
            format: Image format (qcow2, raw, etc.)
        """
        pool = self.pool
        if not pool:
            raise VMError(f"Repository '{self.name}' does not exist")
        
        if not pool.isActive():
            raise VMError(f"Repository '{self.name}' is not active")
        
        # Parse size
        size_bytes = self._parse_size(size)
        
        # Generate volume XML
        xml = f"""
        <volume>
          <name>{name}</name>
          <capacity unit='bytes'>{size_bytes}</capacity>
          <target>
            <format type='{format}'/>
          </target>
        </volume>
        """.strip()
        
        try:
            vol = pool.createXML(xml, 0)
            vol_info = vol.info()
            
            result = {
                'name': vol.name(),
                'path': vol.path(),
                'capacity': vol_info[1],
                'allocation': vol_info[2],
                'format': format
            }
            
            logger.info(f"Created volume '{name}' in repository '{self.name}'")
            return result
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to create volume: {e}")
    
    def delete_volume(self, name: str) -> None:
        """Delete a volume from the repository"""
        pool = self.pool
        if not pool:
            raise VMError(f"Repository '{self.name}' does not exist")
        
        try:
            vol = pool.storageVolLookupByName(name)
            vol.delete(0)
            logger.info(f"Deleted volume '{name}' from repository '{self.name}'")
        except libvirt.libvirtError as e:
            raise VMError(f"Failed to delete volume: {e}")
    
    def get_volume_path(self, name: str) -> str:
        """Get the full path to a volume"""
        pool = self.pool
        if not pool:
            raise VMError(f"Repository '{self.name}' does not exist")
        
        try:
            vol = pool.storageVolLookupByName(name)
            return vol.path()
        except libvirt.libvirtError as e:
            raise VMError(f"Volume '{name}' not found in repository: {e}")
    
    def _parse_size(self, size: str) -> int:
        """Parse size string to bytes"""
        size = size.upper().strip()
        
        if size.endswith('G'):
            return int(size[:-1]) * 1024 * 1024 * 1024
        elif size.endswith('M'):
            return int(size[:-1]) * 1024 * 1024
        elif size.endswith('K'):
            return int(size[:-1]) * 1024
        elif size.endswith('B'):
            return int(size[:-1])
        else:
            return int(size)  # Assume bytes


class StorageManager:
    """
    Manages multiple storage repositories
    
    Provides a centralized interface for all storage operations.
    """
    
    def __init__(self):
        self._conn = None
        self.config_file = Path("/etc/vmkit/storage.json")
        self._repositories = {}
    
    @property
    def conn(self) -> libvirt.virConnect:
        """Lazy libvirt connection"""
        if self._conn is None:
            try:
                self._conn = libvirt.open("qemu:///system")
            except libvirt.libvirtError as e:
                raise VMError(f"Failed to connect to libvirt: {e}")
        return self._conn
    
    def load_repositories(self) -> Dict[str, StorageRepository]:
        """Load repository definitions from libvirt"""
        repositories = {}
        
        try:
            pools = self.conn.listAllStoragePools()
            for pool in pools:
                name = pool.name()
                
                # Get pool info to determine path
                try:
                    xml_desc = pool.XMLDesc(0)
                    # Basic XML parsing - could use proper XML parser
                    if '<path>' in xml_desc:
                        path_start = xml_desc.find('<path>') + 6
                        path_end = xml_desc.find('</path>')
                        path = xml_desc[path_start:path_end]
                    else:
                        path = None
                    
                    repositories[name] = StorageRepository(name, path)
                except Exception as e:
                    logger.warning(f"Could not load repository {name}: {e}")
        
        except libvirt.libvirtError as e:
            logger.error(f"Failed to list storage pools: {e}")
        
        self._repositories = repositories
        return repositories
    
    def list_repositories(self) -> List[Dict]:
        """List all repositories with their status"""
        repositories = self.load_repositories()
        repo_list = []
        
        for name, repo in repositories.items():
            try:
                info = repo.info()
                repo_list.append(info)
            except Exception as e:
                logger.error(f"Error getting info for repository {name}: {e}")
                repo_list.append({
                    'name': name,
                    'status': 'error',
                    'error': str(e)
                })
        
        return repo_list
    
    def get_repository(self, name: str) -> StorageRepository:
        """Get a repository by name"""
        repositories = self.load_repositories()
        
        if name not in repositories:
            raise VMError(f"Repository '{name}' not found")
        
        return repositories[name]
    
    def create_repository(self, name: str, path: Union[str, Path], 
                         auto_start: bool = True) -> StorageRepository:
        """Create a new storage repository"""
        repo = StorageRepository(name, path)
        repo.create(auto_start=auto_start)
        return repo
    
    def delete_repository(self, name: str, force: bool = False) -> None:
        """Delete a storage repository"""
        repo = self.get_repository(name)
        repo.delete(force=force)
    
    def get_default_repository(self) -> StorageRepository:
        """Get or create the default repository"""
        try:
            return self.get_repository("default")
        except VMError:
            # Create default repository
            default_path = Path("/var/lib/vmkit/repos/default")
            return self.create_repository("default", default_path)
    
    def find_volume(self, volume_name: str) -> Optional[Dict]:
        """Find a volume across all repositories"""
        repositories = self.load_repositories()
        
        for repo_name, repo in repositories.items():
            try:
                volumes = repo.list_volumes()
                for vol in volumes:
                    if vol['name'] == volume_name:
                        vol['repository'] = repo_name
                        return vol
            except Exception as e:
                logger.debug(f"Error searching repository {repo_name}: {e}")
        
        return None
    
    def cleanup_unused_volumes(self, dry_run: bool = True) -> List[Dict]:
        """
        Find and optionally remove unused volumes
        
        Args:
            dry_run: If True, only report what would be deleted
        """
        # This would need to cross-reference with VM definitions
        # to determine which volumes are actually in use
        
        unused_volumes = []
        repositories = self.load_repositories()
        
        # Get all defined VMs to see which volumes are in use
        used_paths = set()
        try:
            domains = self.conn.listAllDomains()
            for domain in domains:
                try:
                    xml_desc = domain.XMLDesc(0)
                    # Extract disk paths from XML - this is a simplification
                    if '<source file=' in xml_desc:
                        import re
                        paths = re.findall(r'<source file=[\'"]([^\'"]+)[\'"]', xml_desc)
                        used_paths.update(paths)
                except Exception as e:
                    logger.debug(f"Error checking VM {domain.name()}: {e}")
        except libvirt.libvirtError as e:
            logger.warning(f"Could not list VMs: {e}")
        
        # Find unused volumes
        for repo_name, repo in repositories.items():
            try:
                volumes = repo.list_volumes()
                for vol in volumes:
                    if vol['path'] not in used_paths:
                        vol['repository'] = repo_name
                        unused_volumes.append(vol)
                        
                        if not dry_run:
                            repo.delete_volume(vol['name'])
                            logger.info(f"Deleted unused volume: {vol['name']}")
                            
            except Exception as e:
                logger.error(f"Error processing repository {repo_name}: {e}")
        
        return unused_volumes
