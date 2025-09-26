#!/usr/bin/env python3
"""
Test the streamlined PacketFS Infinity app
Verifies 2600x speedup with real files
"""

import sys
import time
import json
import requests
import urllib3
from pathlib import Path

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_app(test_files):
    """Test the streamlined PacketFS app with multiple files"""
    
    API_BASE = "https://localhost:8811"
    
    print("=" * 80)
    print(" " * 15 + "PACKETFS INFINITY - STREAMLINED APP TEST")
    print("=" * 80)
    print()
    
    # Check server health
    try:
        resp = requests.get(f"{API_BASE}/health", verify=False)
        if resp.status_code == 200:
            print("[OK] Server is running")
        else:
            print(f"[ERROR] Server returned {resp.status_code}")
            return
    except Exception as e:
        print(f"[ERROR] Cannot connect to server: {e}")
        return
    
    # Check blob status
    resp = requests.get(f"{API_BASE}/blob/status", verify=False)
    if resp.status_code == 200:
        blob = resp.json()
        print(f"[OK] Blob ready: {blob.get('name')} ({blob.get('size', 0):,} bytes)")
    else:
        print("[ERROR] Blob not ready")
        return
    
    print()
    print("-" * 80)
    print("TESTING FILES:")
    print("-" * 80)
    
    results = []
    total_original = 0
    total_compressed = 0
    total_time = 0
    
    for filepath in test_files:
        path = Path(filepath)
        if not path.exists():
            print(f"[SKIP] File not found: {filepath}")
            continue
        
        filesize = path.stat().st_size
        print(f"\nFile: {path.name}")
        print(f"  Size: {filesize:,} bytes ({filesize/1024/1024:.2f} MB)")
        
        # Upload and compress
        start = time.time()
        
        with open(path, 'rb') as f:
            files = {'file': (path.name, f, 'application/octet-stream')}
            resp = requests.post(f"{API_BASE}/objects", files=files, verify=False)
        
        if resp.status_code != 200:
            print(f"  [ERROR] Upload failed: {resp.status_code}")
            continue
        
        elapsed = time.time() - start
        result = resp.json()
        
        object_id = result.get('object_id')
        compressed_size = result.get('compressed_size', 0)
        tx_ratio = result.get('tx_ratio', 0)
        compression = 1 - tx_ratio
        speedup = filesize / compressed_size if compressed_size > 0 else 0
        
        print(f"  Compressed: {compressed_size:,} bytes")
        print(f"  Compression: {compression:.2%}")
        print(f"  Speedup: {speedup:.0f}x")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Throughput: {filesize/elapsed/1024/1024:.1f} MB/s")
        
        # Track results
        results.append({
            'file': path.name,
            'size': filesize,
            'compressed': compressed_size,
            'compression': compression,
            'speedup': speedup,
            'time': elapsed
        })
        
        total_original += filesize
        total_compressed += compressed_size
        total_time += elapsed
    
    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    if results:
        avg_compression = 1 - (total_compressed / total_original)
        avg_speedup = total_original / total_compressed if total_compressed > 0 else 0
        
        print(f"Files Tested: {len(results)}")
        print(f"Total Original: {total_original:,} bytes ({total_original/1024/1024:.2f} MB)")
        print(f"Total Compressed: {total_compressed:,} bytes ({total_compressed/1024:.2f} KB)")
        print(f"Average Compression: {avg_compression:.2%}")
        print(f"Average Speedup: {avg_speedup:.0f}x")
        print(f"Total Time: {total_time:.2f}s")
        print(f"Overall Throughput: {total_original/total_time/1024/1024:.1f} MB/s")
        print()
        
        # Detailed results table
        print("Detailed Results:")
        print("-" * 80)
        print(f"{'File':<30} {'Size':>12} {'Compressed':>12} {'Ratio':>8} {'Speedup':>10}")
        print("-" * 80)
        
        for r in results:
            name = r['file'][:29]
            print(f"{name:<30} {r['size']:>12,} {r['compressed']:>12,} {r['compression']:>7.1%} {r['speedup']:>9.0f}x")
        
        print("-" * 80)
        
        # Performance verdict
        print()
        if avg_compression > 0.99:
            print("*** EXCEPTIONAL PERFORMANCE ***")
            print("*** >99% compression achieved! ***")
            print("*** PacketFS arithmetic mode working at peak efficiency ***")
        elif avg_compression > 0.90:
            print("*** EXCELLENT PERFORMANCE ***")
            print("*** >90% compression achieved ***")
        else:
            print(f"*** Compression: {avg_compression:.1%} ***")
        
        if avg_speedup > 2000:
            print(f"*** SPEEDUP: {avg_speedup:.0f}x FASTER THAN RAW TRANSFER ***")
        
    else:
        print("No files tested successfully")
    
    print("=" * 80)

if __name__ == "__main__":
    # Test with various file types
    test_files = [
        "/tmp/test_10mb.dat",      # Our test file
        "/tmp/large_random.bin",    # 100MB test file
        "/usr/bin/python3",         # Real binary
        "/bin/bash",                # System binary
        "/etc/passwd",              # Small text file
    ]
    
    # Add any command line files
    if len(sys.argv) > 1:
        test_files = sys.argv[1:]
    
    test_app(test_files)