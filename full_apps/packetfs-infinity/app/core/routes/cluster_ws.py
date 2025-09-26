from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Dict, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel


class NodeStatus(BaseModel):
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
    total_nodes: int = 0
    active_transfers: int = 0
    storage_used: float = 0.0
    throughput: float = 0.0
    cluster_health: str = "healthy"
    uptime_seconds: int = 0


CLUSTER_STATE = {
    "nodes": {},
    "transfers": {},
    "stats": ClusterStats(),
    "start_time": time.time(),
}

STATE_LOCK = asyncio.Lock()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, Dict] = {}

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_metadata[websocket] = {
            "id": client_id or str(uuid.uuid4()),
            "connected_at": time.time(),
            "last_ping": time.time(),
        }
        await self.send_initial_state(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.connection_metadata.pop(websocket, None)

    async def send_initial_state(self, websocket: WebSocket):
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
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)


manager = ConnectionManager()


async def simulate_node_metrics():
    while True:
        async with STATE_LOCK:
            for node_id, node in CLUSTER_STATE["nodes"].items():
                node.cpu = max(0, min(100, node.cpu + (asyncio.create_task.__hash__() % 11 - 5) * 0.5))
                node.memory = max(0, min(100, node.memory + (asyncio.create_task.__hash__() % 11 - 5) * 0.3))
                node.storage = max(0, min(1000, node.storage + (asyncio.create_task.__hash__() % 3 - 1) * 0.1))
                node.last_seen = time.time()
                node.latency_ms = 5 + (asyncio.create_task.__hash__() % 20)
        await manager.broadcast({
            "type": "nodes_update",
            "timestamp": time.time(),
            "nodes": [node.dict() for node in CLUSTER_STATE["nodes"].values()],
        })
        await asyncio.sleep(2)


async def simulate_transfer_progress():
    while True:
        async with STATE_LOCK:
            completed = []
            for transfer_id, transfer in CLUSTER_STATE["transfers"].items():
                if transfer.percent < 100:
                    speed_variance = (asyncio.create_task.__hash__() % 21 - 10) * 0.1
                    transfer.speed = max(10, transfer.speed + speed_variance)
                    progress_increment = transfer.speed / 10
                    transfer.percent = min(100, transfer.percent + progress_increment)
                    transfer.bytes_transferred = int(transfer.total_bytes * transfer.percent / 100)
                    if transfer.speed > 0:
                        remaining_bytes = transfer.total_bytes - transfer.bytes_transferred
                        eta_seconds = remaining_bytes / (transfer.speed * 1024 * 1024)
                        transfer.eta = f"{int(eta_seconds)}s"
                    transfer.compression_ratio = 0.3 + (asyncio.create_task.__hash__() % 40) / 100
                    await manager.broadcast({
                        "type": "transfer_progress",
                        "timestamp": time.time(),
                        "progress": transfer.dict(),
                    })
                else:
                    completed.append(transfer_id)
            for transfer_id in completed:
                del CLUSTER_STATE["transfers"][transfer_id]
                await manager.broadcast({
                    "type": "transfer_complete",
                    "timestamp": time.time(),
                    "transfer_id": transfer_id,
                })
        await asyncio.sleep(0.5)


async def update_cluster_stats():
    while True:
        async with STATE_LOCK:
            stats = CLUSTER_STATE["stats"]
            stats.total_nodes = len(CLUSTER_STATE["nodes"])
            stats.active_transfers = len(CLUSTER_STATE["transfers"])
            stats.storage_used = sum(node.storage for node in CLUSTER_STATE["nodes"].values())
            stats.throughput = sum(t.speed for t in CLUSTER_STATE["transfers"].values())
            stats.uptime_seconds = int(time.time() - CLUSTER_STATE["start_time"])
            unhealthy = sum(1 for n in CLUSTER_STATE["nodes"].values() if n.status != "healthy")
            if unhealthy == 0:
                stats.cluster_health = "healthy"
            elif unhealthy < stats.total_nodes / 2:
                stats.cluster_health = "warning"
            else:
                stats.cluster_health = "error"
        await manager.broadcast({
            "type": "cluster_stats",
            "timestamp": time.time(),
            "stats": CLUSTER_STATE["stats"].dict(),
        })
        await asyncio.sleep(3)


async def heartbeat_handler():
    while True:
        await manager.broadcast({"type": "heartbeat", "timestamp": time.time()})
        await asyncio.sleep(30)


def register_cluster_ws(app: FastAPI) -> None:
    @app.websocket("/ws/cluster")
    async def cluster_websocket(websocket: WebSocket):
        client_id = str(uuid.uuid4())
        await manager.connect(websocket, client_id)
        await manager.send_personal(websocket, {
            "type": "welcome",
            "timestamp": time.time(),
            "client_id": client_id,
            "message": "Connected to F3 Cluster Management",
        })
        await manager.broadcast({
            "type": "log",
            "level": "info",
            "message": f"New client connected: {client_id[:8]}...",
            "timestamp": time.time(),
        })
        try:
            while True:
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
    msg_type = data.get("type")
    if msg_type == "ping":
        await manager.send_personal(websocket, {"type": "pong", "timestamp": time.time(), "client_id": client_id})
    elif msg_type == "request_stats":
        async with STATE_LOCK:
            await manager.send_personal(websocket, {
                "type": "cluster_stats",
                "timestamp": time.time(),
                "stats": CLUSTER_STATE["stats"].dict(),
            })


background_tasks = []

def start_background_tasks():
    tasks = [
        simulate_node_metrics(),
        simulate_transfer_progress(),
        update_cluster_stats(),
        heartbeat_handler(),
    ]
    for task in tasks:
        background_tasks.append(asyncio.create_task(task))
