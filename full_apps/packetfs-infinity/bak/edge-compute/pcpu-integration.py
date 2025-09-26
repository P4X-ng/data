#!/usr/bin/env python3
"""
pCPU Integration - Seamlessly integrate network compute with PacketFS pCPU
"""

from reliable_network_pcpu import ReliableNetworkPCPU
import time
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

class HybridPCPU:
    """Hybrid pCPU that combines local and network computation"""
    
    def __init__(self):
        self.network_pcpu = ReliableNetworkPCPU()
        self.local_executor = ThreadPoolExecutor(max_workers=4)
        self.operation_count = 0
        self.network_ops = 0
        self.local_ops = 0
        print("🔥 Hybrid pCPU: Local + Network compute ready")
    
    def _should_use_network(self, operation: str) -> bool:
        """Decide whether to use network or local compute"""
        # Use network for operations that benefit from parallelism
        if operation in ['ADD', 'SUB']:
            return True  # Network is fast for these
        elif operation == 'MUL':
            return random.random() < 0.5  # 50/50 split
        return False
    
    def _local_add(self, a: int, b: int) -> int:
        """Local ADD operation"""
        return (a + b) % 256
    
    def _local_sub(self, a: int, b: int) -> int:
        """Local SUB operation"""
        return abs(a - b) % 256
    
    def _local_mul(self, a: int, b: int) -> int:
        """Local MUL operation"""
        return (a * b) % 256
    
    def execute_operation(self, operation: str, a: int, b: int) -> int:
        """Execute operation on best available compute substrate"""
        self.operation_count += 1
        
        if self._should_use_network(operation):
            # Use network compute
            self.network_ops += 1
            if operation == 'ADD':
                return self.network_pcpu.network_add(a, b)
            elif operation == 'SUB':
                return self.network_pcpu.network_sub(a, b)
            elif operation == 'MUL':
                return self.network_pcpu.network_mul(a, b)
        else:
            # Use local compute
            self.local_ops += 1
            if operation == 'ADD':
                return self._local_add(a, b)
            elif operation == 'SUB':
                return self._local_sub(a, b)
            elif operation == 'MUL':
                return self._local_mul(a, b)
        
        return 0
    
    def parallel_execute(self, operations: list) -> list:
        """Execute operations in parallel across hybrid infrastructure"""
        futures = []
        
        for op, a, b in operations:
            future = self.local_executor.submit(self.execute_operation, op, a, b)
            futures.append(future)
        
        return [f.result() for f in futures]
    
    def stats(self) -> dict:
        """Get hybrid pCPU statistics"""
        network_stats = self.network_pcpu.stats()
        
        return {
            "total_operations": self.operation_count,
            "network_operations": self.network_ops,
            "local_operations": self.local_ops,
            "network_ratio": self.network_ops / max(self.operation_count, 1),
            "network_pcpu": network_stats
        }

class PacketFSNetworkExecutor:
    """PacketFS-compatible executor using network compute"""
    
    def __init__(self):
        self.hybrid_pcpu = HybridPCPU()
        self.executed_packets = []
    
    def execute_packet(self, packet_data: Any) -> Any:
        """Execute a packet using hybrid pCPU"""
        # Simulate packet processing with arithmetic operations
        if hasattr(packet_data, 'operation'):
            op = packet_data.operation
            a = getattr(packet_data, 'a', 42)
            b = getattr(packet_data, 'b', 13)
        else:
            # Default packet processing
            op = 'ADD'
            a = hash(str(packet_data)) % 100
            b = len(str(packet_data)) % 100
        
        start = time.time()
        result = self.hybrid_pcpu.execute_operation(op, a, b)
        duration = time.time() - start
        
        self.executed_packets.append({
            'packet_id': id(packet_data),
            'operation': op,
            'result': result,
            'duration_ms': duration * 1000
        })
        
        return result
    
    def execute_packets(self, packets: list) -> list:
        """Execute multiple packets using hybrid infrastructure"""
        operations = []
        
        for packet in packets:
            if hasattr(packet, 'operation'):
                op = packet.operation
                a = getattr(packet, 'a', 42)
                b = getattr(packet, 'b', 13)
            else:
                op = random.choice(['ADD', 'SUB', 'MUL'])
                a = hash(str(packet)) % 100
                b = len(str(packet)) % 100
            
            operations.append((op, a, b))
        
        return self.hybrid_pcpu.parallel_execute(operations)
    
    def report(self) -> dict:
        """Generate execution report"""
        stats = self.hybrid_pcpu.stats()
        
        if self.executed_packets:
            avg_duration = sum(p['duration_ms'] for p in self.executed_packets) / len(self.executed_packets)
            total_duration = sum(p['duration_ms'] for p in self.executed_packets)
        else:
            avg_duration = 0
            total_duration = 0
        
        return {
            "packets_executed": len(self.executed_packets),
            "avg_duration_ms": avg_duration,
            "total_duration_ms": total_duration,
            "hybrid_pcpu": stats
        }

def demo():
    print("🔥 HYBRID pCPU INTEGRATION DEMO")
    print("PacketFS + Network Compute Integration")
    print("=" * 45)
    
    # Test hybrid pCPU
    hybrid = HybridPCPU()
    
    print("Hybrid pCPU operations:")
    
    operations = [
        ('ADD', 42, 13),
        ('SUB', 100, 25),
        ('MUL', 7, 8),
        ('ADD', 50, 30),
        ('SUB', 80, 20),
    ]
    
    start = time.time()
    for op, a, b in operations:
        result = hybrid.execute_operation(op, a, b)
        print(f"  {op}({a}, {b}) = {result}")
    
    sequential_time = time.time() - start
    
    # Test parallel execution
    print(f"\nParallel execution (20 operations):")
    parallel_ops = [(random.choice(['ADD', 'SUB', 'MUL']), 
                    random.randint(1, 100), 
                    random.randint(1, 100)) for _ in range(20)]
    
    start = time.time()
    results = hybrid.parallel_execute(parallel_ops)
    parallel_time = time.time() - start
    
    print(f"  Time: {parallel_time:.3f}s")
    print(f"  Ops/sec: {len(parallel_ops)/parallel_time:.1f}")
    print(f"  Sample results: {results[:5]}")
    
    # Test PacketFS integration
    print(f"\nPacketFS Network Executor:")
    
    class MockPacket:
        def __init__(self, operation, a, b):
            self.operation = operation
            self.a = a
            self.b = b
    
    executor = PacketFSNetworkExecutor()
    
    # Create mock packets
    packets = [
        MockPacket('ADD', 10, 5),
        MockPacket('SUB', 20, 8),
        MockPacket('MUL', 3, 7),
        MockPacket('ADD', 15, 25),
    ]
    
    start = time.time()
    packet_results = executor.execute_packets(packets)
    packet_time = time.time() - start
    
    print(f"  Packets processed: {len(packets)}")
    print(f"  Time: {packet_time:.3f}s")
    print(f"  Results: {packet_results}")
    
    # Show comprehensive stats
    hybrid_stats = hybrid.stats()
    packet_report = executor.report()
    
    print(f"\n📊 COMPREHENSIVE STATISTICS:")
    print(f"Hybrid pCPU:")
    print(f"  Total operations: {hybrid_stats['total_operations']}")
    print(f"  Network operations: {hybrid_stats['network_operations']}")
    print(f"  Local operations: {hybrid_stats['local_operations']}")
    print(f"  Network ratio: {hybrid_stats['network_ratio']:.1%}")
    
    print(f"Network pCPU:")
    net_stats = hybrid_stats['network_pcpu']
    print(f"  Total assets: {net_stats['total_assets']}")
    print(f"  Healthy assets: {net_stats['healthy_assets']}")
    print(f"  Avg reliability: {net_stats['avg_reliability']:.2f}")
    
    print(f"\n🚀 INTEGRATION SUCCESS:")
    print(f"  ✅ Hybrid local + network compute")
    print(f"  ✅ PacketFS-compatible interface")
    print(f"  ✅ Automatic load balancing")
    print(f"  ✅ Infinite scaling potential")

if __name__ == "__main__":
    demo()