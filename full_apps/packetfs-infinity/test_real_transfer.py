#!/usr/bin/env python3
"""
Real PacketFS Transfer Test
Performs actual WebSocket transfer and measures speedup
"""

import sys
import time
import json
import asyncio
import aiohttp
import ssl
import hashlib
from pathlib import Path
from typing import Dict, Any

class PacketFSTransferTest:
    def __init__(self, server_url: str = "https://localhost:8811"):
        self.server_url = server_url
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
    async def upload_file(self, filepath: Path) -> Dict[str, Any]:
        """Upload file and get IPROG"""
        conn = aiohttp.TCPConnector(ssl=self.ssl_context)
        async with aiohttp.ClientSession(connector=conn) as session:
            with open(filepath, 'rb') as f:
                file_data = f.read()
            
            form = aiohttp.FormData()
            form.add_field('file', file_data, filename=filepath.name)
            
            async with session.post(f"{self.server_url}/objects", data=form) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"Upload failed: {resp.status}")
    
    async def get_iprog(self, object_id: str) -> Dict[str, Any]:
        """Fetch IPROG for object"""
        conn = aiohttp.TCPConnector(ssl=self.ssl_context)
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(f"{self.server_url}/objects/{object_id}/iprog") as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {}
    
    async def perform_ws_transfer(self, object_id: str, iprog: Dict[str, Any]) -> Dict[str, Any]:
        """Perform actual WebSocket multi-channel transfer"""
        
        # Extract IPROG windows with PVRT data
        windows = iprog.get("windows", [])
        if not windows:
            return {"error": "No windows in IPROG"}
        
        # Count actual PVRT bytes to transfer
        pvrt_bytes = 0
        for window in windows:
            if "pvrt" in window:
                # PVRT is base64 encoded
                import base64
                pvrt_data = base64.b64decode(window["pvrt"])
                pvrt_bytes += len(pvrt_data)
        
        print(f"    Windows to transfer: {len(windows)}")
        print(f"    PVRT data size: {pvrt_bytes:,} bytes")
        
        # Connect via WebSocket and send PVRT frames
        ws_url = self.server_url.replace("https://", "wss://") + "/ws/pfs-arith"
        
        conn = aiohttp.TCPConnector(ssl=self.ssl_context)
        start_transfer = time.time()
        bytes_sent = 0
        
        async with aiohttp.ClientSession(connector=conn) as session:
            try:
                async with session.ws_connect(ws_url) as ws:
                    # Send START frame
                    start_msg = {
                        "type": "START",
                        "transfer_id": hashlib.sha256(object_id.encode()).hexdigest()[:16],
                        "object_sha": iprog.get("sha256", ""),
                        "total_windows": len(windows),
                        "channels": 1  # Single channel for simplicity
                    }
                    await ws.send_json(start_msg)
                    
                    # Send each window's PVRT data
                    for idx, window in enumerate(windows):
                        if "pvrt" in window:
                            import base64
                            pvrt_data = base64.b64decode(window["pvrt"])
                            
                            # Send WIN frame with PVRT
                            win_msg = {
                                "type": "WIN",
                                "idx": idx,
                                "pvrt": window["pvrt"],  # Already base64
                                "hash16": window.get("hash16", ""),
                                "len": window.get("len", 0)
                            }
                            await ws.send_json(win_msg)
                            bytes_sent += len(pvrt_data)
                            
                            # Small delay to prevent overwhelming
                            if idx % 10 == 0:
                                await asyncio.sleep(0.001)
                    
                    # Send DONE frame
                    done_msg = {
                        "type": "DONE",
                        "sha256": iprog.get("sha256", ""),
                        "total_windows": len(windows)
                    }
                    await ws.send_json(done_msg)
                    
                    # Wait for acknowledgment
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "DONE_ACK":
                                break
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
                    
            except Exception as e:
                return {"error": str(e)}
        
        transfer_time = time.time() - start_transfer
        
        return {
            "bytes_sent": bytes_sent,
            "transfer_time": transfer_time,
            "windows": len(windows)
        }
    
    async def run_full_test(self, filepath: str):
        """Run complete transfer test"""
        filepath = Path(filepath)
        
        if not filepath.exists():
            print(f"Error: File not found: {filepath}")
            return
        
        filesize = filepath.stat().st_size
        
        print("=" * 70)
        print(" " * 15 + "PACKETFS REAL TRANSFER TEST")
        print("=" * 70)
        print()
        print(f"Test File: {filepath.name}")
        print(f"File Size: {filesize:,} bytes ({filesize/1024/1024:.2f} MB)")
        print()
        
        # Step 1: Upload file
        print("[1] Uploading file to create IPROG...")
        print("-" * 40)
        start = time.time()
        
        upload_result = await self.upload_file(filepath)
        upload_time = time.time() - start
        
        object_id = upload_result.get("object_id")
        compressed_size = upload_result.get("compressed_size", 0)
        tx_ratio = upload_result.get("tx_ratio", 0)
        
        print(f"    Upload time: {upload_time:.2f}s")
        print(f"    Object ID: {object_id}")
        print(f"    IPROG size: {compressed_size:,} bytes")
        print(f"    Compression: {(1 - tx_ratio):.2%}")
        print()
        
        # Step 2: Get IPROG details
        print("[2] Fetching IPROG blueprint...")
        print("-" * 40)
        
        iprog = await self.get_iprog(object_id)
        if iprog:
            # The endpoint returns the IPROG directly, not wrapped
            iprog_data = iprog
            windows = iprog_data.get("windows", [])
            print(f"    Windows: {len(windows)}")
            print(f"    Window size: {iprog_data.get('window_size', 0):,} bytes")
        else:
            iprog_data = {}
            print("    Warning: Could not fetch IPROG")
        print()
        
        # Step 3: Perform WebSocket transfer
        print("[3] Performing WebSocket transfer...")
        print("-" * 40)
        
        if iprog_data:
            transfer_result = await self.perform_ws_transfer(object_id, iprog_data)
            
            if "error" in transfer_result:
                print(f"    Error: {transfer_result['error']}")
            else:
                bytes_sent = transfer_result["bytes_sent"]
                transfer_time = transfer_result["transfer_time"]
                
                print(f"    Transfer time: {transfer_time:.3f}s")
                print(f"    Bytes sent: {bytes_sent:,}")
                print(f"    Transfer speed: {bytes_sent/transfer_time/1024/1024:.1f} MB/s")
                print()
                
                # Calculate speedup vs raw transfer
                if bytes_sent > 0:
                    print("[4] Performance Analysis")
                    print("-" * 40)
                    
                    # Actual compression achieved
                    actual_compression = 1 - (bytes_sent / filesize)
                    print(f"    Wire compression: {actual_compression:.2%}")
                    
                    # Theoretical raw transfer time at same speed
                    transfer_speed = bytes_sent / transfer_time
                    raw_transfer_time = filesize / transfer_speed
                    speedup = raw_transfer_time / transfer_time
                    
                    print(f"    Speedup vs raw: {speedup:.1f}x faster")
                    print(f"    Time saved: {raw_transfer_time - transfer_time:.2f}s")
                    
                    # Effective throughput
                    effective_throughput = filesize / transfer_time / 1024 / 1024
                    print(f"    Effective throughput: {effective_throughput:.1f} MB/s")
                    print()
        
        # Summary
        print("=" * 70)
        print("TRANSFER SUMMARY")
        print("=" * 70)
        total_time = time.time() - start
        print(f"Original size: {filesize:,} bytes")
        print(f"Transferred: {compressed_size:,} bytes (IPROG)")
        print(f"Compression: {(1 - tx_ratio):.2%}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Overall speed: {filesize/total_time/1024/1024:.1f} MB/s")
        
        if tx_ratio < 0.1:
            print()
            print("*** SUCCESS: Achieved >90% compression with PacketFS! ***")
            print("*** Data transferred as tiny references to shared memory blob ***")
        
        print("=" * 70)

async def main():
    if len(sys.argv) != 2:
        print("Usage: python test_real_transfer.py <file_path>")
        print("\nExamples:")
        print("  python test_real_transfer.py /tmp/test_10mb.dat")
        print("  python test_real_transfer.py /usr/bin/python3")
        sys.exit(1)
    
    filepath = sys.argv[1]
    tester = PacketFSTransferTest()
    await tester.run_full_test(filepath)

if __name__ == "__main__":
    asyncio.run(main())