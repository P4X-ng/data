#!/usr/bin/env python3
"""
Test PacketFS arithmetic transfer via the HTTP API.
This script uploads a file to get an IPROG, then transfers it via WebSocket.
"""

import sys
import time
import json
import asyncio
import aiofiles
import aiohttp
import ssl
from pathlib import Path

async def test_pfs_transfer(filepath: str, server_url: str = "https://localhost:8811"):
    """Test PacketFS arithmetic transfer"""
    
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return
    
    filesize = filepath.stat().st_size
    print(f"📁 Testing with file: {filepath.name} ({filesize:,} bytes)")
    
    # Create SSL context that accepts self-signed certificates
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    conn = aiohttp.TCPConnector(ssl=ssl_context)
    
    async with aiohttp.ClientSession(connector=conn) as session:
        try:
            # Step 1: Check blob status
            print("\n1️⃣ Checking blob status...")
            async with session.get(f"{server_url}/blob/status") as resp:
                if resp.status == 200:
                    blob_info = await resp.json()
                    print(f"   ✓ Blob active: {blob_info.get('name')} ({blob_info.get('size_mb')} MB)")
                else:
                    print(f"   ⚠ Could not get blob status: {resp.status}")
            
            # Step 2: Upload file to create IPROG
            print("\n2️⃣ Uploading file to create IPROG...")
            start_upload = time.time()
            
            async with aiofiles.open(filepath, 'rb') as f:
                file_data = await f.read()
            
            form = aiohttp.FormData()
            form.add_field('file', file_data, filename=filepath.name)
            
            async with session.post(f"{server_url}/objects", data=form) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    upload_time = time.time() - start_upload
                    print(f"   ✓ IPROG created in {upload_time:.2f}s")
                    print(f"   • Object ID: {result.get('object_id')}")
                    print(f"   • IPROG size: {result.get('iprog_size'):,} bytes")
                    print(f"   • Compression: {result.get('compression_ratio'):.1%}")
                    
                    object_id = result.get('object_id')
                else:
                    print(f"   ❌ Upload failed: {resp.status}")
                    error = await resp.text()
                    print(f"   Error: {error}")
                    return
            
            # Step 3: Test WebSocket transfer
            print("\n3️⃣ Testing PacketFS arithmetic transfer via WebSocket...")
            print("   (This would normally use the /transfers endpoint)")
            
            # Try to trigger a transfer
            start_transfer = time.time()
            transfer_data = {
                "object_id": object_id,
                "method": "pfs-arith",
                "channels": 5
            }
            
            async with session.post(f"{server_url}/transfers", json=transfer_data) as resp:
                if resp.status == 200:
                    transfer_result = await resp.json()
                    transfer_time = time.time() - start_transfer
                    print(f"   ✓ Transfer completed in {transfer_time:.2f}s")
                    print(f"   • Transferred: {transfer_result.get('bytes_transferred'):,} bytes")
                    print(f"   • Speed: {transfer_result.get('speed_mbps'):.1f} MB/s")
                else:
                    print(f"   ⚠ Transfer endpoint returned: {resp.status}")
                    msg = await resp.text()
                    print(f"   Response: {msg}")
            
            # Step 4: Summary
            print("\n📊 Summary:")
            print(f"   • Original file: {filesize:,} bytes")
            print(f"   • Total time: {time.time() - start_upload:.2f}s")
            print(f"   • Effective speed: {filesize / (time.time() - start_upload) / 1024 / 1024:.1f} MB/s")
            
        except aiohttp.ClientError as e:
            print(f"❌ Connection error: {e}")
            print("   Make sure the server is running at https://localhost:8811")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_pfs_transfer.py <file_path>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    asyncio.run(test_pfs_transfer(filepath))