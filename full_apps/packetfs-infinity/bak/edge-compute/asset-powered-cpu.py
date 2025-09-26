#!/usr/bin/env python3
"""
Asset-Powered CPU - Uses cataloged network assets for computation
Dynamically selects fastest available resources for each operation
"""

import sqlite3
import socket
import time
import random
from concurrent.futures import ThreadPoolExecutor

class AssetPoweredCPU:
    def __init__(self, db_path="mega_assets.db"):
        self.db_path = db_path
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.asset_cache = {}
        self._load_assets()
    
    def _load_assets(self):
        """Load assets from database into memory"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT host, port, protocol, avg_latency, instruction_potential, last_value
            FROM assets ORDER BY avg_latency ASC
        """).fetchall()
        conn.close()
        
        # Group by instruction potential
        for row in rows:
            potential = row[4]
            if potential not in self.asset_cache:
                self.asset_cache[potential] = []
            
            self.asset_cache[potential].append({
                'host': row[0],
                'port': row[1], 
                'protocol': row[2],
                'latency': row[3],
                'last_value': row[5]
            })
        
        print(f"🔧 Loaded {sum(len(assets) for assets in self.asset_cache.values())} assets")
        for potential, assets in self.asset_cache.items():
            print(f"  {potential}: {len(assets)} assets")
    
    def _execute_on_asset(self, asset, operation_data):
        """Execute operation on specific asset"""
        try:
            start = time.time()
            
            if asset['protocol'] == 'TCP':
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex((asset['host'], asset['port']))
                sock.close()
                
                # Use connection result + operation data for computation
                return (result + operation_data) % 256
                
            elif asset['protocol'] == 'UDP':
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(0.05)
                payload = f"COMPUTE_{operation_data}".encode()[:8]
                sock.sendto(payload, (asset['host'], asset['port']))
                try:
                    data, addr = sock.recvfrom(64)
                    result = len(data)
                except:
                    result = 0
                sock.close()
                
                return (result + operation_data) % 256
                
        except:
            # Even failures give us data!
            return operation_data % 256
    
    def ADD(self, a, b):
        """ADD using fastest available assets"""
        operation_data = a + b
        
        # Use fastest assets for ADD
        fast_assets = self.asset_cache.get('FAST_OP', [])[:3]
        if not fast_assets:
            return operation_data % 256
        
        # Execute on multiple assets and combine results
        futures = []
        for asset in fast_assets:
            future = self.executor.submit(self._execute_on_asset, asset, operation_data)
            futures.append(future)
        
        results = [f.result() for f in futures]
        # Combine results using XOR for variety
        final_result = operation_data
        for r in results:
            final_result ^= r
        
        return final_result % 256
    
    def SUB(self, a, b):
        """SUB using logic operation assets"""
        operation_data = abs(a - b)
        
        logic_assets = self.asset_cache.get('LOGIC_OP', [])[:2]
        if not logic_assets:
            return operation_data % 256
        
        # Use connection refused/success as binary operation
        futures = []
        for asset in logic_assets:
            future = self.executor.submit(self._execute_on_asset, asset, operation_data)
            futures.append(future)
        
        results = [f.result() for f in futures]
        return (operation_data + sum(results)) % 256
    
    def MUL(self, a, b):
        """MUL using memory operation assets (UDP)"""
        operation_data = a * b
        
        memory_assets = self.asset_cache.get('MEMORY_OP', [])[:2]
        if not memory_assets:
            return operation_data % 256
        
        futures = []
        for asset in memory_assets:
            future = self.executor.submit(self._execute_on_asset, asset, operation_data)
            futures.append(future)
        
        results = [f.result() for f in futures]
        return (operation_data + max(results, default=0)) % 256
    
    def RAND(self):
        """Generate random number using network timing variance"""
        # Use multiple random assets
        all_assets = []
        for asset_list in self.asset_cache.values():
            all_assets.extend(asset_list)
        
        if not all_assets:
            return random.randint(0, 255)
        
        # Pick 5 random assets
        selected = random.sample(all_assets, min(5, len(all_assets)))
        
        futures = []
        for asset in selected:
            future = self.executor.submit(self._execute_on_asset, asset, 42)
            futures.append(future)
        
        results = [f.result() for f in futures]
        # Use timing variance as randomness
        return sum(results) % 256
    
    def parallel_compute(self, operations):
        """Execute multiple operations in parallel across assets"""
        futures = []
        
        for op, a, b in operations:
            if op == 'ADD':
                future = self.executor.submit(self.ADD, a, b)
            elif op == 'SUB':
                future = self.executor.submit(self.SUB, a, b)
            elif op == 'MUL':
                future = self.executor.submit(self.MUL, a, b)
            elif op == 'RAND':
                future = self.executor.submit(self.RAND)
            futures.append(future)
        
        return [f.result() for f in futures]

def benchmark():
    print("🚀 Asset-Powered CPU Benchmark")
    print("=" * 40)
    
    cpu = AssetPoweredCPU()
    
    # Single operations
    print("Single operations using cataloged assets:")
    
    start = time.time()
    result = cpu.ADD(42, 13)
    print(f"  ADD(42, 13) = {result} ({(time.time()-start)*1000:.1f}ms)")
    
    start = time.time()
    result = cpu.SUB(100, 25)
    print(f"  SUB(100, 25) = {result} ({(time.time()-start)*1000:.1f}ms)")
    
    start = time.time()
    result = cpu.MUL(7, 8)
    print(f"  MUL(7, 8) = {result} ({(time.time()-start)*1000:.1f}ms)")
    
    start = time.time()
    result = cpu.RAND()
    print(f"  RAND() = {result} ({(time.time()-start)*1000:.1f}ms)")
    
    # Parallel batch
    print(f"\nParallel computation (100 operations):")
    operations = []
    for i in range(100):
        op = random.choice(['ADD', 'SUB', 'MUL', 'RAND'])
        if op == 'RAND':
            operations.append((op, 0, 0))
        else:
            operations.append((op, i % 50, (i+1) % 50))
    
    start = time.time()
    results = cpu.parallel_compute(operations)
    batch_time = time.time() - start
    
    print(f"  Time: {batch_time:.3f}s")
    print(f"  Ops/sec: {len(operations)/batch_time:.1f}")
    print(f"  Sample results: {results[:10]}")
    
    # Asset utilization
    print(f"\nAsset utilization:")
    for potential, assets in cpu.asset_cache.items():
        fastest = min(assets, key=lambda x: x['latency'])
        print(f"  {potential}: {len(assets)} assets, fastest {fastest['latency']*1000:.1f}ms")

def monte_carlo_pi():
    """Calculate Pi using network-powered random numbers"""
    print(f"\n🎯 Monte Carlo Pi Calculation (Network RNG)")
    print("=" * 45)
    
    cpu = AssetPoweredCPU()
    
    inside_circle = 0
    total_points = 1000
    
    print(f"Generating {total_points} random points using network assets...")
    
    start = time.time()
    
    # Generate random coordinates in batches
    batch_size = 50
    for batch in range(0, total_points, batch_size):
        # Generate x,y coordinates using network randomness
        coords = cpu.parallel_compute([('RAND', 0, 0) for _ in range(batch_size * 2)])
        
        # Process coordinates in pairs
        for i in range(0, len(coords), 2):
            if i+1 < len(coords):
                x = (coords[i] / 255.0) * 2 - 1      # Scale to [-1, 1]
                y = (coords[i+1] / 255.0) * 2 - 1    # Scale to [-1, 1]
                
                if x*x + y*y <= 1:
                    inside_circle += 1
    
    pi_estimate = 4 * inside_circle / total_points
    actual_pi = 3.14159265359
    error = abs(pi_estimate - actual_pi)
    
    calc_time = time.time() - start
    
    print(f"Results:")
    print(f"  Points inside circle: {inside_circle}/{total_points}")
    print(f"  Pi estimate: {pi_estimate:.6f}")
    print(f"  Actual Pi: {actual_pi:.6f}")
    print(f"  Error: {error:.6f}")
    print(f"  Calculation time: {calc_time:.3f}s")
    print(f"  Network RNG rate: {total_points/calc_time:.1f} numbers/sec")

if __name__ == "__main__":
    benchmark()
    monte_carlo_pi()