#!/usr/bin/env python3
"""
Full PacketFS arithmetic mode test
Tests file compression to IPROG and transfer via WebSocket
"""

import sys
import time
import json
import asyncio
import aiofiles
import aiohttp
import ssl
import hashlib
import base64
from pathlib import Path

# Import PacketFS modules
sys.path.insert(0, '/home/punk/Projects/packetfs/src')
from packetfs.protocol import ProtocolEncoder, SyncConfig
from packetfs.filesystem.virtual_blob import VirtualBlob
from packetfs.filesystem.iprog import build_iprog_for_file_bytes

async def test_full_pfs(filepath: str, server_url: str = "https://localhost:8811"):
    """Test complete PacketFS flow"""
    
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"[ERROR] File not found: {filepath}")
        return
    
    filesize = filepath.stat().st_size
    print("=" * 60)
    print("PACKETFS ARITHMETIC MODE TEST")
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
            # Step 1: Check server and blob status
            print("[1] Checking server status...")
            async with session.get(f"{server_url}/blob/status") as resp:
                if resp.status == 200:
                    blob_info = await resp.json()
                    print(f"    Blob: {blob_info.get('name')} ({blob_info.get('size_mb')} MB)")
                    print(f"    Seed: {blob_info.get('seed')}")
                else:
                    print(f"    Warning: Could not get blob status (code {resp.status})")
            
            # Step 2: Create local IPROG using PacketFS encoder
            print("\n[2] Creating IPROG locally...")
            start_encode = time.time()
            
            # Initialize blob matching server config
            blob = VirtualBlob(
                name="pfs_vblob", 
                size_bytes=1073741824,  # 1GB
                seed=1337
            )
            
            # Read file data
            with open(filepath, 'rb') as f:
                file_data = f.read()
            
            # Build IPROG with arithmetic compression
            iprog = build_iprog_for_file_bytes(
                file_data, 
                blob,
                window_pow2=16,  # 2^16 = 65536 bytes
                embed_pvrt=True
            )
            
            encode_time = time.time() - start_encode
            iprog_size = len(json.dumps(iprog).encode())
            compression = 1 - (iprog_size / filesize)
            
            print(f"    IPROG created in {encode_time:.3f}s")
            print(f"    IPROG size: {iprog_size:,} bytes")
            print(f"    Compression: {compression:.1%}")
            print(f"    Windows: {len(iprog.get('windows', []))}")
            
            # Step 3: Upload file to server (creates server-side IPROG)
            print("\n[3] Uploading to server for IPROG creation...")
            start_upload = time.time()
            
            form = aiohttp.FormData()
            form.add_field('file', file_data, filename=filepath.name)
            
            async with session.post(f"{server_url}/objects", data=form) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    upload_time = time.time() - start_upload
                    print(f"    Upload completed in {upload_time:.2f}s")
                    print(f"    Object ID: {result.get('object_id')}")
                    print(f"    Server IPROG size: {result.get('iprog_size'):,} bytes")
                    print(f"    Server compression: {result.get('compression_ratio'):.1%}")
                    object_id = result.get('object_id')
                else:
                    print(f"    ERROR: Upload failed (code {resp.status})")
                    error = await resp.text()
                    print(f"    {error}")
                    return
            
            # Step 4: Trigger WebSocket transfer
            print("\n[4] Testing PacketFS WebSocket transfer...")
            print("    Method: Multi-channel arithmetic mode")
            start_transfer = time.time()
            
            transfer_request = {
                "object_id": object_id,
                "method": "pfs-arith",
                "channels": 5
            }
            
            async with session.post(f"{server_url}/transfers", json=transfer_request) as resp:
                if resp.status == 200:
                    transfer_result = await resp.json()
                    transfer_time = time.time() - start_transfer
                    bytes_sent = transfer_result.get('bytes_transferred', 0)
                    
                    print(f"    Transfer completed in {transfer_time:.2f}s")
                    print(f"    Bytes sent: {bytes_sent:,}")
                    if bytes_sent > 0:
                        actual_compression = 1 - (bytes_sent / filesize)
                        speed = filesize / transfer_time / 1024 / 1024
                        print(f"    Actual compression: {actual_compression:.1%}")
                        print(f"    Effective speed: {speed:.1f} MB/s")
                else:
                    print(f"    Warning: Transfer returned code {resp.status}")
                    msg = await resp.text()
                    print(f"    Response: {msg}")
            
            # Step 5: Summary
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            total_time = time.time() - start_encode
            print(f"Original file: {filesize:,} bytes")
            print(f"IPROG size: {iprog_size:,} bytes")
            print(f"Compression ratio: {compression:.1%}")
            print(f"Total time: {total_time:.2f}s")
            print(f"Overall throughput: {filesize / total_time / 1024 / 1024:.1f} MB/s")
            
            if compression > 0.9:
                print("\n*** PACKETFS ARITHMETIC MODE SUCCESS ***")
                print("Achieved >90% compression using blob references!")
            
        except aiohttp.ClientError as e:
            print(f"\n[ERROR] Connection failed: {e}")
            print("Make sure the server is running:")
            print("  cd /home/punk/Projects/packetfs/full_apps/packetfs-infinity")
            print("  ./run-container.sh")
        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_full_pfs.py <file_path>")
        print("\nExample:")
        print("  python test_full_pfs.py /tmp/test_10mb.dat")
        sys.exit(1)
    
    filepath = sys.argv[1]
    asyncio.run(test_full_pfs(filepath))