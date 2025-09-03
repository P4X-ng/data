#!/usr/bin/env python3
"""
PacketFS Checksum Debugging Tool
Investigates data integrity issues with controlled test patterns
"""

import os
import sys
import time
import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
from logging.handlers import RotatingFileHandler

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from packetfs_file_transfer import PacketFSFileTransfer
except ImportError:
    print("❌ Cannot import PacketFSFileTransfer. Make sure the package is installed.")
    sys.exit(1)


class ChecksumDebugger:
    """Debug checksum mismatches in PacketFS transfers"""

    def __init__(self, remote_host: str = "10.69.69.235"):
        self.remote_host = remote_host
        self.setup_logging()

    def setup_logging(self):
        """Setup detailed logging for debugging"""
        log_dir = Path("debug_logs")
        log_dir.mkdir(exist_ok=True)

        # Create logger
        self.logger = logging.getLogger("ChecksumDebugger")
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.logger.handlers.clear()

        # File handler with rotation
        log_file = log_dir / f"checksum_debug_{int(time.time())}.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=100 * 1024 * 1024, backupCount=3
        )
        file_handler.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Detailed formatter
        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )

        # Simple console formatter
        simple_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )

        file_handler.setFormatter(detailed_formatter)
        console_handler.setFormatter(simple_formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info(f"Checksum debugging initialized - Remote: {self.remote_host}")

    def create_test_pattern_file(self, pattern_type: str, size_kb: int = 64) -> str:
        """Create test files with specific data patterns"""
        filename = f"debug_{pattern_type}_{size_kb}kb.bin"
        target_size = size_kb * 1024

        self.logger.info(
            f"Creating {pattern_type} pattern file: {filename} ({size_kb}KB)"
        )

        with open(filename, "wb") as f:
            if pattern_type == "all_A":
                # All ASCII 'A' (0x41)
                data = b"A" * target_size
                f.write(data)
                self.logger.debug(f"Pattern: All 0x41, size={len(data)}")

            elif pattern_type == "all_zero":
                # All zeros
                data = b"\x00" * target_size
                f.write(data)
                self.logger.debug(f"Pattern: All 0x00, size={len(data)}")

            elif pattern_type == "sequential":
                # Sequential bytes 0x00, 0x01, 0x02, ... 0xFF, repeat
                data = bytes(i % 256 for i in range(target_size))
                f.write(data)
                self.logger.debug(f"Pattern: Sequential 0x00-0xFF, size={len(data)}")

            elif pattern_type == "alternating":
                # Alternating 0xAA, 0x55
                data = b"\xaa\x55" * (target_size // 2)
                if target_size % 2:
                    data += b"\xaa"
                f.write(data)
                self.logger.debug(f"Pattern: Alternating 0xAA/0x55, size={len(data)}")

            elif pattern_type == "endian_test":
                # Test endianness - 32-bit integers
                import struct

                data = b""
                for i in range(0, target_size // 4):
                    data += struct.pack("<I", i)  # Little endian
                if target_size % 4:
                    data += b"\x00" * (target_size % 4)
                f.write(data)
                self.logger.debug(
                    f"Pattern: Little-endian 32-bit ints, size={len(data)}"
                )

            else:
                raise ValueError(f"Unknown pattern type: {pattern_type}")

        # Calculate and log file hash
        file_hash = self.get_file_hash(filename)
        self.logger.info(
            f"Created {filename}: {os.path.getsize(filename)} bytes, SHA256: {file_hash[:16]}..."
        )

        return filename

    def get_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def hex_dump(self, data: bytes, max_bytes: int = 64) -> str:
        """Create a hex dump of data for logging"""
        if len(data) > max_bytes:
            data = data[:max_bytes]

        hex_str = " ".join(f"{b:02x}" for b in data)
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)

        return f"HEX: {hex_str}\nASC: {ascii_str}"

    def debug_packetfs_transfer(self, test_file: str) -> Dict:
        """Perform PacketFS transfer with detailed debugging"""
        self.logger.info(f"🚀 Debug transfer starting: {test_file}")

        # Copy test file to remote
        self.logger.info("📤 Copying test file to remote...")
        rsync_result = subprocess.run(
            ["rsync", "-avz", test_file, f"punk@{self.remote_host}:~/"],
            capture_output=True,
            text=True,
        )

        if rsync_result.returncode != 0:
            self.logger.error(f"Failed to copy file: {rsync_result.stderr}")
            return {"success": False, "error": "rsync_failed"}

        self.logger.debug(f"Rsync output: {rsync_result.stdout}")

        # Start PacketFS server
        server_cmd = (
            f"cd ~/packetfs-remote && "
            f".venv/bin/python tools/packetfs_file_transfer.py server "
            f"--host 0.0.0.0 --port 8337 --debug"
        )

        self.logger.info("🎯 Starting PacketFS server with debug output...")
        server_process = subprocess.Popen(
            ["ssh", "-A", f"punk@{self.remote_host}", server_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        time.sleep(3)  # Wait for server to start

        # Get original file info
        original_size = os.path.getsize(test_file)
        original_hash = self.get_file_hash(test_file)

        self.logger.info(
            f"Original file: {original_size} bytes, SHA256: {original_hash[:16]}..."
        )

        # Read first and last chunks of original file for comparison
        with open(test_file, "rb") as f:
            first_chunk = f.read(8192)
            f.seek(-min(8192, original_size), 2)  # Last chunk
            last_chunk = f.read()

        self.logger.debug(
            f"Original first chunk (64 bytes):\n{self.hex_dump(first_chunk)}"
        )
        self.logger.debug(
            f"Original last chunk (64 bytes):\n{self.hex_dump(last_chunk)}"
        )

        # Perform PacketFS transfer
        pfs = PacketFSFileTransfer()
        start_time = time.time()

        remote_file_path = f"/home/punk/{Path(test_file).name}"
        local_output = f"received_debug_{Path(test_file).stem}.bin"

        self.logger.info(f"📥 Starting transfer: {remote_file_path} -> {local_output}")

        success = pfs.request_file(self.remote_host, remote_file_path, local_output)
        transfer_time = time.time() - start_time

        # Kill server
        try:
            server_process.terminate()
            server_process.wait(timeout=5)
        except:
            server_process.kill()

        # Get server output for analysis
        server_stdout, server_stderr = server_process.communicate()
        if server_stdout:
            self.logger.debug(f"Server stdout:\n{server_stdout}")
        if server_stderr:
            self.logger.debug(f"Server stderr:\n{server_stderr}")

        if not success:
            self.logger.error("❌ PacketFS transfer failed")
            return {"success": False, "error": "transfer_failed"}

        # Analyze received file
        received_size = os.path.getsize(local_output)
        received_hash = self.get_file_hash(local_output)

        self.logger.info(
            f"Received file: {received_size} bytes, SHA256: {received_hash[:16]}..."
        )

        # Read first and last chunks of received file
        with open(local_output, "rb") as f:
            received_first_chunk = f.read(8192)
            f.seek(-min(8192, received_size), 2)  # Last chunk
            received_last_chunk = f.read()

        self.logger.debug(
            f"Received first chunk (64 bytes):\n{self.hex_dump(received_first_chunk)}"
        )
        self.logger.debug(
            f"Received last chunk (64 bytes):\n{self.hex_dump(received_last_chunk)}"
        )

        # Compare chunks byte by byte
        first_chunk_match = first_chunk == received_first_chunk
        last_chunk_match = last_chunk == received_last_chunk
        size_match = original_size == received_size
        hash_match = original_hash == received_hash

        self.logger.info(
            f"Size match: {size_match} ({original_size} vs {received_size})"
        )
        self.logger.info(f"Hash match: {hash_match}")
        self.logger.info(f"First chunk match: {first_chunk_match}")
        self.logger.info(f"Last chunk match: {last_chunk_match}")

        # If chunks don't match, find first difference
        if not first_chunk_match:
            for i, (a, b) in enumerate(zip(first_chunk, received_first_chunk)):
                if a != b:
                    self.logger.warning(
                        f"First difference at byte {i}: original=0x{a:02x}, received=0x{b:02x}"
                    )
                    break

        # Calculate throughput
        throughput_mbs = (
            original_size / (1024 * 1024) / transfer_time if transfer_time > 0 else 0
        )

        results = {
            "success": True,
            "pattern": Path(test_file).stem.split("_")[1],  # Extract pattern type
            "original_size": original_size,
            "received_size": received_size,
            "original_hash": original_hash,
            "received_hash": received_hash,
            "transfer_time": transfer_time,
            "throughput_mbs": throughput_mbs,
            "size_match": size_match,
            "hash_match": hash_match,
            "first_chunk_match": first_chunk_match,
            "last_chunk_match": last_chunk_match,
            "stats": pfs.stats,
        }

        self.logger.info(
            f"✅ Transfer completed: {throughput_mbs:.2f} MB/s, Integrity: {'✅' if hash_match else '❌'}"
        )

        return results

    def run_checksum_debug_suite(self):
        """Run comprehensive checksum debugging with various patterns"""
        print("🔍 PACKETFS CHECKSUM DEBUG SUITE")
        print("=" * 60)

        patterns = ["all_A", "all_zero", "sequential", "alternating", "endian_test"]
        sizes = [8, 32, 64]  # KB sizes for quick testing

        results = []

        for pattern in patterns:
            for size_kb in sizes:
                self.logger.info(
                    f"\n📊 Testing pattern '{pattern}' with {size_kb}KB file"
                )

                # Create test file
                test_file = self.create_test_pattern_file(pattern, size_kb)

                try:
                    # Test transfer
                    result = self.debug_packetfs_transfer(test_file)
                    results.append(result)

                    # Print summary
                    if result.get("success"):
                        integrity = "✅" if result["hash_match"] else "❌"
                        print(
                            f"  {pattern:>12} {size_kb:>3}KB: {result['throughput_mbs']:>6.2f} MB/s, "
                            f"Integrity: {integrity}, Size: {result['size_match']}"
                        )
                    else:
                        print(
                            f"  {pattern:>12} {size_kb:>3}KB: ❌ FAILED - {result.get('error', 'Unknown')}"
                        )

                except Exception as e:
                    self.logger.error(f"Exception during {pattern} test: {e}")
                    print(f"  {pattern:>12} {size_kb:>3}KB: ❌ EXCEPTION - {e}")

                finally:
                    # Cleanup
                    try:
                        os.remove(test_file)
                        received_file = f"received_debug_{pattern}_{size_kb}kb.bin"
                        if os.path.exists(received_file):
                            os.remove(received_file)
                    except:
                        pass

                time.sleep(1)  # Brief pause between tests

        # Summary analysis
        print(f"\n📈 CHECKSUM DEBUG SUMMARY")
        print("-" * 60)

        successful_tests = [r for r in results if r.get("success")]
        if successful_tests:
            integrity_rate = (
                sum(1 for r in successful_tests if r["hash_match"])
                / len(successful_tests)
                * 100
            )
            avg_throughput = sum(r["throughput_mbs"] for r in successful_tests) / len(
                successful_tests
            )

            print(f"Successful transfers: {len(successful_tests)}/{len(results)}")
            print(f"Data integrity rate: {integrity_rate:.1f}%")
            print(f"Average throughput: {avg_throughput:.2f} MB/s")

            # Pattern-specific analysis
            pattern_results = {}
            for result in successful_tests:
                pattern = result["pattern"]
                if pattern not in pattern_results:
                    pattern_results[pattern] = []
                pattern_results[pattern].append(result)

            print(f"\nPattern-specific integrity rates:")
            for pattern, results_list in pattern_results.items():
                integrity_rate = (
                    sum(1 for r in results_list if r["hash_match"])
                    / len(results_list)
                    * 100
                )
                print(
                    f"  {pattern:>12}: {integrity_rate:>5.1f}% ({sum(1 for r in results_list if r['hash_match'])}/{len(results_list)})"
                )

        print(f"\n💾 Detailed logs saved to: debug_logs/checksum_debug_*.log")
        print("🏁 Checksum debugging completed!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PacketFS Checksum Debugging Tool")
    parser.add_argument(
        "--remote", default="10.69.69.235", help="Remote host for testing"
    )
    parser.add_argument(
        "--pattern",
        choices=["all_A", "all_zero", "sequential", "alternating", "endian_test"],
        help="Test specific pattern only",
    )
    parser.add_argument(
        "--size", type=int, default=64, help="File size in KB (default: 64)"
    )

    args = parser.parse_args()

    debugger = ChecksumDebugger(args.remote)

    if args.pattern:
        # Test single pattern
        test_file = debugger.create_test_pattern_file(args.pattern, args.size)
        result = debugger.debug_packetfs_transfer(test_file)
        print(f"Result: {result}")

        # Cleanup
        try:
            os.remove(test_file)
            received_file = f"received_debug_{args.pattern}_{args.size}kb.bin"
            if os.path.exists(received_file):
                os.remove(received_file)
        except:
            pass
    else:
        # Run full debug suite
        debugger.run_checksum_debug_suite()
