#!/usr/bin/env python3
"""
PacketFS Synchronization Blob Debug Tool
Compares synchronized blobs between local and remote hosts to identify sync issues
"""

import os
import sys
import hashlib
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from packetfs.seed_pool import SeedPool
except ImportError:
    print("❌ Cannot import SeedPool. Make sure the package is installed.")
    sys.exit(1)


class SyncBlobDebugger:
    """Debug synchronized blob differences between hosts"""

    def __init__(self, remote_host: str = "10.69.69.235"):
        self.remote_host = remote_host

    def generate_local_blob(self, size_bytes: int = 65536) -> bytes:
        """Generate the synchronized blob on local machine"""
        print(f"🔧 Generating local sync blob ({size_bytes} bytes)")

        # Try to load seeds if available
        seed_file = "seeds.txt"
        if os.path.exists(seed_file):
            try:
                pool = SeedPool.from_file(seed_file)
                print(f"📁 Loaded {len(pool.seeds)} seeds from {seed_file}")

                # Generate blob using seed pool
                blob_data = bytearray()
                for i in range(size_bytes):
                    seed_idx = i % len(pool.seeds)
                    seed = pool.get(seed_idx)
                    blob_data.append(seed[i % len(seed)])

                return bytes(blob_data)

            except Exception as e:
                print(f"⚠️  Failed to use seed pool: {e}")

        # Fallback: generate deterministic blob
        print("🔄 Using deterministic fallback blob generation")
        blob_data = bytearray()

        # Use a predictable pattern that should be architecture-independent
        for i in range(size_bytes):
            # Simple deterministic pattern
            value = (i * 7 + 13) % 256
            blob_data.append(value)

        return bytes(blob_data)

    def generate_remote_blob(self, size_bytes: int = 65536) -> bytes:
        """Generate the synchronized blob on remote machine"""
        print(f"🌐 Generating remote sync blob ({size_bytes} bytes)")

        # Create a temporary script to run on remote
        script_content = f"""#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/home/punk/packetfs-remote/src')

try:
    from packetfs.seed_pool import SeedPool
    
    # Try to load seeds
    seed_file = "/home/punk/packetfs-remote/seeds.txt"
    if os.path.exists(seed_file):
        try:
            pool = SeedPool.from_file(seed_file)
            print(f"Remote loaded {{len(pool.seeds)}} seeds", file=sys.stderr)
            
            # Generate blob using seed pool
            blob_data = bytearray()
            for i in range({size_bytes}):
                seed_idx = i % len(pool.seeds)
                seed = pool.get(seed_idx)
                blob_data.append(seed[i % len(seed)])
                
            sys.stdout.buffer.write(bytes(blob_data))
        except Exception as e:
            print(f"Remote seed pool error: {{e}}", file=sys.stderr)
            raise
    else:
        # Fallback: same deterministic pattern
        print("Remote using deterministic fallback", file=sys.stderr)
        blob_data = bytearray()
        
        for i in range({size_bytes}):
            value = (i * 7 + 13) % 256
            blob_data.append(value)
            
        sys.stdout.buffer.write(bytes(blob_data))
        
except ImportError as e:
    print(f"Remote import error: {{e}}", file=sys.stderr)
    # Pure fallback
    blob_data = bytearray()
    for i in range({size_bytes}):
        value = (i * 7 + 13) % 256
        blob_data.append(value)
    sys.stdout.buffer.write(bytes(blob_data))
"""

        # Create temporary script file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(script_content)
            tmp_path = tmp.name

        try:
            # Copy script to remote and execute
            rsync_result = subprocess.run(
                [
                    "rsync",
                    "-avz",
                    tmp_path,
                    f"punk@{self.remote_host}:/tmp/remote_blob_gen.py",
                ],
                capture_output=True,
                text=True,
            )

            if rsync_result.returncode != 0:
                raise Exception(f"Failed to copy script: {rsync_result.stderr}")

            # Execute script on remote
            ssh_result = subprocess.run(
                [
                    "ssh",
                    f"punk@{self.remote_host}",
                    "cd /home/punk/packetfs-remote && python3 /tmp/remote_blob_gen.py",
                ],
                capture_output=True,
            )

            if ssh_result.returncode != 0:
                print(f"Remote stderr: {ssh_result.stderr.decode()}")
                raise Exception(f"Remote script failed: {ssh_result.stderr.decode()}")

            return ssh_result.stdout

        finally:
            # Cleanup
            os.unlink(tmp_path)
            subprocess.run(
                ["ssh", f"punk@{self.remote_host}", "rm -f /tmp/remote_blob_gen.py"],
                capture_output=True,
            )

    def compare_blobs(self, local_blob: bytes, remote_blob: bytes):
        """Compare local and remote synchronized blobs"""
        print(f"🔍 Comparing synchronized blobs")
        print(f"   Local blob:  {len(local_blob)} bytes")
        print(f"   Remote blob: {len(remote_blob)} bytes")

        # Basic comparison
        size_match = len(local_blob) == len(remote_blob)
        data_match = local_blob == remote_blob

        print(f"   Size match: {size_match}")
        print(f"   Data match: {data_match}")

        if not data_match:
            print(f"🚨 SYNCHRONIZATION ISSUE DETECTED!")

            # Find first difference
            min_len = min(len(local_blob), len(remote_blob))
            first_diff = None

            for i in range(min_len):
                if local_blob[i] != remote_blob[i]:
                    first_diff = i
                    break

            if first_diff is not None:
                print(f"   First difference at byte {first_diff}:")
                print(f"     Local:  0x{local_blob[first_diff]:02x}")
                print(f"     Remote: 0x{remote_blob[first_diff]:02x}")

                # Show context around difference
                start = max(0, first_diff - 8)
                end = min(min_len, first_diff + 9)

                print(f"   Context (bytes {start}-{end-1}):")
                local_hex = " ".join(f"{b:02x}" for b in local_blob[start:end])
                remote_hex = " ".join(f"{b:02x}" for b in remote_blob[start:end])
                print(f"     Local:  {local_hex}")
                print(f"     Remote: {remote_hex}")

                # Mark the difference
                diff_pos = first_diff - start
                marker = "   " * diff_pos + "^^"
                print(f"     Diff:   {marker}")

            # Calculate hashes
            local_hash = hashlib.sha256(local_blob).hexdigest()
            remote_hash = hashlib.sha256(remote_blob).hexdigest()

            print(f"   Local SHA256:  {local_hash}")
            print(f"   Remote SHA256: {remote_hash}")

            # Count differences
            diff_count = sum(
                1 for i in range(min_len) if local_blob[i] != remote_blob[i]
            )
            diff_percentage = (diff_count / min_len) * 100 if min_len > 0 else 0

            print(
                f"   Differences: {diff_count}/{min_len} bytes ({diff_percentage:.2f}%)"
            )

            return False
        else:
            print(f"✅ Synchronized blobs are identical!")
            local_hash = hashlib.sha256(local_blob).hexdigest()
            print(f"   SHA256: {local_hash}")
            return True

    def debug_offset_mapping(self, blob: bytes, test_data: bytes):
        """Debug how test data maps to offsets in the blob"""
        print(f"🎯 Debugging offset mapping")
        print(f"   Blob size: {len(blob)} bytes")
        print(f"   Test data: {len(test_data)} bytes")

        # Simple offset mapping (this should match the actual protocol logic)
        mappings = []

        for i, byte_val in enumerate(test_data):
            # Find where this byte appears in the blob
            try:
                offset = blob.index(byte_val)
                mappings.append((i, byte_val, offset))
                print(f"   Byte {i}: 0x{byte_val:02x} -> offset {offset}")
            except ValueError:
                print(f"   Byte {i}: 0x{byte_val:02x} -> NOT FOUND in blob!")
                mappings.append((i, byte_val, -1))

        return mappings

    def run_sync_debug(self, blob_size: int = 65536):
        """Run comprehensive synchronization debugging"""
        print("🔍 PACKETFS SYNCHRONIZATION DEBUG")
        print("=" * 50)

        try:
            # Generate blobs on both sides
            local_blob = self.generate_local_blob(blob_size)
            remote_blob = self.generate_remote_blob(blob_size)

            # Compare blobs
            blobs_match = self.compare_blobs(local_blob, remote_blob)

            if not blobs_match:
                print(f"\n🔧 SOLUTION IDENTIFIED:")
                print(f"   The synchronized blobs differ between x86_64 and ARM64!")
                print(f"   This explains the systematic data corruption.")
                print(
                    f"   Fix: Ensure identical blob generation on both architectures."
                )

                # Save blobs for analysis
                with open("debug_local_blob.bin", "wb") as f:
                    f.write(local_blob)
                with open("debug_remote_blob.bin", "wb") as f:
                    f.write(remote_blob)

                print(f"\n💾 Saved blobs for analysis:")
                print(f"   debug_local_blob.bin  - Local x86_64 blob")
                print(f"   debug_remote_blob.bin - Remote ARM64 blob")

            else:
                print(
                    f"\n🤔 Blobs are identical - corruption must be elsewhere in protocol"
                )

                # Test with sample data
                test_data = b"AAAA"  # Simple test pattern
                print(f"\n🧪 Testing with sample data: {test_data.hex()}")

                local_mappings = self.debug_offset_mapping(local_blob, test_data)
                print(f"   Local mappings: {local_mappings}")

                # This would help identify if the issue is in the encoding/decoding logic

        except Exception as e:
            print(f"❌ Debug failed: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Debug PacketFS synchronization blobs")
    parser.add_argument(
        "--remote", default="10.69.69.235", help="Remote host for testing"
    )
    parser.add_argument("--size", type=int, default=65536, help="Blob size in bytes")

    args = parser.parse_args()

    debugger = SyncBlobDebugger(args.remote)
    debugger.run_sync_debug(args.size)
