#!/usr/bin/env python3
"""
Unified Filesystem - FUSE overlay of multiple PacketFS filesystems
Creates single view of all cluster nodes' filesystems
"""

import os
import stat
import errno
import time
import json
import threading
from typing import Dict, List, Optional, Tuple
from fuse import FUSE, FuseOSError, Operations
from dataclasses import dataclass

@dataclass
class NodeFS:
    node_id: str
    mount_path: str
    priority: int = 1
    last_seen: float = 0.0
    healthy: bool = True

@dataclass
class FileVersion:
    node_id: str
    path: str
    mtime: float
    size: int
    checksum: Optional[str] = None

class UnifiedFS(Operations):
    """FUSE filesystem that overlays multiple PacketFS nodes"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.nodes: Dict[str, NodeFS] = {}
        self.file_cache: Dict[str, List[FileVersion]] = {}
        self.lock = threading.RLock()
        self._load_config()
        self._start_health_monitor()
    
    def _load_config(self):
        """Load cluster configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            for node_config in config.get('nodes', []):
                node = NodeFS(
                    node_id=node_config['id'],
                    mount_path=node_config['mount_path'],
                    priority=node_config.get('priority', 1)
                )
                self.nodes[node.node_id] = node
                
        except Exception as e:
            print(f"Failed to load config: {e}")
    
    def _start_health_monitor(self):
        """Start background health monitoring"""
        def monitor():
            while True:
                self._check_node_health()
                time.sleep(30)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    
    def _check_node_health(self):
        """Check health of all nodes"""
        with self.lock:
            for node in self.nodes.values():
                try:
                    # Simple health check - can we stat the mount?
                    os.stat(node.mount_path)
                    node.healthy = True
                    node.last_seen = time.time()
                except:
                    node.healthy = False
    
    def _get_healthy_nodes(self) -> List[NodeFS]:
        """Get list of healthy nodes sorted by priority"""
        with self.lock:
            healthy = [n for n in self.nodes.values() if n.healthy]
            return sorted(healthy, key=lambda x: x.priority, reverse=True)
    
    def _resolve_path(self, path: str) -> List[Tuple[NodeFS, str]]:
        """Resolve path to all possible node locations"""
        results = []
        for node in self._get_healthy_nodes():
            full_path = os.path.join(node.mount_path, path.lstrip('/'))
            if os.path.exists(full_path):
                results.append((node, full_path))
        return results
    
    def _get_best_version(self, path: str) -> Optional[Tuple[NodeFS, str]]:
        """Get the best version of a file (latest mtime)"""
        candidates = self._resolve_path(path)
        if not candidates:
            return None
        
        best = None
        best_mtime = 0
        
        for node, full_path in candidates:
            try:
                st = os.stat(full_path)
                if st.st_mtime > best_mtime:
                    best_mtime = st.st_mtime
                    best = (node, full_path)
            except:
                continue
        
        return best
    
    def _list_all_files(self, path: str) -> Dict[str, FileVersion]:
        """List all files from all nodes, with conflict resolution"""
        all_files = {}
        
        for node in self._get_healthy_nodes():
            node_path = os.path.join(node.mount_path, path.lstrip('/'))
            try:
                for entry in os.listdir(node_path):
                    entry_path = os.path.join(node_path, entry)
                    try:
                        st = os.stat(entry_path)
                        version = FileVersion(
                            node_id=node.node_id,
                            path=entry_path,
                            mtime=st.st_mtime,
                            size=st.st_size
                        )
                        
                        # Keep latest version
                        if entry not in all_files or version.mtime > all_files[entry].mtime:
                            all_files[entry] = version
                            
                    except:
                        continue
            except:
                continue
        
        return all_files
    
    # FUSE Operations
    def getattr(self, path, fh=None):
        if path == '/':
            return dict(st_mode=(stat.S_IFDIR | 0o755), st_nlink=2)
        
        best = self._get_best_version(path)
        if not best:
            raise FuseOSError(errno.ENOENT)
        
        node, full_path = best
        try:
            st = os.stat(full_path)
            return dict(
                st_mode=st.st_mode,
                st_nlink=st.st_nlink,
                st_size=st.st_size,
                st_atime=st.st_atime,
                st_mtime=st.st_mtime,
                st_ctime=st.st_ctime
            )
        except OSError as e:
            raise FuseOSError(e.errno)
    
    def readdir(self, path, fh):
        files = self._list_all_files(path)
        return ['.', '..'] + list(files.keys())
    
    def open(self, path, flags):
        best = self._get_best_version(path)
        if not best:
            raise FuseOSError(errno.ENOENT)
        
        node, full_path = best
        try:
            return os.open(full_path, flags)
        except OSError as e:
            raise FuseOSError(e.errno)
    
    def read(self, path, size, offset, fh):
        try:
            os.lseek(fh, offset, os.SEEK_SET)
            return os.read(fh, size)
        except OSError as e:
            raise FuseOSError(e.errno)
    
    def release(self, path, fh):
        try:
            os.close(fh)
        except OSError as e:
            raise FuseOSError(e.errno)
    
    def write(self, path, data, offset, fh):
        """Write to primary node (highest priority healthy node)"""
        try:
            os.lseek(fh, offset, os.SEEK_SET)
            return os.write(fh, data)
        except OSError as e:
            raise FuseOSError(e.errno)
    
    def create(self, path, mode, fi=None):
        """Create file on primary node"""
        healthy_nodes = self._get_healthy_nodes()
        if not healthy_nodes:
            raise FuseOSError(errno.ENOSPC)
        
        primary = healthy_nodes[0]
        full_path = os.path.join(primary.mount_path, path.lstrip('/'))
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        try:
            return os.open(full_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        except OSError as e:
            raise FuseOSError(e.errno)
    
    def mkdir(self, path, mode):
        """Create directory on all healthy nodes"""
        healthy_nodes = self._get_healthy_nodes()
        if not healthy_nodes:
            raise FuseOSError(errno.ENOSPC)
        
        success = False
        for node in healthy_nodes:
            full_path = os.path.join(node.mount_path, path.lstrip('/'))
            try:
                os.makedirs(full_path, mode, exist_ok=True)
                success = True
            except:
                continue
        
        if not success:
            raise FuseOSError(errno.EIO)
    
    def unlink(self, path):
        """Remove file from all nodes that have it"""
        candidates = self._resolve_path(path)
        if not candidates:
            raise FuseOSError(errno.ENOENT)
        
        for node, full_path in candidates:
            try:
                os.unlink(full_path)
            except:
                continue
    
    def rmdir(self, path):
        """Remove directory from all nodes"""
        candidates = self._resolve_path(path)
        if not candidates:
            raise FuseOSError(errno.ENOENT)
        
        for node, full_path in candidates:
            try:
                os.rmdir(full_path)
            except:
                continue
    
    def statfs(self, path):
        """Return filesystem statistics from primary node"""
        healthy_nodes = self._get_healthy_nodes()
        if not healthy_nodes:
            raise FuseOSError(errno.ENOSPC)
        
        primary = healthy_nodes[0]
        try:
            st = os.statvfs(primary.mount_path)
            return dict(
                f_bsize=st.f_bsize,
                f_blocks=st.f_blocks,
                f_bfree=st.f_bfree,
                f_bavail=st.f_bavail
            )
        except OSError as e:
            raise FuseOSError(e.errno)

def mount_unified_fs(config_path: str, mount_point: str, foreground: bool = False):
    """Mount the unified filesystem"""
    os.makedirs(mount_point, exist_ok=True)
    fs = UnifiedFS(config_path)
    
    print(f"Mounting unified filesystem at {mount_point}")
    print(f"Nodes: {list(fs.nodes.keys())}")
    
    FUSE(fs, mount_point, nothreads=True, foreground=foreground)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Mount unified PacketFS filesystem')
    parser.add_argument('--config', required=True, help='Cluster configuration file')
    parser.add_argument('--mount', required=True, help='Mount point')
    parser.add_argument('--foreground', action='store_true', help='Run in foreground')
    
    args = parser.parse_args()
    mount_unified_fs(args.config, args.mount, args.foreground)