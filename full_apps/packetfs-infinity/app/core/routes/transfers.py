"""
Simplified transfers endpoint - PacketFS Arithmetic Mode ONLY
All legacy protocols removed - pure BREF-based transfers
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from fastapi import APIRouter, HTTPException
from app.core.schemas import TransferRequest, TransferStatus
from app.core.state import BLUEPRINTS, TRANSFERS

router = APIRouter()


@router.post("/transfers", response_model=TransferStatus)
async def start_transfer(req: TransferRequest):
    """
    Start a PacketFS arithmetic mode transfer
    ONLY supports IPROG with BREF-based PVRT transfers
    """
    # Get object and verify it has an IPROG
    obj = BLUEPRINTS.get(req.object_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    
    iprog = obj.get("iprog")
    if not iprog:
        raise HTTPException(status_code=400, detail="Object does not have IPROG (PacketFS arithmetic mode required)")
    
    # Generate transfer ID
    tid = hashlib.sha256((req.object_id + req.peer.host).encode()).hexdigest()[:16]
    
    # Get configuration
    import os
    WS_CHANNELS = int(os.environ.get("PFS_WS_CHANNELS", "10"))
    
    # Initialize transfer status
    status = TransferStatus(transfer_id=tid, state="running", details={})
    TRANSFERS[tid] = status
    
    # Metrics
    object_size = int(iprog.get("size", 0))
    t0 = time.time()
    
    async def _run_transfer():
        """Execute the PacketFS arithmetic transfer"""
        try:
            from app.services.transports.ws_proxy import send_iprog_ws_multi
            
            windows = iprog.get("windows", [])
            ws_port = req.peer.ws_port or req.peer.https_port
            
            # Always use multi-channel for optimal performance
            res = await send_iprog_ws_multi(
                req.peer.host, 
                ws_port, 
                iprog, 
                tid, 
                channels=WS_CHANNELS
            )
            
            ok = bool(res.get("ok"))
            bytes_sent = int(res.get("bytes_sent", 0))
            elapsed = time.time() - t0
            
            if ok and bytes_sent > 0:
                # Calculate metrics
                compression_ratio = 1 - (bytes_sent / object_size) if object_size > 0 else 0
                speedup = object_size / bytes_sent if bytes_sent > 0 else 1
                throughput_mbps = (object_size / elapsed) / (1024 * 1024) if elapsed > 0 else 0
                
                status.details = {
                    "object_size": object_size,
                    "bytes_sent": bytes_sent,
                    "compression_ratio": compression_ratio,
                    "speedup": speedup,
                    "elapsed_s": elapsed,
                    "throughput_mbps": throughput_mbps,
                    "channels": WS_CHANNELS,
                    "windows": len(windows),
                    "protocol": "PACKETFS_ARITHMETIC_BREF"
                }
                status.state = "success"
            else:
                status.state = "failed"
                status.details = {"error": "Transfer failed", "elapsed_s": elapsed}
                
        except Exception as e:
            status.state = "failed"
            status.details = {"error": str(e)}
    
    # Start transfer asynchronously
    asyncio.create_task(_run_transfer())
    
    return status


@router.get("/transfers/{transfer_id}", response_model=TransferStatus)
async def get_transfer(transfer_id: str):
    """Get transfer status"""
    status = TRANSFERS.get(transfer_id)
    if not status:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return status


@router.get("/transfers/stats/summary")
async def get_transfer_stats():
    """Get overall transfer statistics"""
    total_transfers = len(TRANSFERS)
    successful = sum(1 for t in TRANSFERS.values() if t.state == "success")
    failed = sum(1 for t in TRANSFERS.values() if t.state == "failed")
    running = sum(1 for t in TRANSFERS.values() if t.state == "running")
    
    # Calculate averages from successful transfers
    avg_compression = 0
    avg_speedup = 0
    total_bytes_saved = 0
    
    successful_transfers = [t for t in TRANSFERS.values() if t.state == "success" and t.details]
    if successful_transfers:
        compressions = [t.details.get("compression_ratio", 0) for t in successful_transfers]
        speedups = [t.details.get("speedup", 1) for t in successful_transfers]
        
        avg_compression = sum(compressions) / len(compressions)
        avg_speedup = sum(speedups) / len(speedups)
        
        for t in successful_transfers:
            original = t.details.get("object_size", 0)
            sent = t.details.get("bytes_sent", 0)
            total_bytes_saved += (original - sent)
    
    return {
        "total_transfers": total_transfers,
        "successful": successful,
        "failed": failed,
        "running": running,
        "avg_compression_ratio": avg_compression,
        "avg_speedup": avg_speedup,
        "total_bytes_saved": total_bytes_saved,
        "protocol": "PACKETFS_ARITHMETIC_MODE"
    }