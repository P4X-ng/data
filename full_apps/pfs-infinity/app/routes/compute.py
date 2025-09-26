"""
Compute endpoint for PacketFS vCPU operations
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import httpx
import time
import hashlib

router = APIRouter()

class Instruction(BaseModel):
    op: str
    offset: int = 0
    length: int = 1048576
    imm: int = 0

class ComputeRequest(BaseModel):
    data_url: str
    instructions: List[Instruction]
    window: Optional[Dict] = None

@router.post("/compute")
async def compute(request: ComputeRequest):
    """Execute packet-based computation (vCPU endpoint)"""
    start_time = time.time()
    
    try:
        # Fetch data with Range support
        headers = {}
        if request.window:
            range_end = request.window['offset'] + request.window['length'] - 1
            headers['Range'] = f"bytes={request.window['offset']}-{range_end}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(request.data_url, headers=headers, timeout=30.0)
            data = response.content
        
        # Execute instructions
        results = []
        total_bytes = 0
        
        for inst in request.instructions:
            offset = inst.offset
            length = min(inst.length, len(data) - offset)
            slice_data = data[offset:offset + length]
            
            if inst.op == "counteq":
                count = sum(1 for b in slice_data if b == inst.imm)
                results.append({"op": inst.op, "count": count, "bytes_scanned": length})
            
            elif inst.op == "xor":
                xored = bytes(b ^ inst.imm for b in slice_data)
                checksum = sum(xored) & 0xFFFFFFFF
                results.append({"op": inst.op, "checksum": checksum, "bytes_processed": length})
            
            elif inst.op == "add":
                added = bytes((b + inst.imm) & 0xFF for b in slice_data)
                checksum = sum(added) & 0xFFFFFFFF
                results.append({"op": inst.op, "checksum": checksum, "bytes_processed": length})
            
            elif inst.op == "fnv":
                h = 0x811c9dc5
                for b in slice_data:
                    h ^= b
                    h = (h * 0x01000193) & 0xFFFFFFFF
                results.append({"op": inst.op, "hash": h, "bytes_hashed": length})
            
            elif inst.op == "crc32":
                # Simple CRC32 (not optimized)
                crc = 0xFFFFFFFF
                for b in slice_data:
                    crc ^= b
                    for _ in range(8):
                        crc = (crc >> 1) ^ (0xEDB88320 & -(crc & 1))
                crc = crc ^ 0xFFFFFFFF
                results.append({"op": inst.op, "crc": crc & 0xFFFFFFFF, "bytes_processed": length})
            
            else:
                results.append({"op": inst.op, "error": f"Unknown operation: {inst.op}"})
            
            total_bytes += length
        
        elapsed_ms = (time.time() - start_time) * 1000
        throughput_mbps = (total_bytes / 1048576) / (elapsed_ms / 1000) if elapsed_ms > 0 else 0
        
        return {
            "vcpu_id": "container-001",
            "type": "local-container", 
            "results": results,
            "metrics": {
                "elapsed_ms": round(elapsed_ms, 2),
                "bytes_processed": total_bytes,
                "throughput_mbps": round(throughput_mbps, 2),
                "cache_hit": False  # Local doesn't have CDN cache
            },
            "packet_flow": {
                "receiver": "container-001",
                "network_is_cpu": True
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))