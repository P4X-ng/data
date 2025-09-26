#!/usr/bin/env python3
"""
Simple Asset CPU - Uses cataloged assets but with simpler logic
"""

import sqlite3
import socket
import time
import random

class SimpleAssetCPU:
    def __init__(self):
        self.fast_assets = self._load_fast_assets()
        print(f"🔧 Loaded {len(self.fast_assets)} fast assets")
    
    def _load_fast_assets(self):
        """Load fastest assets from database"""
        try:
            conn = sqlite3.connect("mega_assets.db")
            rows = conn.execute("""
                SELECT host, port FROM assets 
                WHERE avg_latency < 0.01 
                ORDER BY avg_latency ASC LIMIT 20
            """).fetchall()
            conn.close()
            return [(host, port) for host, port in rows]
        except:
            # Fallback to localhost ports
            return [('127.0.0.1', 22), ('127.0.0.1', 80), ('127.0.0.1', 443)]
    
    def _quick_ping(self, host, port):
        """Quick ping to get a value"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.05)
            result = sock.connect_ex((host, port))
            sock.close()
            return result
        except:
            return 111  # Connection refused
    
    def ADD(self, a, b):
        """ADD using network asset"""
        basic_result = (a + b) % 256
        
        # Pick random fast asset
        if self.fast_assets:
            host, port = random.choice(self.fast_assets)
            network_value = self._quick_ping(host, port)
            return (basic_result + network_value) % 256
        
        return basic_result
    
    def SUB(self, a, b):
        """SUB using different asset"""
        basic_result = abs(a - b) % 256
        
        if len(self.fast_assets) > 1:
            host, port = random.choice(self.fast_assets[1:])
            network_value = self._quick_ping(host, port)
            return (basic_result ^ network_value) % 256  # XOR for variety
        
        return basic_result
    
    def MUL(self, a, b):
        """MUL using multiple assets"""
        basic_result = (a * b) % 256
        
        if len(self.fast_assets) >= 2:
            # Use two assets
            val1 = self._quick_ping(*self.fast_assets[0])
            val2 = self._quick_ping(*self.fast_assets[1])
            network_modifier = (val1 + val2) % 16  # Small modifier
            return (basic_result + network_modifier) % 256
        
        return basic_result

def speed_test():
    print("🚀 Simple Asset CPU Speed Test")
    print("=" * 35)
    
    cpu = SimpleAssetCPU()
    
    # Test individual operations
    operations = [
        ("ADD", 42, 13),
        ("SUB", 100, 25), 
        ("MUL", 7, 8),
        ("ADD", 5, 3),
        ("SUB", 50, 20),
    ]
    
    print("Individual operations:")
    total_time = 0
    
    for op, a, b in operations:
        start = time.time()
        
        if op == "ADD":
            result = cpu.ADD(a, b)
        elif op == "SUB":
            result = cpu.SUB(a, b)
        elif op == "MUL":
            result = cpu.MUL(a, b)
        
        op_time = time.time() - start
        total_time += op_time
        
        print(f"  {op}({a}, {b}) = {result} ({op_time*1000:.1f}ms)")
    
    print(f"\nTotal time: {total_time:.3f}s")
    print(f"Average: {total_time/len(operations)*1000:.1f}ms per operation")
    print(f"Ops/sec: {len(operations)/total_time:.1f}")

def batch_test():
    print(f"\n📦 Batch Test (50 operations)")
    print("=" * 30)
    
    cpu = SimpleAssetCPU()
    
    # Generate random operations
    ops = []
    for i in range(50):
        op = random.choice(["ADD", "SUB", "MUL"])
        a = random.randint(1, 100)
        b = random.randint(1, 100)
        ops.append((op, a, b))
    
    start = time.time()
    results = []
    
    for op, a, b in ops:
        if op == "ADD":
            result = cpu.ADD(a, b)
        elif op == "SUB":
            result = cpu.SUB(a, b)
        elif op == "MUL":
            result = cpu.MUL(a, b)
        results.append(result)
    
    batch_time = time.time() - start
    
    print(f"Time: {batch_time:.3f}s")
    print(f"Ops/sec: {len(ops)/batch_time:.1f}")
    print(f"Sample results: {results[:10]}")

def asset_stats():
    print(f"\n📊 Asset Statistics")
    print("=" * 20)
    
    try:
        conn = sqlite3.connect("mega_assets.db")
        
        # Count by type
        by_type = conn.execute("""
            SELECT instruction_potential, COUNT(*) 
            FROM assets GROUP BY instruction_potential
        """).fetchall()
        
        print("Assets by type:")
        for pot_type, count in by_type:
            print(f"  {pot_type}: {count}")
        
        # Fastest assets
        fastest = conn.execute("""
            SELECT host, port, avg_latency*1000 as ms
            FROM assets ORDER BY avg_latency ASC LIMIT 10
        """).fetchall()
        
        print(f"\nTop 10 fastest assets:")
        for host, port, ms in fastest:
            print(f"  {host}:{port} - {ms:.1f}ms")
        
        conn.close()
        
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    speed_test()
    batch_test()
    asset_stats()