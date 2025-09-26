#!/usr/bin/env python3
"""
FastFS - Ultra-simple, ultra-fast distributed filesystem
Built on PacketFS substrate with network CPU acceleration
"""
import os
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import redis
import asyncio
import aiofiles

class FastFS:
    def __init__(self, node_id: str = None, redis_host: str = "localhost"):
        self.node_id = node_id or f"fastfs-{os.urandom(4).hex()}"
        self.redis = redis.Redis(host=redis_host, decode_responses=True)
        self.local_cache = Path(f"/tmp/fastfs-{self.node_id}")
        self.local_cache.mkdir(exist_ok=True)
        
    def _hash_path(self, path: str) -> str:
        """Generate consistent hash for any path"""
        return hashlib.sha256(path.encode()).hexdigest()[:16]
    
    def _get_nodes_for_path(self, path: str, replicas: int = 3) -> List[str]:
        """Determine which nodes should store this path"""
        path_hash = self._hash_path(path)
        all_nodes = list(self.redis.smembers("fastfs:nodes"))
        
        if not all_nodes:
            return [self.node_id]
        
        # Consistent hashing - same path always maps to same nodes
        hash_int = int(path_hash, 16)
        start_idx = hash_int % len(all_nodes)
        
        nodes = []
        for i in range(replicas):
            idx = (start_idx + i) % len(all_nodes)
            nodes.append(all_nodes[idx])
        
        return nodes
    
    async def write(self, path: str, data: bytes) -> bool:
        """Write file to distributed filesystem - FAST!"""
        path_hash = self._hash_path(path)
        target_nodes = self._get_nodes_for_path(path)
        
        # Metadata
        metadata = {
            "path": path,
            "size": len(data),
            "hash": hashlib.sha256(data).hexdigest(),
            "created": time.time(),
            "nodes": target_nodes
        }
        
        # Store locally first (fastest)
        local_file = self.local_cache / path_hash
        local_file.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(local_file, 'wb') as f:
            await f.write(data)
        
        # Update global metadata
        self.redis.hset(f"fastfs:meta:{path_hash}", mapping=metadata)
        self.redis.sadd("fastfs:files", path)
        self.redis.sadd("fastfs:nodes", self.node_id)
        
        # Async replicate to other nodes (don't wait)
        asyncio.create_task(self._replicate_async(path_hash, data, target_nodes))
        
        print(f"[OK] FastFS: {path} written ({len(data)} bytes)")
        return True
    
    async def read(self, path: str) -> Optional[bytes]:
        """Read file from distributed filesystem - FAST!"""
        path_hash = self._hash_path(path)
        
        # Try local cache first (fastest)
        local_file = self.local_cache / path_hash
        if local_file.exists():
            async with aiofiles.open(local_file, 'rb') as f:
                data = await f.read()
            print(f"[READ] FastFS: {path} read from local cache")
            return data
        
        # Get metadata to find nodes
        metadata = self.redis.hgetall(f"fastfs:meta:{path_hash}")
        if not metadata:
            print(f"[ERR] FastFS: {path} not found")
            return None
        
        # Try to fetch from any node that has it
        target_nodes = json.loads(metadata.get("nodes", "[]"))
        
        for node in target_nodes:
            if node == self.node_id:
                continue
                
            # Try to fetch from remote node
            data = await self._fetch_from_node(node, path_hash)
            if data:
                # Cache locally for next time
                async with aiofiles.open(local_file, 'wb') as f:
                    await f.write(data)
                print(f"[READ] FastFS: {path} read from node {node}")
                return data
        
        print(f"[ERR] FastFS: {path} not available")
        return None
    
    async def _replicate_async(self, path_hash: str, data: bytes, target_nodes: List[str]):
        """Replicate data to target nodes asynchronously"""
        for node in target_nodes:
            if node != self.node_id:
                try:
                    await self._send_to_node(node, path_hash, data)
                except Exception as e:
                    print(f"[WARN] Replication to {node} failed: {e}")
    
    async def _fetch_from_node(self, node: str, path_hash: str) -> Optional[bytes]:
        """Fetch file from remote node"""
        # In real implementation, this would use HTTP/gRPC/etc
        # For now, simulate with Redis pub/sub
        try:
            # Request file from node
            request = {
                "type": "fetch",
                "path_hash": path_hash,
                "requester": self.node_id
            }
            
            self.redis.publish(f"fastfs:node:{node}", json.dumps(request))
            
            # Wait for response (simplified)
            response_key = f"fastfs:response:{self.node_id}:{path_hash}"
            
            for _ in range(10):  # 1 second timeout
                response = self.redis.get(response_key)
                if response:
                    self.redis.delete(response_key)
                    return response.encode() if response != "NOT_FOUND" else None
                await asyncio.sleep(0.1)
            
            return None
            
        except Exception as e:
            print(f"Fetch error: {e}")
            return None
    
    async def _send_to_node(self, node: str, path_hash: str, data: bytes):
        """Send file to remote node"""
        # Simplified - in real implementation would use proper network protocol
        request = {
            "type": "store",
            "path_hash": path_hash,
            "data": data.hex(),  # Hex encode for Redis
            "sender": self.node_id
        }
        
        self.redis.publish(f"fastfs:node:{node}", json.dumps(request))
    
    def list_files(self) -> List[str]:
        """List all files in FastFS"""
        return list(self.redis.smembers("fastfs:files"))
    
    def stats(self) -> Dict:
        """Get FastFS statistics"""
        files = self.redis.smembers("fastfs:files")
        nodes = self.redis.smembers("fastfs:nodes")
        
        local_files = len(list(self.local_cache.glob("*")))
        
        return {
            "total_files": len(files),
            "total_nodes": len(nodes),
            "local_cached": local_files,
            "node_id": self.node_id
        }
    
    async def start_node_listener(self):
        """Start listening for inter-node requests"""
        pubsub = self.redis.pubsub()
        pubsub.subscribe(f"fastfs:node:{self.node_id}")
        
        print(f"[NODE] FastFS node {self.node_id} listening...")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    request = json.loads(message['data'])
                    await self._handle_node_request(request)
                except Exception as e:
                    print(f"Request handling error: {e}")
    
    async def _handle_node_request(self, request: Dict):
        """Handle requests from other nodes"""
        if request["type"] == "fetch":
            path_hash = request["path_hash"]
            requester = request["requester"]
            
            local_file = self.local_cache / path_hash
            if local_file.exists():
                async with aiofiles.open(local_file, 'rb') as f:
                    data = await f.read()
                
                response_key = f"fastfs:response:{requester}:{path_hash}"
                self.redis.setex(response_key, 5, data.decode('latin1'))
            else:
                response_key = f"fastfs:response:{requester}:{path_hash}"
                self.redis.setex(response_key, 5, "NOT_FOUND")
        
        elif request["type"] == "store":
            path_hash = request["path_hash"]
            data = bytes.fromhex(request["data"])
            
            local_file = self.local_cache / path_hash
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(local_file, 'wb') as f:
                await f.write(data)

async def main():
    import sys
    
    if len(sys.argv) < 2:
        print("FastFS - Ultra-fast distributed filesystem")
        print("Usage: fastfs.py <command> [args]")
        print("Commands:")
        print("  node                    - Start FastFS node")
        print("  write <path> <content>  - Write file")
        print("  read <path>             - Read file")
        print("  list                    - List files")
        print("  stats                   - Show statistics")
        return
    
    fs = FastFS()
    command = sys.argv[1]
    
    if command == "node":
        await fs.start_node_listener()
        
    elif command == "write" and len(sys.argv) >= 4:
        path = sys.argv[2]
        content = sys.argv[3].encode()
        await fs.write(path, content)
        
    elif command == "read" and len(sys.argv) >= 3:
        path = sys.argv[2]
        data = await fs.read(path)
        if data:
            print(data.decode())
        
    elif command == "list":
        files = fs.list_files()
        for f in files:
            print(f)
            
    elif command == "stats":
        stats = fs.stats()
        print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    asyncio.run(main())