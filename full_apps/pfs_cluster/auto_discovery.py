#!/usr/bin/env python3
"""
F3 Cluster Auto-Discovery
Scans IP ranges for SSH-accessible machines and auto-adds them to the cluster
"""

import asyncio
import ipaddress
import socket
import paramiko
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

logger = logging.getLogger(__name__)

@dataclass
class DiscoveredNode:
    """Represents a discovered node that can join the cluster"""
    ip: str
    hostname: str
    ssh_port: int
    os_info: str
    cpu_cores: int
    memory_gb: float
    disk_gb: float
    discovered_at: datetime
    username: Optional[str] = None
    
    def to_dict(self):
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "ssh_port": self.ssh_port,
            "os_info": self.os_info,
            "cpu_cores": self.cpu_cores,
            "memory_gb": self.memory_gb,
            "disk_gb": self.disk_gb,
            "discovered_at": self.discovered_at.isoformat(),
            "username": self.username
        }

class ClusterAutoDiscovery:
    """Auto-discovers and adds nodes to the F3 cluster"""
    
    def __init__(self):
        self.discovered_nodes: List[DiscoveredNode] = []
        self.scanning = False
        self.scan_progress = 0
        self.total_ips = 0
        self.active_connections: Dict[str, paramiko.SSHClient] = {}
        
    async def scan_port(self, ip: str, port: int = 22, timeout: float = 0.5) -> bool:
        """Check if a port is open on an IP"""
        try:
            # Use asyncio to check port without blocking
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False
    
    async def scan_ip_range(
        self, 
        ip_range: str,
        port: int = 22,
        batch_size: int = 50,
        progress_callback=None
    ) -> List[str]:
        """
        Scan an IP range for open SSH ports
        
        Args:
            ip_range: CIDR notation (e.g., "192.168.1.0/24")
            port: SSH port to check
            batch_size: Number of IPs to check concurrently
            progress_callback: Async callback for progress updates
        
        Returns:
            List of IPs with SSH open
        """
        self.scanning = True
        accessible_ips = []
        
        try:
            network = ipaddress.ip_network(ip_range, strict=False)
            all_ips = [str(ip) for ip in network.hosts()]
            self.total_ips = len(all_ips)
            
            logger.info(f"Scanning {self.total_ips} IPs in {ip_range}")
            
            # Process IPs in batches
            for i in range(0, len(all_ips), batch_size):
                batch = all_ips[i:i + batch_size]
                
                # Check all IPs in batch concurrently
                tasks = [self.scan_port(ip, port) for ip in batch]
                results = await asyncio.gather(*tasks)
                
                # Collect accessible IPs
                for ip, is_open in zip(batch, results):
                    if is_open:
                        accessible_ips.append(ip)
                        logger.info(f"Found SSH on {ip}:{port}")
                
                # Update progress
                self.scan_progress = min(i + batch_size, self.total_ips)
                if progress_callback:
                    await progress_callback({
                        "scanning": True,
                        "progress": self.scan_progress,
                        "total": self.total_ips,
                        "found": len(accessible_ips),
                        "current_ip": batch[-1] if batch else None
                    })
            
        except Exception as e:
            logger.error(f"Error scanning IP range: {e}")
        finally:
            self.scanning = False
            self.scan_progress = 0
            
        return accessible_ips
    
    def get_node_info_via_ssh(
        self, 
        ip: str,
        username: str,
        password: str,
        port: int = 22
    ) -> Optional[DiscoveredNode]:
        """
        Connect via SSH and gather system information
        
        Args:
            ip: Target IP address
            username: SSH username
            password: SSH password
            port: SSH port
        
        Returns:
            DiscoveredNode with system info or None if failed
        """
        ssh = paramiko.SSHClient()
        # AutoAddPolicy automatically accepts unknown host keys
        # In production, you might want to use paramiko.RejectPolicy() and manage known_hosts
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Connect with timeout and auto-accept host keys
            ssh.connect(
                ip, 
                port=port,
                username=username,
                password=password,
                timeout=5,
                look_for_keys=False,  # Don't use SSH keys, only password
                allow_agent=False,     # Don't use SSH agent
                banner_timeout=10      # Wait longer for banner/prompts
            )
            
            # Get hostname
            stdin, stdout, stderr = ssh.exec_command("hostname")
            hostname = stdout.read().decode().strip()
            
            # Get OS info
            stdin, stdout, stderr = ssh.exec_command("uname -a")
            os_info = stdout.read().decode().strip()
            
            # Get CPU cores
            stdin, stdout, stderr = ssh.exec_command("nproc")
            cpu_cores = int(stdout.read().decode().strip())
            
            # Get memory (in GB)
            stdin, stdout, stderr = ssh.exec_command(
                "free -b | grep Mem | awk '{print $2}'"
            )
            memory_bytes = int(stdout.read().decode().strip())
            memory_gb = round(memory_bytes / (1024**3), 2)
            
            # Get disk space (in GB)
            stdin, stdout, stderr = ssh.exec_command(
                "df -B1 / | tail -1 | awk '{print $2}'"
            )
            disk_bytes = int(stdout.read().decode().strip())
            disk_gb = round(disk_bytes / (1024**3), 2)
            
            # Store connection for later use
            self.active_connections[ip] = ssh
            
            node = DiscoveredNode(
                ip=ip,
                hostname=hostname,
                ssh_port=port,
                os_info=os_info,
                cpu_cores=cpu_cores,
                memory_gb=memory_gb,
                disk_gb=disk_gb,
                discovered_at=datetime.utcnow(),
                username=username
            )
            
            logger.info(f"Successfully gathered info from {ip}: {hostname}")
            return node
            
        except Exception as e:
            logger.error(f"Failed to connect to {ip}: {e}")
            try:
                ssh.close()
            except:
                pass
            return None
    
    async def auto_discover_and_add(
        self,
        ip_range: str,
        username: str,
        password: str,
        port: int = 22,
        auto_add: bool = True,
        progress_callback=None
    ) -> List[DiscoveredNode]:
        """
        Scan IP range, discover nodes, and optionally auto-add to cluster
        
        Args:
            ip_range: CIDR notation for IP range to scan
            username: SSH username for discovered nodes
            password: SSH password for discovered nodes
            port: SSH port (default 22)
            auto_add: Whether to automatically add discovered nodes
            progress_callback: Async callback for progress updates
        
        Returns:
            List of discovered nodes
        """
        # First, scan for SSH-accessible IPs
        accessible_ips = await self.scan_ip_range(
            ip_range, 
            port,
            progress_callback=progress_callback
        )
        
        if progress_callback:
            await progress_callback({
                "phase": "authentication",
                "total_found": len(accessible_ips),
                "authenticating": 0
            })
        
        # Try to authenticate and get info from each IP
        self.discovered_nodes = []
        
        for i, ip in enumerate(accessible_ips):
            if progress_callback:
                await progress_callback({
                    "phase": "authentication",
                    "total_found": len(accessible_ips),
                    "authenticating": i + 1,
                    "current_ip": ip
                })
            
            # Run SSH connection in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            node = await loop.run_in_executor(
                None,
                self.get_node_info_via_ssh,
                ip, username, password, port
            )
            
            if node:
                self.discovered_nodes.append(node)
                
                if auto_add:
                    # Auto-add to cluster
                    await self.add_node_to_cluster(node, password)
                    
                if progress_callback:
                    await progress_callback({
                        "phase": "discovered",
                        "node": node.to_dict()
                    })
        
        return self.discovered_nodes
    
    async def add_node_to_cluster(
        self, 
        node: DiscoveredNode,
        password: str
    ) -> bool:
        """
        Add a discovered node to the F3 cluster
        
        Args:
            node: DiscoveredNode to add
            password: SSH password for setup commands
        
        Returns:
            True if successfully added
        """
        try:
            ssh = self.active_connections.get(node.ip)
            if not ssh:
                # Reconnect if needed
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    node.ip,
                    port=node.ssh_port,
                    username=node.username,
                    password=password,
                    timeout=5,
                    look_for_keys=False,
                    allow_agent=False
                )
            
            # Install F3 agent on the node
            commands = [
                # Check if Docker/Podman is installed
                "command -v docker || command -v podman",
                
                # Pull F3 agent image (using podman if available, else docker)
                "(command -v podman && podman pull localhost:5000/f3-agent) || docker pull localhost:5000/f3-agent",
                
                # Run F3 agent
                f"(command -v podman && podman run -d --name f3-agent --network host localhost:5000/f3-agent --master {socket.gethostname()}) || "
                f"docker run -d --name f3-agent --network host localhost:5000/f3-agent --master {socket.gethostname()}"
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                result = stdout.read().decode()
                error = stderr.read().decode()
                
                if error and "not found" not in error.lower():
                    logger.warning(f"Command warning on {node.ip}: {error}")
            
            logger.info(f"Successfully added {node.hostname} ({node.ip}) to cluster")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add {node.ip} to cluster: {e}")
            return False
    
    def close_all_connections(self):
        """Close all active SSH connections"""
        for ip, ssh in self.active_connections.items():
            try:
                ssh.close()
            except:
                pass
        self.active_connections.clear()


# WebSocket handler for auto-discovery
class AutoDiscoveryWebSocket:
    """WebSocket handler for real-time auto-discovery updates"""
    
    def __init__(self):
        self.discovery = ClusterAutoDiscovery()
        self.active_scans = {}
    
    async def handle_message(self, websocket, message: dict):
        """Handle incoming WebSocket messages"""
        action = message.get("action")
        
        if action == "scan":
            # Start scanning IP range
            ip_range = message.get("ip_range", "192.168.1.0/24")
            username = message.get("username", "root")
            password = message.get("password", "")
            auto_add = message.get("auto_add", True)
            
            # Progress callback to send updates
            async def progress_update(data):
                await websocket.send_json({
                    "type": "scan_progress",
                    **data
                })
            
            # Run discovery in background
            task = asyncio.create_task(
                self.discovery.auto_discover_and_add(
                    ip_range=ip_range,
                    username=username,
                    password=password,
                    auto_add=auto_add,
                    progress_callback=progress_update
                )
            )
            
            self.active_scans[ip_range] = task
            
            # Wait for completion
            nodes = await task
            
            # Send final results
            await websocket.send_json({
                "type": "scan_complete",
                "nodes": [node.to_dict() for node in nodes],
                "total": len(nodes)
            })
            
        elif action == "stop_scan":
            # Stop ongoing scan
            ip_range = message.get("ip_range")
            if ip_range in self.active_scans:
                self.active_scans[ip_range].cancel()
                del self.active_scans[ip_range]
                
                await websocket.send_json({
                    "type": "scan_stopped",
                    "ip_range": ip_range
                })
        
        elif action == "get_discovered":
            # Return currently discovered nodes
            await websocket.send_json({
                "type": "discovered_nodes",
                "nodes": [node.to_dict() for node in self.discovery.discovered_nodes]
            })


if __name__ == "__main__":
    # Test auto-discovery
    async def test():
        discovery = ClusterAutoDiscovery()
        
        # Test scanning local network
        print("Scanning local network for SSH hosts...")
        ips = await discovery.scan_ip_range("192.168.1.0/24")
        print(f"Found {len(ips)} hosts with SSH open: {ips}")
        
        # Test authentication (example)
        if ips:
            print(f"\nTrying to connect to {ips[0]}...")
            node = discovery.get_node_info_via_ssh(
                ips[0], 
                username="test",
                password="test"
            )
            if node:
                print(f"Node info: {node.to_dict()}")
    
    asyncio.run(test())