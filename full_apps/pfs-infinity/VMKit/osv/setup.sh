#!/bin/bash
set -e

# OSv Setup Script for HGWS VMKit Integration
# Installs OSv, Capstan, and creates optimized VM images

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
OSV_DIR="${SCRIPT_DIR}/osv"
CAPSTAN_VERSION="v0.3.0"

echo "🚀 Setting up OSv unikernel environment..."

# Check KVM support
if [ ! -e /dev/kvm ]; then
    echo "❌ KVM not available. OSv requires hardware virtualization."
    echo "   Enable VT-x/AMD-V in BIOS and ensure kvm modules are loaded."
    exit 1
fi

# Check if user is in kvm group
if ! groups | grep -q kvm; then
    echo "⚠️  User not in kvm group. You may need to run: sudo usermod -aG kvm $USER"
    echo "   Then logout and login again."
fi

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt-get update
sudo apt-get install -y \
    qemu-kvm \
    qemu-utils \
    libvirt-daemon-system \
    libvirt-clients \
    bridge-utils \
    build-essential \
    cmake \
    libyaml-cpp-dev \
    libboost-all-dev \
    genromfs \
    autoconf \
    libtool \
    openjdk-11-jdk \
    ant \
    maven \
    npm \
    genisoimage \
    python3-pip \
    python3-dev \
    python3-pytest \
    python3-requests \
    python3-yaml \
    python3-boto3 \
    wget \
    git

# Install Capstan (OSv package manager)
echo "📦 Installing Capstan..."
if ! command -v capstan &> /dev/null; then
    wget -q "https://github.com/cloudius-systems/capstan/releases/download/${CAPSTAN_VERSION}/capstan-${CAPSTAN_VERSION}-linux-amd64.tar.gz"
    tar xzf "capstan-${CAPSTAN_VERSION}-linux-amd64.tar.gz"
    sudo mv capstan /usr/local/bin/
    rm "capstan-${CAPSTAN_VERSION}-linux-amd64.tar.gz"
    echo "✅ Capstan installed"
else
    echo "✅ Capstan already installed"
fi

# Clone OSv if not exists
if [ ! -d "${OSV_DIR}" ]; then
    echo "📦 Cloning OSv repository..."
    git clone https://github.com/cloudius-systems/osv.git "${OSV_DIR}"
    cd "${OSV_DIR}"
    git submodule update --init --recursive
else
    echo "✅ OSv repository exists, updating..."
    cd "${OSV_DIR}"
    git pull
    git submodule update --init --recursive
fi

# Build OSv
echo "🔨 Building OSv (this may take a while)..."
cd "${OSV_DIR}"
./scripts/setup.py

# Build a minimal image
echo "🔨 Building minimal OSv image..."
./scripts/build -j$(nproc) image=native-example

# Create optimized configurations
echo "📝 Creating optimized configurations..."
cd "${SCRIPT_DIR}"

# Create Makefile for easy OSv operations
cat > Makefile << 'EOF'
# OSv Makefile for HGWS VMKit

OSV_DIR := ./osv
APPS_DIR := ./apps
BUILD_DIR := ./build

.PHONY: all clean build-base run-hello benchmark

all: build-base

# Build base OSv image
build-base:
	@echo "Building base OSv image..."
	cd $(OSV_DIR) && ./scripts/build -j$$(nproc) image=native-example

# Build hello world example
build-hello: build-base
	@echo "Building hello world app..."
	mkdir -p $(APPS_DIR)/hello
	echo '#include <stdio.h>\nint main() { printf("Hello from OSv!\\n"); return 0; }' > $(APPS_DIR)/hello/hello.c
	gcc -o $(APPS_DIR)/hello/hello $(APPS_DIR)/hello/hello.c
	cd $(OSV_DIR) && ./scripts/build -j$$(nproc) image=native-example,apps=$(APPS_DIR)/hello

# Run hello world with KVM
run-hello:
	@echo "Running OSv hello world..."
	cd $(OSV_DIR) && ./scripts/run.py -nv

# Build threading benchmark
build-thread-bench:
	@echo "Building threading benchmark..."
	mkdir -p $(APPS_DIR)/thread-bench
	cp thread_benchmark.c $(APPS_DIR)/thread-bench/
	gcc -pthread -O3 -o $(APPS_DIR)/thread-bench/thread_benchmark $(APPS_DIR)/thread-bench/thread_benchmark.c
	cd $(OSV_DIR) && ./scripts/build -j$$(nproc) image=native-example,apps=$(APPS_DIR)/thread-bench

# Run threading benchmark
run-thread-bench:
	@echo "Running threading benchmark..."
	cd $(OSV_DIR) && ./scripts/run.py -nv -m 512M -c 4

# Benchmark boot time
benchmark-boot:
	@echo "Benchmarking OSv boot time..."
	@for i in {1..10}; do \
		start=$$(date +%s%N); \
		timeout 2 $(OSV_DIR)/scripts/run.py -nv -e "true" > /dev/null 2>&1; \
		end=$$(date +%s%N); \
		echo "Boot $$i: $$(( (end - start) / 1000000 ))ms"; \
	done

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR)
	cd $(OSV_DIR) && make clean

# Show VM status
status:
	@echo "OSv Status:"
	@echo "KVM Available: $$([ -e /dev/kvm ] && echo '✅' || echo '❌')"
	@echo "Capstan Version: $$(capstan --version 2>/dev/null || echo 'Not installed')"
	@echo "OSv Built: $$([ -f $(OSV_DIR)/build/release.x64/loader.img ] && echo '✅' || echo '❌')"

help:
	@echo "OSv VMKit Makefile Commands:"
	@echo "  make build-base      - Build base OSv image"
	@echo "  make build-hello     - Build hello world example"
	@echo "  make run-hello       - Run hello world VM"
	@echo "  make build-thread-bench - Build threading benchmark"
	@echo "  make run-thread-bench   - Run threading benchmark"
	@echo "  make benchmark-boot  - Benchmark boot times"
	@echo "  make status         - Show OSv status"
	@echo "  make clean          - Clean build artifacts"
EOF

# Create threading benchmark
cat > thread_benchmark.c << 'EOF'
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#define NUM_THREADS 16
#define ITERATIONS 1000000

typedef struct {
    int id;
    long result;
} thread_data_t;

void* worker(void* arg) {
    thread_data_t* data = (thread_data_t*)arg;
    long sum = 0;
    
    for (int i = 0; i < ITERATIONS; i++) {
        sum += i * data->id;
    }
    
    data->result = sum;
    return NULL;
}

int main() {
    pthread_t threads[NUM_THREADS];
    thread_data_t thread_data[NUM_THREADS];
    struct timespec start, end;
    
    printf("OSv Threading Benchmark\n");
    printf("Threads: %d, Iterations: %d\n", NUM_THREADS, ITERATIONS);
    
    clock_gettime(CLOCK_MONOTONIC, &start);
    
    // Create threads
    for (int i = 0; i < NUM_THREADS; i++) {
        thread_data[i].id = i;
        pthread_create(&threads[i], NULL, worker, &thread_data[i]);
    }
    
    // Join threads
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    
    clock_gettime(CLOCK_MONOTONIC, &end);
    
    double elapsed = (end.tv_sec - start.tv_sec) + 
                    (end.tv_nsec - start.tv_nsec) / 1000000000.0;
    
    printf("Time: %.3f seconds\n", elapsed);
    printf("Throughput: %.0f ops/sec\n", (NUM_THREADS * ITERATIONS) / elapsed);
    
    return 0;
}
EOF

# Create Python VM orchestrator
cat > vm_orchestrator.py << 'EOF'
#!/usr/bin/env /home/punk/.venv/bin/python3
"""
OSv VM Orchestrator for HGWS
Manages a pool of OSv VMs for job processing
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any
import aioredis
from dataclasses import dataclass
from enum import Enum

class VMState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"

@dataclass
class OSvVM:
    id: str
    state: VMState
    port: int
    pid: int = None
    start_time: float = None
    jobs_processed: int = 0

class OSvOrchestrator:
    def __init__(self, pool_size: int = 10):
        self.pool_size = pool_size
        self.vms: Dict[str, OSvVM] = {}
        self.redis = None
        self.base_port = 9000
        
    async def initialize(self):
        """Initialize Redis connection and VM pool"""
        self.redis = await aioredis.create_redis_pool('redis://localhost')
        await self.spawn_pool()
        
    async def spawn_pool(self):
        """Spawn initial pool of VMs"""
        for i in range(self.pool_size):
            vm_id = f"osv-{i:03d}"
            port = self.base_port + i
            vm = OSvVM(id=vm_id, state=VMState.IDLE, port=port)
            self.vms[vm_id] = vm
            await self.start_vm(vm)
    
    async def start_vm(self, vm: OSvVM):
        """Start an OSv VM instance"""
        vm.state = VMState.STARTING
        
        cmd = [
            "./osv/scripts/run.py",
            "-nv",
            "-m", "128M",
            "-c", "2",
            "-p", f"qemu-monitor:tcp:127.0.0.1:{vm.port},server,nowait",
            "-e", "/hello"
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        vm.pid = process.pid
        vm.state = VMState.RUNNING
        vm.start_time = time.time()
        
        print(f"Started VM {vm.id} (PID: {vm.pid})")
        
    async def stop_vm(self, vm: OSvVM):
        """Stop an OSv VM instance"""
        vm.state = VMState.STOPPING
        
        if vm.pid:
            try:
                subprocess.run(["kill", str(vm.pid)], check=True)
            except:
                pass
        
        vm.state = VMState.STOPPED
        vm.pid = None
        
    async def get_idle_vm(self) -> OSvVM:
        """Get an idle VM from the pool"""
        for vm in self.vms.values():
            if vm.state == VMState.IDLE:
                return vm
        return None
        
    async def process_job(self, job_id: str, job_data: Dict[str, Any]):
        """Process a job using an available VM"""
        vm = await self.get_idle_vm()
        
        if not vm:
            print(f"No idle VMs available for job {job_id}")
            return None
            
        vm.state = VMState.RUNNING
        
        # TODO: Send job to VM via vsock or network
        # For now, simulate processing
        await asyncio.sleep(0.1)
        
        vm.jobs_processed += 1
        vm.state = VMState.IDLE
        
        return {"job_id": job_id, "vm_id": vm.id, "result": "completed"}
        
    async def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        idle = sum(1 for vm in self.vms.values() if vm.state == VMState.IDLE)
        running = sum(1 for vm in self.vms.values() if vm.state == VMState.RUNNING)
        total_jobs = sum(vm.jobs_processed for vm in self.vms.values())
        
        return {
            "pool_size": self.pool_size,
            "idle_vms": idle,
            "running_vms": running,
            "total_jobs_processed": total_jobs,
            "vms": [
                {
                    "id": vm.id,
                    "state": vm.state.value,
                    "jobs_processed": vm.jobs_processed,
                    "uptime": time.time() - vm.start_time if vm.start_time else 0
                }
                for vm in self.vms.values()
            ]
        }

async def main():
    orchestrator = OSvOrchestrator(pool_size=5)
    await orchestrator.initialize()
    
    print("OSv VM Orchestrator Started")
    print(f"Managing {orchestrator.pool_size} VMs")
    
    # Simulate job processing
    for i in range(10):
        result = await orchestrator.process_job(f"job-{i}", {"task": "compute"})
        print(f"Processed: {result}")
        
    stats = await orchestrator.get_stats()
    print(f"\nStats: {json.dumps(stats, indent=2)}")

if __name__ == "__main__":
    asyncio.run(main())
EOF

chmod +x vm_orchestrator.py

echo "✅ OSv setup complete!"
echo ""
echo "📚 Next steps:"
echo "  1. Logout and login to apply kvm group membership"
echo "  2. cd ${SCRIPT_DIR}"
echo "  3. make build-hello  # Build hello world"
echo "  4. make run-hello    # Run hello world VM"
echo "  5. make benchmark-boot # Test boot times"
echo ""
echo "🚀 For integration with HGWS:"
echo "  - Use vm_orchestrator.py to manage VM pools"
echo "  - Connect to Redis job queue for work distribution"
echo "  - See README.md for architecture details"
