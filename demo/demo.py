#!/usr/bin/env python3
import os
import sys
import time
import logging
import argparse
from pathlib import Path
import psutil
import numpy as np
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.packetfs.protocol import PacketFSProtocol
from src.packetfs.seed_pool import SeedPool

class PacketFSDemo:
    def __init__(self, remote_host="10.69.69.235", test_size_mb=10):
        self.remote_host = remote_host
        self.test_size = test_size_mb * 1024 * 1024  # Convert to bytes
        self.protocol = PacketFSProtocol()
        self.seed_pool = SeedPool()
        
        # Configure logging
        logging.basicConfig(
            format='%(message)s',
            level=logging.INFO,
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.log = logging.getLogger("PacketFSDemo")

    def generate_test_data(self):
        """Generate deterministic test data"""
        self.log.info("Generating test data...")
        data = np.random.RandomState(42).bytes(self.test_size)
        test_file = Path("/tmp/packetfs_test_data.bin")
        with open(test_file, "wb") as f:
            f.write(data)
        return test_file

    def measure_memory(self):
        """Get current memory usage in MB"""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024

    def format_speed(self, bytes_transferred, seconds):
        """Format transfer speed nicely"""
        mb_transferred = bytes_transferred / 1024 / 1024
        speed = mb_transferred / seconds
        return f"{speed:.2f} MB/s"

    def run_demo(self):
        """Run the complete PacketFS demonstration"""
        print("\nPacketFS Performance Demonstration")
        print("=================================")
        print(f"Remote Host: {self.remote_host}")
        print(f"Test Size: {self.test_size / 1024 / 1024:.1f} MB")
        print("=================================\n")

        # Initialize metrics
        initial_memory = self.measure_memory()

        # Generate test data
        test_file = self.generate_test_data()
        
        # Outbound transfer
        print("Outbound Transfer Test")
        print("---------------------")
        start_time = time.time()
        self.protocol.send_file(test_file, self.remote_host)
        transfer_time = time.time() - start_time
        print(f"Transfer Time: {transfer_time:.2f} seconds")
        print(f"Transfer Speed: {self.format_speed(self.test_size, transfer_time)}")
        
        # Memory usage after send
        send_memory = self.measure_memory()
        print(f"Memory Usage: {send_memory:.1f} MB (Δ {send_memory - initial_memory:.1f} MB)\n")

        # Inbound transfer
        print("Inbound Transfer Test")
        print("-------------------")
        start_time = time.time()
        self.protocol.receive_file("/tmp/packetfs_received.bin", self.remote_host)
        transfer_time = time.time() - start_time
        print(f"Transfer Time: {transfer_time:.2f} seconds")
        print(f"Transfer Speed: {self.format_speed(self.test_size, transfer_time)}")
        
        # Memory usage after receive
        receive_memory = self.measure_memory()
        print(f"Memory Usage: {receive_memory:.1f} MB (Δ {receive_memory - initial_memory:.1f} MB)\n")

        # Data integrity verification
        print("Data Integrity Verification")
        print("-------------------------")
        with open(test_file, "rb") as f1, open("/tmp/packetfs_received.bin", "rb") as f2:
            data1 = f1.read()
            data2 = f2.read()
            if data1 == data2:
                print("Status: VERIFIED - Data integrity confirmed")
            else:
                print("Status: FAILED - Data corruption detected")
                print(f"Original size: {len(data1)} bytes")
                print(f"Received size: {len(data2)} bytes")

        # Cleanup
        test_file.unlink()
        Path("/tmp/packetfs_received.bin").unlink()

def main():
    parser = argparse.ArgumentParser(description="PacketFS Performance Demo")
    parser.add_argument("--size", type=int, default=10, help="Test file size in MB")
    parser.add_argument("--host", type=str, default="10.69.69.235", help="Remote host address")
    args = parser.parse_args()

    demo = PacketFSDemo(args.host, args.size)
    demo.run_demo()

if __name__ == "__main__":
    main()
