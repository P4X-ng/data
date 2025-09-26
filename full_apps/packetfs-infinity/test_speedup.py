#!/usr/bin/env python3
"""
PacketFS Transfer Speedup Calculator
Demonstrates the actual speedup achieved by PacketFS compression
"""

import sys
import time
import json
import hashlib
from pathlib import Path
import requests
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_speedup(filepath: str, server_url: str = "https://localhost:8811"):
    """Calculate and demonstrate PacketFS transfer speedup"""
    
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"[ERROR] File not found: {filepath}")
        return
    
    filesize = filepath.stat().st_size
    
    print("=" * 80)
    print(" " * 20 + "PACKETFS TRANSFER SPEEDUP ANALYSIS")
    print("=" * 80)
    print()
    print(f"Test File: {filepath.name}")
    print(f"Original Size: {filesize:,} bytes ({filesize/1024/1024:.2f} MB)")
    print()
    
    # Step 1: Upload file to create IPROG
    print("[1] Creating PacketFS IPROG")
    print("-" * 50)
    
    start = time.time()
    with open(filepath, 'rb') as f:
        files = {'file': (filepath.name, f, 'application/octet-stream')}
        resp = requests.post(f"{server_url}/objects", files=files, verify=False)
    
    if resp.status_code != 200:
        print(f"Error: Upload failed with status {resp.status_code}")
        return
    
    upload_time = time.time() - start
    result = resp.json()
    
    object_id = result.get('object_id')
    compressed_size = result.get('compressed_size', 0)
    tx_ratio = result.get('tx_ratio', 0)
    
    print(f"Object ID: {object_id[:40]}...")
    print(f"IPROG Creation Time: {upload_time:.2f}s")
    print(f"IPROG Size: {compressed_size:,} bytes")
    print(f"Compression Ratio: {(1 - tx_ratio):.3%}")
    print()
    
    # Step 2: Fetch IPROG to get window details
    print("[2] Analyzing IPROG Structure")
    print("-" * 50)
    
    iprog_resp = requests.get(f"{server_url}/objects/{object_id}/iprog", verify=False)
    if iprog_resp.status_code == 200:
        iprog = iprog_resp.json()
        windows = iprog.get('windows', [])
        
        # Count PVRT bytes
        pvrt_bytes = 0
        for window in windows:
            if 'pvrt' in window:
                import base64
                pvrt_data = base64.b64decode(window['pvrt'])
                pvrt_bytes += len(pvrt_data)
        
        print(f"Windows: {len(windows)}")
        print(f"Window Size: {iprog.get('window_size', 0):,} bytes")
        print(f"PVRT Data: {pvrt_bytes:,} bytes (actual wire transfer)")
        actual_wire_bytes = pvrt_bytes
    else:
        print("Could not fetch IPROG details")
        actual_wire_bytes = compressed_size
    print()
    
    # Step 3: Calculate speedup for different network speeds
    print("[3] Transfer Speedup Analysis")
    print("-" * 50)
    
    # Different network scenarios (MB/s)
    network_speeds = [
        (1, "Slow DSL"),
        (10, "Fast DSL/Cable"),
        (100, "Gigabit LAN"),
        (1000, "10 Gigabit"),
        (10000, "100 Gigabit")
    ]
    
    print(f"Original file transfer times vs PacketFS:")
    print()
    print(f"{'Network':<20} {'Speed':<12} {'Raw Transfer':<15} {'PFS Transfer':<15} {'Speedup':<12} {'Time Saved'}")
    print("-" * 95)
    
    for speed_mbps, desc in network_speeds:
        speed_bps = speed_mbps * 1024 * 1024
        
        # Raw file transfer time
        raw_time = filesize / speed_bps
        
        # PacketFS transfer time (only PVRT data)
        pfs_time = actual_wire_bytes / speed_bps
        
        # Calculate speedup
        speedup = raw_time / pfs_time if pfs_time > 0 else float('inf')
        time_saved = raw_time - pfs_time
        
        # Format times
        def format_time(t):
            if t < 1:
                return f"{t*1000:.1f}ms"
            elif t < 60:
                return f"{t:.2f}s"
            else:
                return f"{t/60:.1f}min"
        
        print(f"{desc:<20} {speed_mbps:>6} MB/s   {format_time(raw_time):>14}  {format_time(pfs_time):>14}  {speedup:>9.1f}x  {format_time(time_saved):>12}")
    
    print()
    
    # Step 4: Real-world impact
    print("[4] Real-World Impact")
    print("-" * 50)
    
    compression_pct = (1 - tx_ratio) * 100
    
    if filesize >= 1024 * 1024:  # File is at least 1MB
        # Calculate for typical scenarios
        print(f"For a {filesize/1024/1024:.1f}MB file:")
        print()
        
        # Mobile data scenario
        mobile_cost_per_gb = 10  # $10 per GB typical
        data_saved_gb = (filesize - actual_wire_bytes) / (1024**3)
        money_saved = data_saved_gb * mobile_cost_per_gb
        print(f"  Mobile Data Savings: ${money_saved:.2f} (@$10/GB)")
        
        # Cloud transfer scenario
        cloud_transfer_cost = 0.09  # $0.09 per GB typical egress
        cloud_saved = data_saved_gb * cloud_transfer_cost * 1000  # x1000 for scale
        print(f"  Cloud Egress Savings: ${cloud_saved:.2f} for 1000 transfers")
        
        # Time savings
        typical_speed = 10  # 10 MB/s typical home internet
        time_saved_typical = (filesize - actual_wire_bytes) / (typical_speed * 1024 * 1024)
        print(f"  Time Saved per Transfer: {time_saved_typical:.1f}s @ 10MB/s")
        
        # Scale impact
        print()
        print(f"  At scale (1 million transfers):")
        bandwidth_saved_tb = (filesize - actual_wire_bytes) * 1000000 / (1024**4)
        print(f"    Bandwidth Saved: {bandwidth_saved_tb:.1f} TB")
        print(f"    Data Costs Saved: ${bandwidth_saved_tb * 90:.0f}")  # ~$90/TB typical
    
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"PacketFS Compression: {compression_pct:.1%}")
    print(f"Data Reduction: {filesize:,} → {actual_wire_bytes:,} bytes")
    print(f"Speedup Factor: {filesize/actual_wire_bytes:.1f}x")
    print()
    
    if compression_pct > 99:
        print("*** EXCEPTIONAL: >99% compression achieved! ***")
        print("*** This represents near-optimal reference-based compression ***")
    elif compression_pct > 90:
        print("*** EXCELLENT: >90% compression achieved! ***")
        print("*** Massive bandwidth and time savings enabled ***")
    elif compression_pct > 50:
        print("*** GOOD: >50% compression achieved ***")
    else:
        print(f"*** Compression: {compression_pct:.1f}% ***")
    
    print()
    print("PacketFS achieves this by:")
    print("  1. Both endpoints share identical deterministic memory blob")
    print("  2. Files are encoded as tiny references (BREF) to blob positions")
    print("  3. Only the references are transmitted, not the actual data")
    print("  4. Receiver reconstructs using references + shared blob")
    print("=" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_speedup.py <file_path>")
        print("\nExamples:")
        print("  python test_speedup.py /tmp/test_10mb.dat")
        print("  python test_speedup.py /usr/bin/python3")
        print("  python test_speedup.py /boot/vmlinuz-$(uname -r)")
        sys.exit(1)
    
    filepath = sys.argv[1]
    test_speedup(filepath)