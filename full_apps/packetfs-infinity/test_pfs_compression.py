#!/usr/bin/env python3
"""
PacketFS Compression Demonstration
Shows the extreme compression achieved by PacketFS arithmetic mode
"""

import sys
import time
import json
import hashlib
from pathlib import Path
import requests
import urllib3

# Disable SSL warnings for self-signed cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_compression(filepath: str, server_url: str = "https://localhost:8811"):
    """Test PacketFS compression"""
    
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"[ERROR] File not found: {filepath}")
        return
    
    filesize = filepath.stat().st_size
    print("=" * 70)
    print(" " * 20 + "PACKETFS COMPRESSION TEST")
    print("=" * 70)
    print()
    print(f"Test File: {filepath.name}")
    print(f"Original Size: {filesize:,} bytes ({filesize/1024/1024:.2f} MB)")
    print()
    
    # Check server status
    print("[1] Server Status")
    print("-" * 40)
    try:
        resp = requests.get(f"{server_url}/blob/status", verify=False)
        if resp.status_code == 200:
            blob_info = resp.json()
            print(f"Blob Name: {blob_info.get('name')}")
            print(f"Blob Size: {blob_info.get('size', 0):,} bytes")
            print(f"Blob Seed: {blob_info.get('seed')}")
            print(f"Fill Status: {blob_info.get('fill', {}).get('status', 'unknown')}")
        else:
            print(f"Warning: Server returned {resp.status_code}")
    except Exception as e:
        print(f"Error: {e}")
        return
    
    # Upload file and create IPROG
    print()
    print("[2] PacketFS Compression")
    print("-" * 40)
    
    start = time.time()
    
    with open(filepath, 'rb') as f:
        files = {'file': (filepath.name, f, 'application/octet-stream')}
        resp = requests.post(f"{server_url}/objects", files=files, verify=False)
    
    upload_time = time.time() - start
    
    if resp.status_code != 200:
        print(f"Error: Upload failed with status {resp.status_code}")
        print(resp.text[:500])
        return
    
    result = resp.json()
    object_id = result.get('object_id')
    compressed_size = result.get('compressed_size', 0)
    tx_ratio = result.get('tx_ratio', 0)
    
    print(f"Object ID: {object_id}")
    print(f"Upload Time: {upload_time:.2f} seconds")
    print()
    print(f"Original Size: {filesize:,} bytes")
    print(f"Compressed Size: {compressed_size:,} bytes")
    print(f"Compression Ratio: {1 - tx_ratio:.2%}")
    print(f"Space Saved: {filesize - compressed_size:,} bytes")
    print()
    
    # Calculate speeds
    upload_speed = filesize / upload_time / 1024 / 1024
    
    if compressed_size > 0 and compressed_size < filesize:
        # Calculate theoretical transfer advantage
        typical_network_speed = 100  # MB/s typical gigabit ethernet
        raw_transfer_time = filesize / (typical_network_speed * 1024 * 1024)
        compressed_transfer_time = compressed_size / (typical_network_speed * 1024 * 1024)
        speedup = raw_transfer_time / compressed_transfer_time if compressed_transfer_time > 0 else 0
        
        print("[3] Performance Analysis")
        print("-" * 40)
        print(f"Upload Speed: {upload_speed:.1f} MB/s")
        print()
        print("For network transfer at 100 MB/s:")
        print(f"  Raw Transfer: {raw_transfer_time:.3f} seconds")
        print(f"  PFS Transfer: {compressed_transfer_time:.3f} seconds")
        print(f"  Speedup: {speedup:.1f}x faster")
        print()
    
    # Summary
    print("=" * 70)
    if tx_ratio > 0 and tx_ratio < 0.1:  # >90% compression
        print("*** SUCCESS: PACKETFS ARITHMETIC MODE ACHIEVED >90% COMPRESSION ***")
        print()
        print("This demonstrates PacketFS's ability to compress data by referencing")
        print("shared memory patterns instead of transmitting raw bytes.")
    elif tx_ratio > 0 and tx_ratio < 0.5:  # >50% compression
        print("*** GOOD: PacketFS achieved significant compression ***")
    else:
        print("*** PacketFS compression ratio: {:.1%} ***".format(1 - tx_ratio))
    print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_pfs_compression.py <file_path>")
        print()
        print("Examples:")
        print("  python test_pfs_compression.py /tmp/test_10mb.dat")
        print("  python test_pfs_compression.py /usr/bin/python3")
        sys.exit(1)
    
    filepath = sys.argv[1]
    test_compression(filepath)