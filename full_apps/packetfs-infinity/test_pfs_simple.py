#!/usr/bin/env python3
"""
Simple PacketFS transfer test
Tests uploading a file and transferring via arithmetic WebSocket
"""

import sys
import time
import json
import asyncio
import aiohttp
import ssl
from pathlib import Path

async def test_pfs_simple(filepath: str, server_url: str = "https://localhost:8811"):
    """Simple test of PacketFS transfer flow"""
    
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"[ERROR] File not found: {filepath}")
        return
    
    filesize = filepath.stat().st_size
    print("=" * 60)
    print("PACKETFS TRANSFER TEST")
    print("=" * 60)
    print(f"File: {filepath.name}")
    print(f"Size: {filesize:,} bytes ({filesize/1024/1024:.2f} MB)")
    print()
    
    # Create SSL context for self-signed cert
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    conn = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=conn) as session:
        try:
            # Step 1: Check server status
            print("[1] Checking server...")
            async with session.get(f"{server_url}/blob/status") as resp:
                if resp.status == 200:
                    blob_info = await resp.json()
                    print(f"    OK - Blob: {blob_info.get('name', 'unknown')}")
                    print(f"    Size: {blob_info.get('size_mb', 0)} MB")
                    print(f"    Seed: {blob_info.get('seed', 0)}")
                else:
                    print(f"    Warning: Server returned {resp.status}")
            
            # Step 2: Upload file to create IPROG
            print("\n[2] Uploading file...")
            start_upload = time.time()
            
            with open(filepath, 'rb') as f:
                file_data = f.read()
            
            form = aiohttp.FormData()
            form.add_field('file', file_data, filename=filepath.name)
            
            async with session.post(f"{server_url}/objects", data=form) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    upload_time = time.time() - start_upload
                    object_id = result.get('object_id')
                    # The API returns 'compressed_size' not 'iprog_size'
                    iprog_size = result.get('compressed_size', 0)
                    tx_ratio = result.get('tx_ratio', 0)
                    
                    print(f"    Upload: {upload_time:.2f}s")
                    print(f"    Object ID: {object_id}")
                    print(f"    IPROG size: {iprog_size:,} bytes")
                    
                    if iprog_size > 0:
                        actual_ratio = 1 - (iprog_size / filesize)
                        print(f"    Compression: {actual_ratio:.1%}")
                    elif tx_ratio > 0:
                        print(f"    Compression: {1 - tx_ratio:.1%}")
                else:
                    print(f"    ERROR: Upload failed ({resp.status})")
                    error = await resp.text()
                    print(f"    {error[:200]}")
                    return
            
            # Step 3: Transfer via WebSocket
            print("\n[3] Testing PacketFS WebSocket transfer...")
            start_transfer = time.time()
            
            # Request transfer with multi-channel arithmetic mode
            transfer_req = {
                "object_id": object_id,
                "mode": "ws-multi",  # Multi-channel WebSocket mode
                "peer": {
                    "host": "localhost",
                    "https_port": 8811,
                    "ws_port": 8811
                },
                "timeout_s": 10.0
            }
            
            async with session.post(f"{server_url}/transfers", json=transfer_req) as resp:
                transfer_time = time.time() - start_transfer
                
                if resp.status == 200:
                    result = await resp.json()
                    bytes_transferred = result.get('bytes_transferred', 0)
                    speed_mbps = result.get('speed_mbps', 0)
                    
                    print(f"    Transfer time: {transfer_time:.2f}s")
                    print(f"    Bytes sent: {bytes_transferred:,}")
                    
                    if bytes_transferred > 0:
                        wire_ratio = 1 - (bytes_transferred / filesize)
                        actual_speed = filesize / transfer_time / 1024 / 1024
                        print(f"    Wire compression: {wire_ratio:.1%}")
                        print(f"    Speed: {actual_speed:.1f} MB/s")
                        
                        if wire_ratio > 0.9:
                            print("\n    >>> SUCCESS: Achieved >90% compression!")
                    else:
                        print(f"    Speed: {speed_mbps:.1f} MB/s")
                else:
                    print(f"    Warning: Transfer returned {resp.status}")
                    msg = await resp.text()
                    print(f"    Response: {msg[:200]}")
            
            # Summary
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            total_time = time.time() - start_upload
            print(f"File size: {filesize:,} bytes")
            print(f"IPROG size: {iprog_size:,} bytes")
            print(f"Total time: {total_time:.2f}s")
            print(f"Throughput: {filesize / total_time / 1024 / 1024:.1f} MB/s")
            
            if iprog_size > 0 and iprog_size < filesize * 0.1:
                print("\n*** PacketFS arithmetic mode working correctly! ***")
            
        except aiohttp.ClientError as e:
            print(f"\n[ERROR] Connection failed: {e}")
            print("\nMake sure the server is running:")
            print("  cd /home/punk/Projects/packetfs/full_apps/packetfs-infinity")
            print("  ./run-container.sh")
        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_pfs_simple.py <file_path>")
        print("\nExample:")
        print("  python test_pfs_simple.py /tmp/test_10mb.dat")
        sys.exit(1)
    
    filepath = sys.argv[1]
    asyncio.run(test_pfs_simple(filepath))