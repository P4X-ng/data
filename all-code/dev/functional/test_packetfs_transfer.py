#!/usr/bin/env python3
"""
Test PacketFS Protocol Transfer
===============================
Demonstrate real PacketFS protocol transfer to the in-memory mount
"""

import sys
import os
import time
import json
import socket
import threading
from pathlib import Path

# Add PacketFS to path
sys.path.insert(0, 'realsrc/network')

from packetfs_file_transfer import PacketFSFileTransfer

def test_large_file_transfer():
    print("PacketFS Protocol Transfer Test")
    print("===============================")
    
    # Check for large test file
    large_files = ['test_1gb.bin', 'test_pattern_1gb.bin', 'ultimate_1gb_pattern.bin']
    test_file = None
    
    for filename in large_files:
        if Path(filename).exists():
            test_file = filename
            break
            
    if not test_file:
        print("Creating 1GB test file for transfer...")
        test_file = 'packetfs_test_1gb.bin'
        # Create pattern file for best compression
        with open(test_file, 'wb') as f:
            pattern = b'PacketFS' * 128  # 1KB pattern
            for _ in range(1024 * 1024):  # Write 1GB
                f.write(pattern)
        print(f"Created {test_file}")
    
    file_size = Path(test_file).stat().st_size
    print(f"Test file: {test_file} ({file_size / (1024*1024*1024):.2f} GB)")
    
    # Initialize PacketFS
    pfs = PacketFSFileTransfer()
    
    # Start server in background
    def run_server():
        try:
            pfs.start_server()
        except Exception as e:
            print(f"Server error: {e}")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(2)
    
    print("\nStarting PacketFS transfer using real protocol...")
    start_time = time.time()
    
    try:
        # Use PacketFS protocol to transfer to the in-memory mount
        output_file = "/mnt/packetfs_demo/data/large_file_via_packetfs.bin"
        
        # Request file transfer using PacketFS protocol
        success = pfs.request_file("127.0.0.1", test_file, output_file)
        
        if success:
            transfer_time = time.time() - start_time
            transferred_size = Path(output_file).stat().st_size
            
            print(f"\n🎉 PacketFS Transfer Complete!")
            print(f"File: {test_file}")
            print(f"Size: {transferred_size:,} bytes ({transferred_size/(1024*1024):.1f} MB)")
            print(f"Time: {transfer_time:.2f} seconds")
            print(f"Speed: {(transferred_size/(1024*1024))/transfer_time:.1f} MB/s")
            print(f"Output: {output_file}")
            
            # Check compression in mount
            time.sleep(3)  # Let the mount process it
            
            return True
        else:
            print("❌ PacketFS transfer failed")
            return False
            
    except Exception as e:
        print(f"Transfer error: {e}")
        return False

if __name__ == "__main__":
    test_large_file_transfer()
