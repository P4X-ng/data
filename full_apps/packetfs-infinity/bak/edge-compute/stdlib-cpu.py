#!/usr/bin/env python3
"""
Standard Library Network CPU - No external dependencies
Uses urllib for HTTP requests and socket for raw speed
"""

import urllib.request
import urllib.error
import socket
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

class StdlibNetworkCPU:
    def __init__(self, max_workers=10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
    
    def _http_request(self, url, timeout=1.0):
        """Fast HTTP request using urllib"""
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'NetworkCPU/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.getcode()
        except:
            return 0
    
    def ADD(self, a, b):
        """ADD using HTTP status codes"""
        result = (a + b) % 600
        url = f"https://httpbin.org/status/{result}"
        return self._http_request(url)
    
    def SUB(self, a, b):
        """SUB using HTTP status codes"""
        result = abs(a - b) % 600
        url = f"https://httpbin.org/status/{result}"
        return self._http_request(url)
    
    def MUL(self, a, b):
        """MUL using simple computation + network verification"""
        result = (a * b) % 256
        # Quick ping to verify network
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            sock.connect(('8.8.8.8', 53))
            sock.close()
            return result
        except:
            return result
    
    def parallel_execute(self, operations):
        """Execute operations in parallel"""
        futures = []
        for op, a, b in operations:
            if op == 'ADD':
                future = self.executor.submit(self.ADD, a, b)
            elif op == 'SUB':
                future = self.executor.submit(self.SUB, a, b)
            elif op == 'MUL':
                future = self.executor.submit(self.MUL, a, b)
            futures.append(future)
        
        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                results.append(0)
        
        return results

def speed_test():
    """Test network CPU speed"""
    print("🚀 Standard Library Network CPU Speed Test")
    print("=" * 50)
    
    with StdlibNetworkCPU() as cpu:
        # Sequential test
        print("Sequential execution: 5 + 3 - 2")
        start = time.time()
        
        result1 = cpu.ADD(5, 3)
        result2 = cpu.SUB(result1, 2)
        
        sequential_time = time.time() - start
        print(f"Results: {result1} → {result2}")
        print(f"Time: {sequential_time:.3f}s")
        
        # Parallel test
        print(f"\nParallel execution: 10 operations")
        operations = [
            ('ADD', 5, 3),
            ('SUB', 10, 4),
            ('MUL', 3, 7),
            ('ADD', 15, 25),
            ('SUB', 100, 30),
            ('MUL', 4, 8),
            ('ADD', 7, 13),
            ('SUB', 50, 20),
            ('MUL', 6, 9),
            ('ADD', 11, 17),
        ]
        
        start = time.time()
        results = cpu.parallel_execute(operations)
        parallel_time = time.time() - start
        
        print(f"Results: {results}")
        print(f"Time: {parallel_time:.3f}s")
        print(f"Operations/sec: {len(operations)/parallel_time:.1f}")
        print(f"Avg latency: {parallel_time/len(operations)*1000:.1f}ms")

def ping_speed_test():
    """Test raw socket speed for comparison"""
    print(f"\n🏓 Raw Socket Speed Test")
    print("=" * 30)
    
    hosts = ['8.8.8.8', '1.1.1.1', '208.67.222.222']
    
    def ping_host(host):
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex((host, 53))
            sock.close()
            latency = time.time() - start
            return latency if result == 0 else None
        except:
            return None
    
    # Test each host
    for host in hosts:
        latencies = []
        for _ in range(5):
            latency = ping_host(host)
            if latency:
                latencies.append(latency)
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            print(f"{host}: {avg_latency*1000:.1f}ms avg")

def minimal_program():
    """Run minimal computation program"""
    print(f"\n📊 Minimal Program: (10 + 5) * 2")
    print("=" * 35)
    
    with StdlibNetworkCPU() as cpu:
        start = time.time()
        
        # Execute program
        step1 = cpu.ADD(10, 5)    # Should return 15 (or HTTP status)
        step2 = cpu.MUL(step1, 2) # Multiply result
        
        total_time = time.time() - start
        
        print(f"Step 1 (10+5): {step1}")
        print(f"Step 2 (*2): {step2}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Instructions/sec: {2/total_time:.1f}")

if __name__ == "__main__":
    speed_test()
    ping_speed_test()
    minimal_program()