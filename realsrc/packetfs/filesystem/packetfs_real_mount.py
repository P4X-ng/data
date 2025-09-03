#!/usr/bin/env python3
"""
PacketFS Real In-Memory Mount
============================

Professional PacketFS implementation with:
- Real tmpfs mounting  
- Actual compression (gzip)
- File monitoring
- Performance metrics
- Clean logging output for demonstrations
"""

import os
import sys
import time
import json
import hashlib
import gzip
import subprocess
import threading
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('PacketFS')

@dataclass
class CompressionStats:
    original_size: int
    compressed_size: int
    compression_ratio: float
    algorithm: str
    time_ms: float

@dataclass  
class PacketFSMetrics:
    mount_point: str
    mount_time: float
    total_files: int = 0
    total_original_bytes: int = 0
    total_compressed_bytes: int = 0
    dedup_saved_bytes: int = 0
    operations_count: int = 0

class PacketFSRealMount:
    def __init__(self, mount_point="/mnt/packetfs", size_mb=512):
        self.mount_point = Path(mount_point)
        self.size_mb = size_mb
        self.dedup_hashes = {}
        self.metrics = PacketFSMetrics(str(self.mount_point), time.time())
        self.running = False
        self.watcher_thread = None
        self.lock = threading.RLock()
        
    def create_mount(self):
        logger.info(f"Creating tmpfs mount: {self.mount_point} ({self.size_mb}MB)")
        
        try:
            self.mount_point.mkdir(parents=True, exist_ok=True)
            
            # Check if already mounted
            result = subprocess.run(['mountpoint', '-q', str(self.mount_point)], 
                                  capture_output=True)
            if result.returncode != 0:
                subprocess.run([
                    'mount', '-t', 'tmpfs', '-o', f'size={self.size_mb}M',
                    'packetfs', str(self.mount_point)
                ], check=True, capture_output=True, text=True)
                logger.info("tmpfs mounted successfully")
            else:
                logger.info("Mount point already mounted")
            
            # Create directory structure
            for dir_name in ["data", "compressed", "metadata", "stats"]:
                (self.mount_point / dir_name).mkdir(exist_ok=True)
                
            config = {
                "version": "1.0.0",
                "mount_point": str(self.mount_point),
                "size_mb": self.size_mb,
                "created": time.time()
            }
            
            with open(self.mount_point / "metadata" / "config.json", 'w') as f:
                json.dump(config, f, indent=2)
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to create mount: {e}")
            return False
            
    def compress_file(self, file_path: Path) -> CompressionStats:
        try:
            with open(file_path, 'rb') as f:
                original_data = f.read()
            original_size = len(original_data)
            
            if original_size == 0:
                return CompressionStats(0, 0, 1.0, "none", 0.0)
            
            # Check deduplication
            file_hash = hashlib.sha256(original_data).hexdigest()
            if file_hash in self.dedup_hashes:
                existing_path = self.dedup_hashes[file_hash]
                logger.info(f"Deduplication: {file_path.name} matches {Path(existing_path).name}")
                with self.lock:
                    self.metrics.dedup_saved_bytes += original_size
                return CompressionStats(original_size, 0, float('inf'), "dedup", 0.0)
            
            # Compress
            start_time = time.perf_counter()
            compressed_data = gzip.compress(original_data, compresslevel=6)
            compression_time = (time.perf_counter() - start_time) * 1000
            
            compressed_size = len(compressed_data)
            
            # Store compressed file
            compressed_path = self.mount_point / "compressed" / f"{file_path.name}.gz"
            with open(compressed_path, 'wb') as f:
                f.write(compressed_data)
                
            self.dedup_hashes[file_hash] = str(file_path)
            
            compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            
            stats = CompressionStats(original_size, compressed_size, compression_ratio, "gzip", compression_time)
            
            logger.info(f"Compressed {file_path.name}: {original_size:,} -> {compressed_size:,} bytes ({compression_ratio:.2f}x)")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error compressing {file_path}: {e}")
            return CompressionStats(0, 0, 1.0, "error", 0.0)
            
    def start_watcher(self):
        data_dir = self.mount_point / "data"
        logger.info(f"Starting file watcher for {data_dir}")
        
        known_files = set()
        
        def watcher_worker():
            nonlocal known_files
            while self.running:
                try:
                    current_files = set()
                    if data_dir.exists():
                        for file_path in data_dir.rglob('*'):
                            if file_path.is_file():
                                current_files.add(file_path)
                    
                    new_files = current_files - known_files
                    for file_path in new_files:
                        logger.info(f"New file: {file_path.name}")
                        self.process_file(file_path)
                        
                    known_files = current_files
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Watcher error: {e}")
                    time.sleep(2)
                    
        self.watcher_thread = threading.Thread(target=watcher_worker, daemon=True)
        self.watcher_thread.start()
        
    def process_file(self, file_path: Path):
        try:
            stats = self.compress_file(file_path)
            
            with self.lock:
                self.metrics.total_files += 1
                self.metrics.total_original_bytes += stats.original_size
                self.metrics.total_compressed_bytes += stats.compressed_size
                self.metrics.operations_count += 1
                
            metadata = {
                "original_path": str(file_path),
                "stats": asdict(stats),
                "processed_time": time.time()
            }
            
            metadata_path = self.mount_point / "metadata" / f"{file_path.name}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            
    def get_stats(self):
        with self.lock:
            uptime = time.time() - self.metrics.mount_time
            original_mb = self.metrics.total_original_bytes / (1024*1024)
            compressed_mb = self.metrics.total_compressed_bytes / (1024*1024) 
            space_saved = original_mb - compressed_mb
            dedup_mb = self.metrics.dedup_saved_bytes / (1024*1024)
            
            return {
                "mount_point": str(self.mount_point),
                "uptime_sec": round(uptime, 1),
                "total_files": self.metrics.total_files,
                "original_mb": round(original_mb, 2),
                "compressed_mb": round(compressed_mb, 2),
                "space_saved_mb": round(space_saved, 2),
                "dedup_saved_mb": round(dedup_mb, 2),
                "avg_compression": round(original_mb / compressed_mb, 2) if compressed_mb > 0 else 1.0,
                "files_per_sec": round(self.metrics.total_files / uptime, 2) if uptime > 0 else 0,
                "operations": self.metrics.operations_count
            }
            
    def print_stats(self):
        stats = self.get_stats()
        print("\nPacketFS Real-Time Statistics")
        print("=" * 40)
        print(f"Mount: {stats['mount_point']}")
        print(f"Uptime: {stats['uptime_sec']}s")
        print(f"Files: {stats['total_files']}")
        print(f"Operations: {stats['operations']}")
        print(f"Rate: {stats['files_per_sec']} files/sec")
        print()
        print(f"Original Size: {stats['original_mb']} MB")
        print(f"Compressed: {stats['compressed_mb']} MB")
        print(f"Space Saved: {stats['space_saved_mb']} MB")
        print(f"Dedup Saved: {stats['dedup_saved_mb']} MB")
        print(f"Compression: {stats['avg_compression']}x average")
        
        # Write to stats file
        with open(self.mount_point / "stats" / "live_stats.json", 'w') as f:
            json.dump(stats, f, indent=2)
        
    def start(self):
        logger.info("Starting PacketFS Real Mount")
        
        if not self.create_mount():
            return False
            
        self.running = True
        
        # Create data directory
        (self.mount_point / "data").mkdir(exist_ok=True)
        
        self.start_watcher()
        
        logger.info(f"PacketFS ready at {self.mount_point}")
        logger.info(f"Copy files to {self.mount_point}/data")
        
        return True
        
    def stop(self):
        logger.info("Stopping PacketFS")
        self.running = False
        
        if self.watcher_thread:
            self.watcher_thread.join(timeout=2)
            
        try:
            result = subprocess.run(['mountpoint', '-q', str(self.mount_point)], 
                                  capture_output=True)
            if result.returncode == 0:
                subprocess.run(['umount', str(self.mount_point)], check=True)
                logger.info("Unmounted successfully")
        except Exception as e:
            logger.warning(f"Unmount error: {e}")

def main():
    print("PacketFS Real In-Memory Mount v1.0")
    print("Professional Implementation")
    print()
    
    mount = PacketFSRealMount("/mnt/packetfs_demo", 256)
    
    try:
        if not mount.start():
            return 1
            
        time.sleep(1)
        mount.print_stats()
        
        print("\nPacketFS is running!")
        print("Copy files to /mnt/packetfs_demo/data")
        print("Press Ctrl+C to stop")
        
        while True:
            time.sleep(10)
            mount.print_stats()
            
    except KeyboardInterrupt:
        print("\nShutting down...")
        mount.stop()
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        mount.stop()
        return 1

if __name__ == "__main__":
    sys.exit(main())
