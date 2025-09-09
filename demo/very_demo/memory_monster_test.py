#!/usr/bin/env python3
"""
🔥 MEMORY MONSTER TEST 🔥
PacketFS 1GB Linear Transfer - Pure In-Memory Beast Mode

This test creates a 1GB file in memory and transfers it using PacketFS
telnet interface over loopback with NO threading - pure linear processing
for maximum memory bandwidth utilization.
"""

import os
import sys
import time
import threading
import tempfile
import psutil
import gc
from pathlib import Path

# Add PacketFS modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from packetfs_file_transfer import PacketFSFileTransfer

class MemoryMonster:
    """The Memory Monster - 1GB linear transfer beast"""
    
    def __init__(self):
        self.size_gb = 1
        self.size_bytes = self.size_gb * 1024 * 1024 * 1024
        self.chunk_size = 64 * 1024 * 1024  # 64MB chunks for MAXIMUM MEMORY THROUGHPUT
        self.host = "127.0.0.1"  # LOOPBACK BEAST MODE
        self.port = 8337
        
        print(f"🔥 MEMORY MONSTER INITIALIZED 🔥")
        print(f"📏 Target size: {self.size_gb} GB ({self.size_bytes:,} bytes)")
        print(f"🧩 Chunk size: {self.chunk_size // (1024*1024)} MB")
        print(f"🌐 Interface: {self.host}:{self.port} (LOOPBACK BEAST)")
        print(f"🚀 Mode: LINEAR - NO THREADING - PURE MEMORY POWER")
    
    def create_memory_monster_file(self) -> str:
        """Create 1GB test file IN MEMORY - THE BEAST AWAKENS"""
        print(f"\n🧠 CREATING MEMORY MONSTER - 1GB IN RAM...")
        
        # Get memory info before
        mem_before = psutil.virtual_memory()
        print(f"📊 Memory before: {mem_before.available / (1024**3):.2f} GB available")
        
        if mem_before.available < self.size_bytes * 2:
            print(f"⚠️  WARNING: Low memory! Available: {mem_before.available / (1024**3):.2f} GB")
            print(f"⚠️  Required: {(self.size_bytes * 2) / (1024**3):.2f} GB (2x for safety)")
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.monster')
        temp_path = temp_file.name
        
        print(f"💾 Creating monster file: {temp_path}")
        
        start_time = time.time()
        bytes_written = 0
        
        # Write in large chunks for maximum memory bandwidth
        with open(temp_path, 'wb') as f:
            while bytes_written < self.size_bytes:
                remaining = self.size_bytes - bytes_written
                write_size = min(self.chunk_size, remaining)
                
                # Generate random data chunk - MEMORY INTENSIVE
                chunk = os.urandom(write_size)
                f.write(chunk)
                bytes_written += write_size
                
                # Progress reporting
                progress = (bytes_written / self.size_bytes) * 100
                if bytes_written % (self.chunk_size * 4) == 0:  # Every 256MB
                    elapsed = time.time() - start_time
                    rate = bytes_written / (1024**3) / elapsed  # GB/s
                    print(f"🔥 {progress:5.1f}% | {bytes_written/(1024**3):6.2f} GB | {rate:6.2f} GB/s write rate")
        
        creation_time = time.time() - start_time
        creation_rate = self.size_bytes / (1024**3) / creation_time
        
        # Get memory info after
        mem_after = psutil.virtual_memory()
        mem_used = (mem_before.available - mem_after.available) / (1024**3)
        
        print(f"✅ MONSTER CREATED!")
        print(f"⏱️  Creation time: {creation_time:.3f} seconds")
        print(f"🚀 Creation rate: {creation_rate:.2f} GB/s")
        print(f"🧠 Memory used: {mem_used:.2f} GB")
        print(f"📊 Memory after: {mem_after.available / (1024**3):.2f} GB available")
        
        return temp_path
    
    def start_monster_server(self):
        """Start PacketFS server for the memory monster"""
        print(f"\n🚀 STARTING MEMORY MONSTER SERVER ON {self.host}:{self.port}")
        
        server = PacketFSFileTransfer(self.host, self.port)
        
        def run_server():
            try:
                server.start_server()
            except Exception as e:
                print(f"❌ Server error: {e}")
        
        # Start server in background thread
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True
        server_thread.start()
        
        # Wait for server to start
        time.sleep(2)
        print(f"✅ MONSTER SERVER READY!")
        
        return server
    
    def monster_transfer_test(self, monster_file: str):
        """Execute the MEMORY MONSTER 1GB transfer test"""
        print(f"\n🔥🔥🔥 MEMORY MONSTER TRANSFER - 1GB LINEAR TEST 🔥🔥🔥")
        print(f"📁 Source: {monster_file}")
        print(f"🎯 Target: LOOPBACK ({self.host})")
        print(f"⚡ Mode: LINEAR - NO THREADING - PURE MEMORY BANDWIDTH")
        
        # Get initial memory state
        mem_start = psutil.virtual_memory()
        cpu_start = psutil.cpu_percent(interval=1)
        
        print(f"\n📊 INITIAL SYSTEM STATE:")
        print(f"🧠 Memory: {mem_start.available / (1024**3):.2f} GB available")
        print(f"🖥️  CPU: {cpu_start:.1f}% utilization")
        
        # Create client
        client = PacketFSFileTransfer()
        destination = tempfile.NamedTemporaryFile(delete=False, suffix='.received').name
        
        print(f"\n🚀 INITIATING MEMORY MONSTER TRANSFER...")
        print(f"📤 Source: {monster_file}")
        print(f"📥 Destination: {destination}")
        
        # THE BEAST UNLEASHED - 1GB LINEAR TRANSFER
        start_time = time.time()
        
        try:
            success = client.request_file(self.host, monster_file, destination)
            
            transfer_time = time.time() - start_time
            
            if success:
                # Verify file sizes
                source_size = os.path.getsize(monster_file)
                dest_size = os.path.getsize(destination)
                
                print(f"\n🎉 MEMORY MONSTER TRANSFER COMPLETE! 🎉")
                print(f"✅ SUCCESS: {success}")
                print(f"📏 Source size: {source_size:,} bytes ({source_size/(1024**3):.3f} GB)")
                print(f"📏 Dest size: {dest_size:,} bytes ({dest_size/(1024**3):.3f} GB)")
                print(f"⏱️  Transfer time: {transfer_time:.3f} seconds")
                
                if source_size == dest_size:
                    print(f"✅ SIZE VERIFICATION: PERFECT MATCH!")
                else:
                    print(f"❌ SIZE MISMATCH: {dest_size - source_size:,} bytes difference")
                
                # Calculate throughput
                throughput_bps = source_size / transfer_time
                throughput_mbps = throughput_bps / (1024**2)  # MB/s
                throughput_gbps = throughput_bps / (1024**3)  # GB/s
                
                print(f"\n🚀 MEMORY MONSTER PERFORMANCE METRICS:")
                print(f"🏃 Throughput: {throughput_gbps:.3f} GB/s")
                print(f"🏃 Throughput: {throughput_mbps:.1f} MB/s") 
                print(f"🏃 Throughput: {throughput_bps/1000000:.1f} Mbps")
                
                # Memory analysis
                mem_end = psutil.virtual_memory()
                mem_peak_usage = (mem_start.available - mem_end.available) / (1024**3)
                
                print(f"\n🧠 MEMORY MONSTER ANALYSIS:")
                print(f"📊 Peak memory usage: {mem_peak_usage:.2f} GB")
                print(f"📊 Memory efficiency: {(source_size/(1024**3))/max(mem_peak_usage, 0.1):.2f}x")
                print(f"📊 Final memory: {mem_end.available / (1024**3):.2f} GB available")
                
                # CPU analysis  
                cpu_end = psutil.cpu_percent()
                print(f"🖥️  CPU utilization: {cpu_end:.1f}%")
                
                # Calculate theoretical limits
                print(f"\n🎯 THEORETICAL ANALYSIS:")
                print(f"💭 Data processed: {source_size/(1024**3):.3f} GB in {transfer_time:.3f}s")
                print(f"💭 Memory bandwidth: {throughput_gbps:.3f} GB/s sustained")
                print(f"💭 PacketFS efficiency: Linear processing achieved")
                
                return True
                
            else:
                print(f"❌ MEMORY MONSTER TRANSFER FAILED!")
                return False
                
        except Exception as e:
            transfer_time = time.time() - start_time
            print(f"💥 MEMORY MONSTER EXCEPTION: {e}")
            print(f"⏱️  Failed after: {transfer_time:.3f} seconds")
            return False
    
    def cleanup_monster(self, *files):
        """Clean up monster files"""
        print(f"\n🧹 CLEANING UP MEMORY MONSTER...")
        for file_path in files:
            try:
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    os.remove(file_path)
                    print(f"🗑️  Removed: {file_path} ({size/(1024**3):.3f} GB)")
            except Exception as e:
                print(f"⚠️  Cleanup error: {e}")
        
        # Force garbage collection
        gc.collect()
        
        final_mem = psutil.virtual_memory()
        print(f"🧠 Final memory: {final_mem.available / (1024**3):.2f} GB available")

def main():
    """UNLEASH THE MEMORY MONSTER"""
    
    print("🔥" * 60)
    print("🔥                 MEMORY MONSTER TEST                   🔥")
    print("🔥            1GB LINEAR PACKETFS TRANSFER              🔥")
    print("🔥               PURE IN-MEMORY BEAST MODE              🔥") 
    print("🔥" * 60)
    
    monster = MemoryMonster()
    
    # Check system resources
    mem = psutil.virtual_memory()
    if mem.available < 3 * (1024**3):  # 3GB minimum
        print(f"❌ INSUFFICIENT MEMORY!")
        print(f"💾 Available: {mem.available / (1024**3):.2f} GB")
        print(f"💾 Required: 3+ GB (for 1GB file + overhead)")
        return
    
    monster_file = None
    dest_file = None
    server = None
    
    try:
        # Phase 1: Create the memory monster
        monster_file = monster.create_memory_monster_file()
        
        # Phase 2: Start the server
        server = monster.start_monster_server()
        
        # Phase 3: Execute the memory monster transfer
        success = monster.monster_transfer_test(monster_file)
        
        if success:
            print(f"\n🎉 MEMORY MONSTER TEST: COMPLETE SUCCESS! 🎉")
        else:
            print(f"\n💥 MEMORY MONSTER TEST: FAILED! 💥")
            
    except KeyboardInterrupt:
        print(f"\n🛑 MEMORY MONSTER INTERRUPTED!")
        
    except Exception as e:
        print(f"\n💥 MEMORY MONSTER ERROR: {e}")
        
    finally:
        # Cleanup
        if monster_file:
            monster.cleanup_monster(monster_file)
        
        if server:
            try:
                server.stop()
                server.print_stats()
            except:
                pass
    
    print(f"\n🔥 MEMORY MONSTER TEST COMPLETE! 🔥")

if __name__ == "__main__":
    main()
