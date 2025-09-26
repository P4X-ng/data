#!/usr/bin/env python3
"""
Packet Bridge - Network machines as filesystem directories
Makes `cd /net/machine2` work seamlessly
"""
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Set
import redis
import json

class PacketBridge:
    def __init__(self, mount_root="/net", redis_host="localhost", redis_port=6379):
        self.mount_root = Path(mount_root)
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.active_mounts: Dict[str, subprocess.Popen] = {}
        self.discovery_thread = None
        self.running = False
        
        # Ensure mount root exists
        self.mount_root.mkdir(parents=True, exist_ok=True)
    
    def discover_machines(self):
        """Auto-discover PacketFS machines on network"""
        while self.running:
            try:
                # Get cluster nodes from F3 API
                machines = self.redis.smembers("pfs:cluster:nodes")
                for machine in machines:
                    if machine not in self.active_mounts:
                        self.mount_machine(machine)
                time.sleep(30)  # Check every 30s
            except Exception as e:
                print(f"Discovery error: {e}")
                time.sleep(10)
    
    def mount_machine(self, hostname: str, port: int = 8811):
        """Mount remote PacketFS machine as local directory"""
        mount_point = self.mount_root / hostname
        mount_point.mkdir(exist_ok=True)
        
        if hostname in self.active_mounts:
            return  # Already mounted
        
        # Mount using PacketFS FUSE
        cmd = [
            "python", "-m", "packetfs.filesystem.pfsfs_mount",
            "--remote", f"{hostname}:{port}",
            "--mount", str(mount_point),
            "--foreground", "false"
        ]
        
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.active_mounts[hostname] = proc
            
            # Register in Redis for other nodes
            self.redis.sadd("pfs:bridges:active", hostname)
            print(f"Mounted {hostname} at {mount_point}")
            
        except Exception as e:
            print(f"Failed to mount {hostname}: {e}")
    
    def unmount_machine(self, hostname: str):
        """Unmount remote machine"""
        if hostname not in self.active_mounts:
            return
        
        mount_point = self.mount_root / hostname
        
        # Kill FUSE process
        proc = self.active_mounts[hostname]
        proc.terminate()
        proc.wait()
        
        # Unmount
        subprocess.run(["fusermount", "-u", str(mount_point)], check=False)
        
        del self.active_mounts[hostname]
        self.redis.srem("pfs:bridges:active", hostname)
        print(f"Unmounted {hostname}")
    
    def start(self):
        """Start packet bridge service"""
        self.running = True
        self.discovery_thread = threading.Thread(target=self.discover_machines)
        self.discovery_thread.daemon = True
        self.discovery_thread.start()
        print(f"Packet Bridge started - machines will appear in {self.mount_root}")
    
    def stop(self):
        """Stop packet bridge and unmount all"""
        self.running = False
        if self.discovery_thread:
            self.discovery_thread.join()
        
        for hostname in list(self.active_mounts.keys()):
            self.unmount_machine(hostname)
    
    def list_bridges(self):
        """List active packet bridges"""
        return list(self.active_mounts.keys())

def main():
    bridge = PacketBridge()
    
    try:
        bridge.start()
        print("Packet Bridge running. Press Ctrl+C to stop.")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping Packet Bridge...")
        bridge.stop()

if __name__ == "__main__":
    main()