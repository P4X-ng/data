"""
F3 Cluster WebSocket Handler
Real-time cluster management with smooth streaming updates
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel


class NodeStatus(BaseModel):
    """Node status model"""
    id: str
    name: str
    address: str
    role: str = "worker"
    status: str = "healthy"
    cpu: float = 0.0
    memory: float = 0.0
    storage: float = 0.0
    connections: int = 0
    last_seen: float = 0.0
    latency_ms: Optional[float] = None


class TransferProgress(BaseModel):
    """Transfer progress model"""
    id: str
    filename: str
    size: str
    speed: float
    percent: float
    eta: str
    bytes_transferred: int = 0
    total_bytes: int = 0
    compression_ratio: float = 0.0


class ClusterStats(BaseModel):
    """Overall cluster statistics"""
    total_nodes: int = 0
    active_transfers: int = 0
    storage_used: float = 0.0
    throughput: float = 0.0
    cluster_health: str = "healthy"
    uptime_seconds: int = 0


class ClusterEvent(BaseModel):
    """Generic cluster event"""
    type: str
    timestamp: float
    data: Dict


# Global state for cluster management
CLUSTER_STATE = {
    "nodes": {},  # Dict[str, NodeStatus]
    "transfers": {},  # Dict[str, TransferProgress]
    "stats": ClusterStats(),
    "connections": set(),  # Set of active WebSocket connections
    "start_time": time.time(),
}

# Lock for state modifications
STATE_LOCK = asyncio.Lock()


class ConnectionManager:
    """Manages WebSocket connections for cluster updates"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_metadata[websocket] = {
            "id": client_id or str(uuid.uuid4()),
            "connected_at": time.time(),
            "last_ping": time.time(),
        }
        
        # Send initial state
        await self.send_initial_state(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        self.connection_metadata.pop(websocket, None)
    
    async def send_initial_state(self, websocket: WebSocket):
        """Send current cluster state to newly connected client"""
        async with STATE_LOCK:
            initial_data = {
                "type": "initial_state",
                "timestamp": time.time(),
                "nodes": [node.dict() for node in CLUSTER_STATE["nodes"].values()],
                "transfers": [transfer.dict() for transfer in CLUSTER_STATE["transfers"].values()],
                "stats": CLUSTER_STATE["stats"].dict(),
            }
        
        await websocket.send_json(initial_data)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)


# Global connection manager
manager = ConnectionManager()


async def simulate_node_metrics():
    """Simulate node metrics updates for demo"""
    while True:
        async with STATE_LOCK:
            for node_id, node in CLUSTER_STATE["nodes"].items():
                # Smooth metric changes
                node.cpu = max(0, min(100, node.cpu + (asyncio.create_task.__hash__() % 11 - 5) * 0.5))
                node.memory = max(0, min(100, node.memory + (asyncio.create_task.__hash__() % 11 - 5) * 0.3))
                node.storage = max(0, min(1000, node.storage + (asyncio.create_task.__hash__() % 3 - 1) * 0.1))
                node.last_seen = time.time()
                
                # Calculate latency based on "distance"
                node.latency_ms = 5 + (asyncio.create_task.__hash__() % 20)
        
        # Broadcast node updates
        await manager.broadcast({
            "type": "nodes_update",
            "timestamp": time.time(),
            "nodes": [node.dict() for node in CLUSTER_STATE["nodes"].values()],
        })
        
        await asyncio.sleep(2)  # Update every 2 seconds


async def simulate_transfer_progress():
    """Simulate file transfer progress"""
    while True:
        async with STATE_LOCK:
            # Update existing transfers
            completed = []
            for transfer_id, transfer in CLUSTER_STATE["transfers"].items():
                if transfer.percent < 100:
                    # Smooth progress increase
                    speed_variance = (asyncio.create_task.__hash__() % 21 - 10) * 0.1
                    transfer.speed = max(10, transfer.speed + speed_variance)
                    
                    progress_increment = transfer.speed / 10  # Progress based on speed
                    transfer.percent = min(100, transfer.percent + progress_increment)
                    
                    # Update transferred bytes
                    transfer.bytes_transferred = int(transfer.total_bytes * transfer.percent / 100)
                    
                    # Calculate ETA
                    if transfer.speed > 0:
                        remaining_bytes = transfer.total_bytes - transfer.bytes_transferred
                        eta_seconds = remaining_bytes / (transfer.speed * 1024 * 1024)
                        transfer.eta = f"{int(eta_seconds)}s"
                    
                    # Update compression ratio
                    transfer.compression_ratio = 0.3 + (asyncio.create_task.__hash__() % 40) / 100
                    
                    # Broadcast progress
                    await manager.broadcast({
                        "type": "transfer_progress",
                        "timestamp": time.time(),
                        "progress": transfer.dict(),
                    })
                else:
                    completed.append(transfer_id)
            
            # Remove completed transfers after a delay
            for transfer_id in completed:
                del CLUSTER_STATE["transfers"][transfer_id]
                await manager.broadcast({
                    "type": "transfer_complete",
                    "timestamp": time.time(),
                    "transfer_id": transfer_id,
                })
        
        await asyncio.sleep(0.5)  # Update every 500ms for smooth progress


async def update_cluster_stats():
    """Update overall cluster statistics"""
    while True:
        async with STATE_LOCK:
            stats = CLUSTER_STATE["stats"]
            stats.total_nodes = len(CLUSTER_STATE["nodes"])
            stats.active_transfers = len(CLUSTER_STATE["transfers"])
            
            # Calculate total storage
            stats.storage_used = sum(node.storage for node in CLUSTER_STATE["nodes"].values())
            
            # Calculate throughput
            total_speed = sum(t.speed for t in CLUSTER_STATE["transfers"].values())
            stats.throughput = total_speed
            
            # Update uptime
            stats.uptime_seconds = int(time.time() - CLUSTER_STATE["start_time"])
            
            # Determine cluster health
            unhealthy_nodes = sum(1 for n in CLUSTER_STATE["nodes"].values() if n.status != "healthy")
            if unhealthy_nodes == 0:
                stats.cluster_health = "healthy"
            elif unhealthy_nodes < stats.total_nodes / 2:
                stats.cluster_health = "warning"
            else:
                stats.cluster_health = "error"
        
        # Broadcast stats update
        await manager.broadcast({
            "type": "cluster_stats",
            "timestamp": time.time(),
            "stats": CLUSTER_STATE["stats"].dict(),
        })
        
        await asyncio.sleep(3)  # Update every 3 seconds


async def heartbeat_handler():
    """Send periodic heartbeats to keep connections alive"""
    while True:
        await manager.broadcast({
            "type": "heartbeat",
            "timestamp": time.time(),
        })
        await asyncio.sleep(30)  # Heartbeat every 30 seconds


def register_cluster_ws(app: FastAPI) -> None:
    """Register cluster WebSocket handlers"""
    
    @app.websocket("/ws/cluster")
    async def cluster_websocket(websocket: WebSocket):
        """Main cluster WebSocket endpoint"""
        client_id = str(uuid.uuid4())
        await manager.connect(websocket, client_id)
        
        # Send welcome message with smooth animation trigger
        await manager.send_personal(websocket, {
            "type": "welcome",
            "timestamp": time.time(),
            "client_id": client_id,
            "message": "Connected to F3 Cluster Management",
        })
        
        # Log connection
        await manager.broadcast({
            "type": "log",
            "level": "info",
            "message": f"New client connected: {client_id[:8]}...",
            "timestamp": time.time(),
        })
        
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_json()
                await handle_client_message(websocket, client_id, data)
                
        except WebSocketDisconnect:
            manager.disconnect(websocket)
            await manager.broadcast({
                "type": "log",
                "level": "info",
                "message": f"Client disconnected: {client_id[:8]}...",
                "timestamp": time.time(),
            })
        except Exception as e:
            manager.disconnect(websocket)
            await manager.broadcast({
                "type": "log",
                "level": "error",
                "message": f"Client error: {str(e)}",
                "timestamp": time.time(),
            })


async def handle_client_message(websocket: WebSocket, client_id: str, data: dict):
    """Handle messages from client"""
    msg_type = data.get("type")
    
    if msg_type == "bootstrap_seed":
        # Handle seed node bootstrap
        node_name = data.get("name", "seed-1")
        bind_address = data.get("bind_address", "0.0.0.0:8811")
        
        # Create seed node
        node_id = str(uuid.uuid4())
        node = NodeStatus(
            id=node_id,
            name=node_name,
            address=bind_address,
            role="seed",
            status="healthy",
            cpu=10.0,
            memory=15.0,
            storage=100.0,
            connections=0,
            last_seen=time.time(),
        )
        
        async with STATE_LOCK:
            CLUSTER_STATE["nodes"][node_id] = node
        
        # Send progress updates
        steps = [
            ("Creating cluster configuration...", 20),
            ("Initializing storage backend...", 40),
            ("Setting up TLS certificates...", 60),
            ("Starting cluster services...", 80),
            ("Seed node initialized!", 100),
        ]
        
        for message, progress in steps:
            await manager.send_personal(websocket, {
                "type": "bootstrap_progress",
                "progress": progress,
                "message": message,
                "timestamp": time.time(),
            })
            
            await manager.broadcast({
                "type": "log",
                "level": "info",
                "message": message,
                "timestamp": time.time(),
            })
            
            await asyncio.sleep(0.8)  # Smooth animation
        
        # Broadcast node addition
        await manager.broadcast({
            "type": "node_added",
            "node": node.dict(),
            "timestamp": time.time(),
        })
        
        await manager.broadcast({
            "type": "log",
            "level": "success",
            "message": f"Seed node '{node_name}' successfully initialized",
            "timestamp": time.time(),
        })
    
    elif msg_type == "join_cluster":
        # Handle node join
        node_name = data.get("name", "node")
        node_address = data.get("address", "")
        seed_address = data.get("seed_address", "")
        
        node_id = str(uuid.uuid4())
        node = NodeStatus(
            id=node_id,
            name=node_name,
            address=node_address,
            role="worker",
            status="healthy",
            cpu=20.0,
            memory=30.0,
            storage=200.0,
            connections=1,
            last_seen=time.time(),
        )
        
        async with STATE_LOCK:
            CLUSTER_STATE["nodes"][node_id] = node
        
        # Send join progress
        steps = [
            ("Connecting to seed node...", 20),
            ("Exchanging certificates...", 40),
            ("Syncing cluster state...", 60),
            ("Registering with cluster...", 80),
            ("Successfully joined cluster!", 100),
        ]
        
        for message, progress in steps:
            await manager.send_personal(websocket, {
                "type": "join_progress",
                "progress": progress,
                "message": message,
                "timestamp": time.time(),
            })
            
            await manager.broadcast({
                "type": "log",
                "level": "info",
                "message": message,
                "timestamp": time.time(),
            })
            
            await asyncio.sleep(0.6)
        
        await manager.broadcast({
            "type": "node_added",
            "node": node.dict(),
            "timestamp": time.time(),
        })
        
        await manager.broadcast({
            "type": "log",
            "level": "success",
            "message": f"Node '{node_name}' successfully joined the cluster",
            "timestamp": time.time(),
        })
    
    elif msg_type == "start_transfer":
        # Start a file transfer
        filename = data.get("filename", "data.bin")
        size_mb = data.get("size_mb", 100)
        
        transfer_id = str(uuid.uuid4())
        transfer = TransferProgress(
            id=transfer_id,
            filename=filename,
            size=f"{size_mb} MB",
            speed=50.0,  # MB/s
            percent=0.0,
            eta="calculating...",
            total_bytes=size_mb * 1024 * 1024,
            compression_ratio=0.0,
        )
        
        async with STATE_LOCK:
            CLUSTER_STATE["transfers"][transfer_id] = transfer
        
        await manager.broadcast({
            "type": "transfer_started",
            "transfer": transfer.dict(),
            "timestamp": time.time(),
        })
        
        await manager.broadcast({
            "type": "log",
            "level": "info",
            "message": f"Started transfer: {filename}",
            "timestamp": time.time(),
        })
    
    elif msg_type == "ping":
        # Respond to ping with pong
        await manager.send_personal(websocket, {
            "type": "pong",
            "timestamp": time.time(),
            "client_id": client_id,
        })
    
    elif msg_type == "request_stats":
        # Send current stats
        async with STATE_LOCK:
            await manager.send_personal(websocket, {
                "type": "cluster_stats",
                "timestamp": time.time(),
                "stats": CLUSTER_STATE["stats"].dict(),
            })


# Background tasks
background_tasks = []

def start_background_tasks():
    """Start all background tasks for cluster management"""
    tasks = [
        simulate_node_metrics(),
        simulate_transfer_progress(),
        update_cluster_stats(),
        heartbeat_handler(),
    ]
    for task in tasks:
        background_tasks.append(asyncio.create_task(task))


def stop_background_tasks():
    """Stop all background tasks"""
    for task in background_tasks:
        task.cancel()
    background_tasks.clear()