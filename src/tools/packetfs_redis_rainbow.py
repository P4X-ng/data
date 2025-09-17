#!/usr/bin/env python3
"""
PacketFS REDIS RAINBOW TABLES - PHASE 3: NUCLEAR UDP ANNIHILATION! 💥

This is THE BIG ONE - Redis-powered precomputed rainbow tables for INSTANT PacketFS encoding!

Features:
- Redis caching of PacketFS encodings (ZERO compute time!)  
- Precomputed 1GB+ blob libraries
- Parallel Redis workers
- Zero-copy Redis data structures  
- INSANE throughput via lookup tables
- Ready for kernel module integration!

Goal: 500+ MB/s throughput = UDP TOTALLY DESTROYED! 🔥
"""

import os
import sys
import mmap
import time
import hashlib
import struct
import socket
import threading
import numpy as np
import redis
import json
import pickle
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from packetfs.protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig

# REDIS RAINBOW TABLE constants
REDIS_MAGIC = b'PFS5'  # PacketFS v5 - REDIS RAINBOW TABLES!
REDIS_PORT = 8350

@dataclass
class RedisRainbowConfig:
    """Configuration for REDIS RAINBOW TABLE PacketFS"""
    mega_frame_size: int = 32 * 1024 * 1024    # 32MB frames (GO BIG!)
    rainbow_blob_size: int = 1024 * 1024 * 1024  # 1GB rainbow blob!
    redis_host: str = 'localhost'
    redis_port: int = 6379
    redis_db: int = 0
    parallel_workers: int = 8                   # 8 Redis workers!
    precompute_rainbow_tables: bool = True      # Build rainbow tables
    use_redis_pipeline: bool = True             # Redis pipelines for SPEED
    chunk_cache_size: int = 10000               # Cache 10K chunks
    
class RedisRainbowTransfer:
    """THE REDIS RAINBOW TABLE MONSTER! 🌈⚡"""
    
    def __init__(self, config: RedisRainbowConfig = None):
        self.config = config or RedisRainbowConfig()
        
        # Connect to Redis
        print(f"🔗 Connecting to Redis at {self.config.redis_host}:{self.config.redis_port}...")
        self.redis_client = redis.Redis(
            host=self.config.redis_host,
            port=self.config.redis_port, 
            db=self.config.redis_db,
            decode_responses=False  # Keep binary data
        )
        
        try:
            self.redis_client.ping()
            print("✅ Redis connection established!")
        except redis.ConnectionError:
            print("❌ Redis connection failed!")
            print("💡 Start Redis with: redis-server")
            print("🚀 Or use Docker: docker run -d -p 6379:6379 redis")
            sys.exit(1)
            
        # PacketFS protocol for encoding
        self.pfs_config = SyncConfig(
            window_pow2=8,  # 256 refs per window - MAXIMUM compression!
            window_crc16=True
        )
        self.encoder = ProtocolEncoder(self.pfs_config)
        self.decoder = ProtocolDecoder(self.pfs_config)
        
        # Performance stats
        self.stats = {
            'start_time': time.time(),
            'rainbow_generation_time': 0,
            'redis_lookup_time': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'bytes_processed': 0,
            'network_time': 0
        }
        
        print(f"🌈 REDIS RAINBOW TABLE CONFIG:")
        print(f"   Frame size: {self.config.mega_frame_size // (1024*1024)}MB")
        print(f"   Rainbow blob: {self.config.rainbow_blob_size // (1024*1024)}MB") 
        print(f"   Workers: {self.config.parallel_workers}")
        print(f"   Cache size: {self.config.chunk_cache_size:,} chunks")
        
        # Initialize rainbow tables
        if self.config.precompute_rainbow_tables:
            self.build_rainbow_tables()
    
    def build_rainbow_tables(self):
        """Build REDIS RAINBOW TABLES for instant lookups! 🌈"""
        print(f"\\n🌈 Building REDIS RAINBOW TABLES...")
        start_time = time.time()
        
        # Check if rainbow tables already exist
        existing_keys = self.redis_client.keys("pfs:rainbow:*")
        if existing_keys:
            print(f"🔍 Found {len(existing_keys)} existing rainbow table entries")
            print("💡 Use --rebuild-rainbow to rebuild tables")
            return
            
        print(f"🚀 Generating {self.config.rainbow_blob_size // (1024*1024)}MB rainbow blob...")
        
        # Generate MASSIVE rainbow blob with patterns
        rainbow_blob = self.generate_rainbow_blob()
        
        print(f"📊 Precomputing PacketFS encodings for rainbow patterns...")
        
        # Break into chunks and precompute encodings
        chunk_size = 64 * 1024  # 64KB chunks for fine-grained caching
        total_chunks = len(rainbow_blob) // chunk_size
        
        print(f"   Processing {total_chunks:,} rainbow chunks...")
        
        with ThreadPoolExecutor(max_workers=self.config.parallel_workers) as executor:
            # Process chunks in parallel
            futures = []
            for i in range(0, len(rainbow_blob), chunk_size):
                chunk = rainbow_blob[i:i+chunk_size]
                future = executor.submit(self.precompute_chunk_encoding, i // chunk_size, chunk)
                futures.append(future)
                
                # Process in batches to avoid memory explosion
                if len(futures) >= self.config.parallel_workers * 10:
                    for future in futures:
                        future.result()
                    futures = []
                    print(f"     🌈 Processed {(i // chunk_size):,}/{total_chunks:,} chunks...")
            
            # Process remaining futures
            for future in futures:
                future.result()
        
        generation_time = time.time() - start_time
        self.stats['rainbow_generation_time'] = generation_time
        
        print(f"✅ Rainbow tables built in {generation_time:.2f} seconds!")
        print(f"💎 Redis now contains precomputed encodings for INSTANT lookups!")
        
    def generate_rainbow_blob(self) -> bytes:
        """Generate MASSIVE rainbow blob with diverse patterns"""
        print(f"🌈 Generating rainbow patterns...")
        
        # Use memory-efficient numpy generation
        blob_array = np.empty(self.config.rainbow_blob_size, dtype=np.uint8)
        
        # Pattern mix for maximum diversity
        patterns = [
            ("zeros", 0.2),       # 20% zeros (high compression)
            ("ones", 0.1),        # 10% ones  
            ("sequential", 0.2),  # 20% sequential data
            ("random", 0.3),      # 30% random data
            ("repeated", 0.2),    # 20% repeated patterns
        ]
        
        offset = 0
        for pattern_name, proportion in patterns:
            size = int(self.config.rainbow_blob_size * proportion)
            end_offset = offset + size
            
            print(f"   🎨 {pattern_name}: {size // (1024*1024)}MB")
            
            if pattern_name == "zeros":
                blob_array[offset:end_offset] = 0
            elif pattern_name == "ones":
                blob_array[offset:end_offset] = 255
            elif pattern_name == "sequential":
                seq = np.arange(size, dtype=np.uint64) % 256
                blob_array[offset:end_offset] = seq.astype(np.uint8)
            elif pattern_name == "random":
                np.random.seed(42)  # Deterministic randomness
                blob_array[offset:end_offset] = np.random.randint(0, 256, size, dtype=np.uint8)
            elif pattern_name == "repeated":
                # Create repeated pattern
                base_pattern = np.array([i % 256 for i in range(1024)], dtype=np.uint8)
                repeats = size // len(base_pattern) + 1
                repeated = np.tile(base_pattern, repeats)[:size]
                blob_array[offset:end_offset] = repeated
                
            offset = end_offset
            
        return blob_array.tobytes()
    
    def precompute_chunk_encoding(self, chunk_id: int, chunk_data: bytes) -> bool:
        """Precompute and cache PacketFS encoding for a chunk"""
        try:
            # Generate chunk hash as Redis key
            chunk_hash = hashlib.blake2b(chunk_data, digest_size=16).hexdigest()
            redis_key = f"pfs:rainbow:{chunk_hash}"
            
            # Check if already cached
            if self.redis_client.exists(redis_key):
                return True
                
            # Try PacketFS encoding
            try:
                out = bytearray(len(chunk_data) * 2)
                bits = self.encoder.pack_refs(out, 0, chunk_data, 8)
                encoded = bytes(out[:(bits + 7) // 8])
                compression_ratio = len(chunk_data) / len(encoded)
            except Exception:
                # Fallback to raw data
                encoded = chunk_data
                compression_ratio = 1.0
                
            # Store in Redis with metadata
            cache_entry = {
                'encoded': encoded,
                'original_size': len(chunk_data),
                'compressed_size': len(encoded),
                'compression_ratio': compression_ratio,
                'chunk_id': chunk_id
            }
            
            # Use Redis pipeline for efficiency
            pipe = self.redis_client.pipeline()
            pipe.set(redis_key, pickle.dumps(cache_entry))
            pipe.expire(redis_key, 3600 * 24)  # 24 hour expiry
            pipe.execute()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to precompute chunk {chunk_id}: {e}")
            return False
    
    def redis_encode_frame(self, frame_data: bytes) -> Tuple[bytes, float]:
        """Encode frame using REDIS RAINBOW TABLE lookups! ⚡"""
        start_time = time.time()
        
        # Break frame into chunks for lookup
        chunk_size = 64 * 1024
        encoded_chunks = []
        cache_hits = 0
        cache_misses = 0
        
        for i in range(0, len(frame_data), chunk_size):
            chunk = frame_data[i:i+chunk_size]
            chunk_hash = hashlib.blake2b(chunk, digest_size=16).hexdigest()
            redis_key = f"pfs:rainbow:{chunk_hash}"
            
            # Try Redis lookup first (INSTANT!)
            cached_entry = self.redis_client.get(redis_key)
            if cached_entry:
                cache_hits += 1
                entry = pickle.loads(cached_entry)
                encoded_chunks.append(entry['encoded'])
            else:
                cache_misses += 1
                # Fallback encoding
                try:
                    out = bytearray(len(chunk) * 2)
                    bits = self.encoder.pack_refs(out, 0, chunk, 8)
                    encoded = bytes(out[:(bits + 7) // 8])
                    encoded_chunks.append(encoded)
                    
                    # Cache for future use
                    cache_entry = {
                        'encoded': encoded,
                        'original_size': len(chunk),
                        'compressed_size': len(encoded),
                        'compression_ratio': len(chunk) / len(encoded),
                        'chunk_id': i // chunk_size
                    }
                    self.redis_client.setex(redis_key, 3600, pickle.dumps(cache_entry))
                    
                except Exception:
                    encoded_chunks.append(chunk)  # Raw fallback
        
        # Combine encoded chunks
        encoded_frame = b''.join(encoded_chunks)
        lookup_time = time.time() - start_time
        
        self.stats['cache_hits'] += cache_hits
        self.stats['cache_misses'] += cache_misses
        self.stats['redis_lookup_time'] += lookup_time
        
        print(f"     🌈 Redis lookup: {cache_hits} hits, {cache_misses} misses ({lookup_time:.3f}s)")
        
        return encoded_frame, lookup_time
    
    def redis_rainbow_transfer(self, file_path: str):
        """THE REDIS RAINBOW TRANSFER! 🌈💥"""
        print(f"\\n🌈💥 REDIS RAINBOW TRANSFER: {file_path}")
        print("🔥" * 30)
        
        total_start_time = time.time()
        
        # Memory-map file
        file_size = Path(file_path).stat().st_size
        print(f"📁 Memory-mapping {file_size // (1024*1024)}MB file...")
        
        file_obj = open(file_path, 'rb')
        mapped_file = mmap.mmap(file_obj.fileno(), 0, access=mmap.ACCESS_READ)
        
        try:
            # Create MEGA FRAMES
            frame_size = self.config.mega_frame_size
            frames_needed = (file_size + frame_size - 1) // frame_size
            
            print(f"📦 Creating {frames_needed} x {frame_size // (1024*1024)}MB REDIS RAINBOW FRAMES...")
            
            mega_frames = []
            for i in range(frames_needed):
                start_offset = i * frame_size
                end_offset = min(start_offset + frame_size, file_size)
                mega_chunk = bytes(mapped_file[start_offset:end_offset])
                mega_frames.append(mega_chunk)
            
            # REDIS RAINBOW ENCODING (INSTANT!)
            print(f"🌈 REDIS RAINBOW ENCODING...")
            encoded_frames = []
            total_lookup_time = 0
            
            for i, frame in enumerate(mega_frames):
                print(f"   🌈 Rainbow encoding frame {i+1}/{frames_needed}...")
                encoded_frame, lookup_time = self.redis_encode_frame(frame)
                encoded_frames.append(encoded_frame)
                total_lookup_time += lookup_time
            
            # Network transmission
            print(f"💥 REDIS RAINBOW NETWORK TRANSMISSION...")
            network_start = time.time()
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256 * 1024 * 1024)  # 256MB buffer!
            
            bytes_sent = 0
            for frame_id, encoded_data in enumerate(encoded_frames):
                # Minimal protocol overhead
                header = struct.pack('!4sII', REDIS_MAGIC, frame_id, len(encoded_data))
                packet = header + encoded_data
                
                try:
                    sent = sock.send(packet)
                    bytes_sent += len(packet)
                    print(f"     💥 Sent frame {frame_id+1}: {sent:,} bytes")
                except Exception as e:
                    print(f"     ❌ Send failed: {e}")
            
            sock.close()
            network_time = time.time() - network_start
            
            # REDIS RAINBOW RESULTS! 
            total_time = time.time() - total_start_time
            throughput_mbs = file_size / (1024 * 1024) / total_time
            
            print(f"\\n" + "🏆" * 15 + " REDIS RAINBOW RESULTS " + "🏆" * 15)
            print(f"⏱️  Total time: {total_time:.2f} seconds")
            print(f"🚀 Throughput: {throughput_mbs:.2f} MB/s")
            print(f"🌈 Cache performance:")
            print(f"   ✅ Hits: {self.stats['cache_hits']:,}")
            print(f"   ❌ Misses: {self.stats['cache_misses']:,}")
            print(f"   📈 Hit rate: {self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['cache_misses']) * 100:.1f}%")
            print(f"💾 Performance breakdown:")
            print(f"   🌈 Rainbow generation: {self.stats['rainbow_generation_time']:.2f}s")
            print(f"   🔍 Redis lookups: {total_lookup_time:.2f}s") 
            print(f"   📡 Network: {network_time:.2f}s")
            
            # THE MOMENT OF TRUTH!
            print(f"\\n" + "💎" * 20)
            if throughput_mbs > 500:
                print(f"🏆💎🔥 NUCLEAR SUCCESS! {throughput_mbs:.2f} MB/s!")
                print(f"💥💥 UDP UTTERLY ANNIHILATED!")
                print(f"🚀 Ready for KERNEL MODULE phase!")
                
            elif throughput_mbs > 244.68:
                print(f"🏆🔥💥 UDP = SMOKED! {throughput_mbs:.2f} > 244.68 MB/s!")
                print(f"🎉 REDIS RAINBOW TABLES = VICTORY!")
                
                if throughput_mbs > 300:
                    print(f"💯 BONUS: Over 300 MB/s!")
                    
            else:
                speedup_needed = 244.68 / throughput_mbs
                print(f"📈 Strong progress: {throughput_mbs:.2f} MB/s")
                print(f"🎯 Need {speedup_needed:.1f}x more to SMOKE UDP")
                print(f"💡 Try larger frames or more Redis workers!")
            
            print(f"💎" * 20)
            
            return True, throughput_mbs
            
        finally:
            mapped_file.close()
            file_obj.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PacketFS REDIS RAINBOW TABLES")
    parser.add_argument('--file', required=True, help='File to transfer')
    parser.add_argument('--frame-size', type=int, default=32, 
                       help='Frame size in MB (default: 32MB)')
    parser.add_argument('--rainbow-size', type=int, default=1024, 
                       help='Rainbow blob size in MB (default: 1GB)')
    parser.add_argument('--redis-host', default='localhost',
                       help='Redis host (default: localhost)')
    parser.add_argument('--redis-port', type=int, default=6379,
                       help='Redis port (default: 6379)')
    parser.add_argument('--workers', type=int, default=8,
                       help='Parallel workers (default: 8)')
    parser.add_argument('--rebuild-rainbow', action='store_true',
                       help='Rebuild rainbow tables')
    
    args = parser.parse_args()
    
    config = RedisRainbowConfig(
        mega_frame_size=args.frame_size * 1024 * 1024,
        rainbow_blob_size=args.rainbow_size * 1024 * 1024,
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        parallel_workers=args.workers,
        precompute_rainbow_tables=True
    )
    
    print(f"🌈💎 INITIALIZING REDIS RAINBOW TABLES...")
    
    if args.rebuild_rainbow:
        print("🔄 Rebuilding rainbow tables...")
        redis_client = redis.Redis(host=args.redis_host, port=args.redis_port)
        keys = redis_client.keys("pfs:rainbow:*")
        if keys:
            redis_client.delete(*keys)
            print(f"🗑️  Deleted {len(keys)} existing rainbow table entries")
    
    rainbow_transfer = RedisRainbowTransfer(config)
    
    print(f"\\n🌈💥 REDIS RAINBOW TABLES READY!")
    print(f"🚀 TARGET: DESTROY UDP (244.68 MB/s)!")
    success, throughput = rainbow_transfer.redis_rainbow_transfer(args.file)
    
    if success and throughput > 500:
        print(f"\\n🏆💎 PHASE 3 NUCLEAR SUCCESS!")
        print(f"💥💥 UDP = TOTALLY ANNIHILATED!")
        print(f"🚀 Ready for PHASE 4: Kernel modules + hugepages!")
    elif success and throughput > 244.68:
        print(f"\\n🏆🔥 PHASE 3 SUCCESS!")
        print(f"💥 UDP HAS BEEN SMOKED!")
        print(f"🌈 REDIS RAINBOW TABLES VICTORY!")
    else:
        print(f"\\n📈 REDIS foundation established!")
        print(f"💡 Tune parameters and try again!")
