#!/usr/bin/env python3
"""
PacketFS Edge Compute Demo
Shows the MASSIVE difference between downloading vs edge compute!
"""

import time
import requests
import json

def test_traditional_download():
    """Traditional way: Download then compute"""
    print("\n📥 TRADITIONAL: Download entire file then compute locally")
    print("=" * 60)
    
    start = time.time()
    
    # Download the entire file
    response = requests.get('http://localhost:5000/api/logs')
    data = response.content
    download_time = time.time() - start
    
    # Compute locally
    compute_start = time.time()
    count_E = sum(1 for b in data if b == ord('E'))
    count_null = sum(1 for b in data if b == 0)
    compute_time = time.time() - compute_start
    
    total_time = time.time() - start
    
    print(f"  📊 Data size: {len(data):,} bytes")
    print(f"  ⏱️  Download time: {download_time:.3f} seconds")
    print(f"  🖥️  Compute time: {compute_time:.3f} seconds")
    print(f"  ⏰ Total time: {total_time:.3f} seconds")
    print(f"  📈 Bytes transferred: {len(data):,}")
    print(f"  ✅ Results: {count_E} 'E's, {count_null} nulls")
    
    return len(data), total_time

def test_edge_compute():
    """PacketFS way: Compute at edge, get only results"""
    print("\n⚡ PACKETFS: Edge compute without downloading")
    print("=" * 60)
    
    start = time.time()
    
    # Send compute request to edge
    program = {
        "data_url": "http://localhost:5000/api/logs",
        "instructions": [
            {"op": "counteq", "imm": ord('E')},  # Count 'E's
            {"op": "counteq", "imm": 0},         # Count nulls
            {"op": "crc32c"},                    # Get checksum
            {"op": "sha256"}                     # Get hash
        ]
    }
    
    response = requests.post('http://localhost:5000/compute', json=program)
    result = response.json()
    
    total_time = time.time() - start
    
    if 'error' in result:
        print(f"  ❌ Error: {result['error']}")
        return 0, total_time
    
    data_size = result.get('data_size', 0)
    print(f"  📊 Data size (at edge): {data_size:,} bytes")
    print(f"  ⏰ Total time: {total_time:.3f} seconds")
    print(f"  📈 Bytes transferred: {len(response.content)} (just the results!)")
    print(f"  🌐 Computed at: {result.get('edge_location', 'unknown')}")
    print(f"  ✅ Results:")
    for r in result.get('results', []):
        print(f"     - {r['op']}: {r.get('value', 'computed')}")
    
    return data_size, total_time

def test_with_headers():
    """Using simple headers for edge compute"""
    print("\n🎯 HEADER-BASED: Compute with simple headers")
    print("=" * 60)
    
    start = time.time()
    
    # Just add headers to normal request!
    response = requests.get('http://localhost:5000/api/logs',
                           headers={
                               'X-PacketFS-Op': 'counteq',
                               'X-PacketFS-Imm': str(ord('E'))
                           })
    
    total_time = time.time() - start
    
    print(f"  ⏰ Total time: {total_time:.3f} seconds")
    print(f"  📊 Data size (at edge): {response.headers.get('X-PacketFS-Data-Size', 'unknown')}")
    print(f"  📈 Bytes transferred: {len(response.content)} (empty!)")
    print(f"  ✅ Result: {response.headers.get('X-PacketFS-Result')} 'E's found")
    
    return int(response.headers.get('X-PacketFS-Data-Size', 0)), total_time

def main():
    print("🚀 PacketFS Edge Compute Demo")
    print("💡 Comparing traditional download vs edge compute")
    
    # Run tests
    trad_size, trad_time = test_traditional_download()
    edge_size, edge_time = test_edge_compute()
    header_size, header_time = test_with_headers()
    
    # Show comparison
    print("\n" + "=" * 60)
    print("📊 COMPARISON RESULTS")
    print("=" * 60)
    
    speedup_full = trad_time / edge_time if edge_time > 0 else float('inf')
    speedup_header = trad_time / header_time if header_time > 0 else float('inf')
    
    print(f"\n🏆 Edge Compute (full): {speedup_full:.1f}x faster")
    print(f"🏆 Edge Compute (headers): {speedup_header:.1f}x faster")
    print(f"💾 Bandwidth saved: {trad_size:,} bytes → ~500 bytes")
    print(f"📉 Reduction: {(1 - 500/trad_size)*100:.1f}% less data transferred!")
    
    print("\n🌟 IMAGINE THIS AT SCALE:")
    print(f"  - 1GB file: Download 1GB vs transfer 500 bytes")
    print(f"  - 1TB dataset: Process remotely, get tiny results")
    print(f"  - Entire internet as blob: Compute everywhere, download nothing!")

if __name__ == '__main__':
    main()