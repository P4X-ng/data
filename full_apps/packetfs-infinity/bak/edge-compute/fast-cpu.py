#!/usr/bin/env python3
"""
Fast Network CPU - Minimal implementation focused on speed
Uses HTTP status codes as the primary instruction set
"""

import asyncio
import aiohttp
import time
from typing import List, Dict

class FastNetworkCPU:
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        # Optimized session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=20,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(total=1.0, connect=0.5)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'NetworkCPU/1.0'}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def ADD(self, a: int, b: int) -> int:
        """ADD using httpbin status codes"""
        result = (a + b) % 600  # Keep in HTTP status range
        url = f"https://httpbin.org/status/{result}"
        try:
            async with self.session.get(url) as resp:
                return resp.status
        except:
            return result  # Fallback to computed value
    
    async def SUB(self, a: int, b: int) -> int:
        """SUB using different endpoints"""
        result = abs(a - b) % 600
        url = f"https://httpbin.org/status/{result}"
        try:
            async with self.session.get(url) as resp:
                return resp.status
        except:
            return result
    
    async def MUL(self, a: int, b: int) -> int:
        """MUL using response time as computation"""
        start = time.time()
        url = f"https://httpbin.org/delay/{min(a*b % 3, 2)}"
        try:
            async with self.session.get(url) as resp:
                elapsed_ms = int((time.time() - start) * 1000)
                return (a * b + elapsed_ms) % 256
        except:
            return (a * b) % 256

class AssetDB:
    """Database of fast network assets for computation"""
    def __init__(self):
        self.fast_endpoints = [
            "https://httpbin.org/status/{}",
            "https://jsonplaceholder.typicode.com/posts/{}",
            "https://api.github.com/zen",
            "https://httpstat.us/{}",
        ]
        self.cached_responses = {}
    
    def get_endpoint(self, instruction: str, value: int) -> str:
        """Get fastest endpoint for instruction"""
        if instruction == "ADD":
            return self.fast_endpoints[0].format(value % 600)
        elif instruction == "SUB":
            return self.fast_endpoints[1].format(value % 100)
        else:
            return self.fast_endpoints[0].format(value % 600)

async def speed_test():
    """Test network CPU speed"""
    print("🚀 Network CPU Speed Test")
    print("=" * 40)
    
    async with FastNetworkCPU() as cpu:
        # Simple computation: 5 + 3 - 2
        start_time = time.time()
        
        print("Computing: 5 + 3 - 2")
        
        # Sequential execution
        result1 = await cpu.ADD(5, 3)
        result2 = await cpu.SUB(result1, 2)
        
        sequential_time = time.time() - start_time
        
        print(f"Sequential result: {result2}")
        print(f"Sequential time: {sequential_time:.3f}s")
        
        # Parallel execution
        start_time = time.time()
        
        print("\nComputing in parallel: (5+3), (7-2), (4*2)")
        tasks = [
            cpu.ADD(5, 3),
            cpu.SUB(7, 2), 
            cpu.MUL(4, 2)
        ]
        
        results = await asyncio.gather(*tasks)
        parallel_time = time.time() - start_time
        
        print(f"Parallel results: {results}")
        print(f"Parallel time: {parallel_time:.3f}s")
        print(f"Speedup: {sequential_time/parallel_time:.1f}x")
        
        # Batch test
        print(f"\n🔥 Batch test: 20 ADD operations")
        start_time = time.time()
        
        batch_tasks = [cpu.ADD(i, i+1) for i in range(20)]
        batch_results = await asyncio.gather(*batch_tasks)
        
        batch_time = time.time() - start_time
        ops_per_sec = len(batch_tasks) / batch_time
        
        print(f"Batch time: {batch_time:.3f}s")
        print(f"Operations/sec: {ops_per_sec:.1f}")
        print(f"Average latency: {batch_time/len(batch_tasks)*1000:.1f}ms")

async def benchmark_program():
    """Run a simple program and benchmark it"""
    print("\n📊 Program Benchmark")
    print("=" * 40)
    
    # Simple program: Calculate (10 + 5) * 2 - 3
    async with FastNetworkCPU() as cpu:
        start = time.time()
        
        step1 = await cpu.ADD(10, 5)    # 15
        step2 = await cpu.MUL(step1, 2) # 30  
        step3 = await cpu.SUB(step2, 3) # 27
        
        total_time = time.time() - start
        
        print(f"Program: (10 + 5) * 2 - 3")
        print(f"Steps: {step1} → {step2} → {step3}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Instructions/sec: {3/total_time:.1f}")

if __name__ == "__main__":
    async def main():
        await speed_test()
        await benchmark_program()
    
    asyncio.run(main())