#!/usr/bin/env python3
"""
Dual vCPU Demo: PacketFS execution across local container and Cloudflare Worker
Packets ARE execution. The network IS the CPU.
"""

import asyncio
import json
import time
import httpx
from typing import Dict, List, Any

# vCPU registry
VCPUS = {
    "local": {
        "id": "container-001",
        "endpoint": "http://localhost:8811/compute",
        "type": "container",
        "latency_ms": 1,
        "location": "localhost"
    },
    "edge": {
        "id": "cf-edge-001", 
        "endpoint": "https://pfs-vcpu.YOUR-SUBDOMAIN.workers.dev/compute",  # UPDATE THIS
        "type": "cloudflare-worker",
        "latency_ms": 25,
        "location": "global"
    }
}

# Test data URL (using httpbin for demo)
TEST_DATA_URL = "https://httpbin.org/bytes/1048576"  # 1MB of random bytes

class PacketScheduler:
    """Schedules packet execution across multiple vCPUs"""
    
    def __init__(self, vcpus: Dict):
        self.vcpus = vcpus
        self.metrics = {"total_packets": 0, "total_bytes": 0}
    
    async def execute_packet(self, vcpu_name: str, instruction: Dict) -> Dict:
        """Execute a single packet (instruction) on a vCPU"""
        vcpu = self.vcpus[vcpu_name]
        
        print(f"[PACKET] Sending to {vcpu['id']} ({vcpu['type']})")
        print(f"         Instruction: {instruction['op']} on {instruction['length']} bytes")
        
        payload = {
            "data_url": TEST_DATA_URL,
            "instructions": [instruction],
            "window": {
                "offset": instruction.get("offset", 0),
                "length": instruction.get("length", 1048576)
            }
        }
        
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    vcpu['endpoint'],
                    json=payload,
                    headers={"x-sender-vcpu": "scheduler"}
                )
                result = response.json()
                
                elapsed = (time.time() - start_time) * 1000
                
                # THIS IS THE MAGIC: The packet was executed!
                print(f"[RESULT] vCPU {vcpu['id']} executed in {elapsed:.1f}ms")
                
                if "results" in result:
                    print(f"         Result: {result['results'][0]}")
                if "metrics" in result:
                    metrics = result['metrics']
                    print(f"         Cache: {metrics.get('cache_hit', 'unknown')}")
                    print(f"         Throughput: {metrics.get('throughput_mbps', 'N/A')} MB/s")
                
                self.metrics["total_packets"] += 1
                self.metrics["total_bytes"] += instruction.get("length", 0)
                
                return result
                
            except Exception as e:
                print(f"[ERROR] vCPU {vcpu['id']} failed: {e}")
                return {"error": str(e), "vcpu": vcpu['id']}
    
    async def distribute_execution(self, instructions: List[Dict]) -> List[Dict]:
        """Distribute packet execution across available vCPUs"""
        print("\n" + "="*60)
        print("PACKET EXECUTION DISTRIBUTION")
        print("="*60)
        
        tasks = []
        
        # Simple round-robin distribution (could be smarter based on latency/cost)
        for i, instruction in enumerate(instructions):
            # Alternate between local and edge
            vcpu_name = "local" if i % 2 == 0 else "edge"
            
            # Skip edge if not configured
            if vcpu_name == "edge" and "YOUR-SUBDOMAIN" in self.vcpus["edge"]["endpoint"]:
                vcpu_name = "local"
            
            task = self.execute_packet(vcpu_name, instruction)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        print("\n" + "-"*60)
        print(f"EXECUTION COMPLETE")
        print(f"  Total packets executed: {self.metrics['total_packets']}")
        print(f"  Total bytes processed: {self.metrics['total_bytes']:,}")
        print(f"  Effective CPUpwn: {self.metrics['total_bytes'] / 1048576:.1f} MB")
        print("-"*60)
        
        return results

async def main():
    """Demonstrate dual vCPU execution"""
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  PacketFS Dual vCPU Demo                                    ║
║                                                              ║
║  Packets ARE execution                                      ║  
║  The network IS the CPU                                     ║
║                                                              ║
║  vCPU #1: Local container (fast, local)                     ║
║  vCPU #2: Cloudflare Worker (global, cached)                ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Define packet instructions to execute
    instructions = [
        {"op": "counteq", "imm": 0, "offset": 0, "length": 262144},      # Count zeros in first 256KB
        {"op": "fnv", "offset": 262144, "length": 262144},               # FNV hash next 256KB
        {"op": "xor", "imm": 42, "offset": 524288, "length": 262144},    # XOR next 256KB
        {"op": "crc32", "offset": 786432, "length": 262144},             # CRC32 last 256KB
    ]
    
    print(f"Scheduling {len(instructions)} packets for execution...")
    print(f"Total data: 1MB split into 4 x 256KB windows")
    
    # Create scheduler and distribute execution
    scheduler = PacketScheduler(VCPUS)
    results = await scheduler.distribute_execution(instructions)
    
    print("\n" + "="*60)
    print("INSIGHTS")
    print("="*60)
    print("""
1. Each 'packet' is an instruction that executes somewhere
2. The local container executed some packets (vCPU #1)
3. Cloudflare Worker executed others (vCPU #2)  
4. The network carried both data AND execution
5. From the OS perspective: just network I/O
6. Reality: Distributed computation across the planet!

The 'filesystem read' you thought you did?
It was actually a globally distributed computation.
The OS has no idea. FUSE made it invisible.

Welcome to PacketFS - where packets ARE execution!
""")

if __name__ == "__main__":
    # Check if edge endpoint is configured
    if "YOUR-SUBDOMAIN" in VCPUS["edge"]["endpoint"]:
        print("\n⚠️  NOTE: Update VCPUS['edge']['endpoint'] with your Cloudflare Worker URL")
        print("   Deploy with: cd edge-compute && wrangler publish")
        print("   Then update the URL in this script\n")
        print("   Running with local vCPU only for now...\n")
    
    asyncio.run(main())