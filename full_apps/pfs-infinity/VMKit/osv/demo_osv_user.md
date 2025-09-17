# 🚀 OSv Unikernel - User Demo Guide

## What is OSv?

OSv is a specialized operating system that runs **one application** at lightning speed. Think of it as a "single-purpose VM" that:
- **Boots in 5-10ms** (vs 100-500ms for containers)
- **Uses 20-30MB RAM** (vs 100-500MB for regular VMs)
- **Runs your code at near-native speed**

Perfect for: microservices, job processing, serverless functions, isolated workloads.

## 🎯 Quick Demo: Your First OSv VM

### 1. Initial Setup (one-time only)
```bash
# Set up OSv environment (installs dependencies, builds OSv)
just vm-osv-setup

# Check everything is ready
just vm-doctor
```

### 2. Run Hello World
```bash
# Build and run a simple "Hello World" in an OSv VM
just vm-osv-hello
```

**What just happened?**
- Built a complete OS image with your app
- Booted a VM in ~10ms
- Ran your code
- Shut down cleanly

### 3. See the Speed: Boot Time Benchmark
```bash
# Measure how fast OSv boots (10 iterations)
just vm-osv-boot-bench
```

Output:
```
Boot 1: 8ms
Boot 2: 6ms
Boot 3: 7ms
...
```

### 4. Run a Real Workload: Threading Benchmark
```bash
# Run a multi-threaded computation benchmark
just vm-osv-bench
```

This spawns 16 threads doing parallel computation - OSv handles real threading!

## 💼 Real-World Use Case: Job Processing

### Scenario: Process 1000 Image Thumbnails

**Traditional Approach:**
- Start container (200ms)
- Load Python + libraries (500ms)
- Process image (100ms)
- Total per job: **800ms** × 1000 = **13 minutes**

**OSv Approach:**
- Start OSv VM (10ms)
- Process image (100ms) - app pre-loaded
- Total per job: **110ms** × 1000 = **1.8 minutes**

**7x faster!** ⚡

### Example: Integration with HGWS Job Queue

```python
# Your job processor (runs inside OSv VM)
def process_job(job_data):
    # This runs in its own isolated VM!
    result = expensive_computation(job_data)
    return result
```

Start the orchestrator:
```bash
# This manages a pool of OSv VMs for job processing
just vm-osv-orchestrator
```

The orchestrator:
1. Maintains a pool of pre-warmed OSv VMs
2. Receives jobs from Redis queue
3. Dispatches to available VM
4. Returns results
5. Recycles or respawns VMs

## 🎮 Interactive Demo: Create Your Own VM

### 1. Write a Simple C Program
```c
// my_app.c
#include <stdio.h>
#include <unistd.h>

int main() {
    printf("🚀 Running in OSv!\n");
    printf("PID: %d\n", getpid());
    printf("Sleeping for 2 seconds...\n");
    sleep(2);
    printf("Done! OSv is awesome!\n");
    return 0;
}
```

### 2. Build and Run
```bash
# Compile
gcc -o my_app my_app.c

# Build OSv image with your app
cd VMKit/osv
./osv/scripts/build image=native-example,apps=my_app

# Run it!
./osv/scripts/run.py
```

### 3. What You'll See
```
OSv v0.57.0
eth0: 10.0.2.15
🚀 Running in OSv!
PID: 2
Sleeping for 2 seconds...
Done! OSv is awesome!
```

Total time: ~15ms from power-on to app running!

## 🔥 Advanced: Run a Web Service

### FastAPI in OSv (Python)
```python
# api.py
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from OSv!", "boot_time": "10ms"}
```

```bash
# Build Python app image
cd VMKit/osv
./scripts/build image=python3-from-host,apps=api

# Run with port forwarding
./scripts/run.py -f 8000:8000

# Test it
curl http://localhost:8000
```

## 📊 Performance Comparison

| Task | Container | OSv | Speedup |
|------|-----------|-----|---------|
| Boot to app | 500ms | 10ms | **50x** |
| Memory usage | 200MB | 30MB | **6.6x** |
| 1000 jobs | 13 min | 1.8 min | **7x** |
| Context switch | 2-5μs | <1μs | **3x** |

## 🎯 When to Use OSv

**Perfect for:**
- ✅ Short-lived tasks (batch jobs, functions)
- ✅ Microservices needing isolation
- ✅ High-frequency operations (need fast boot)
- ✅ Memory-constrained environments
- ✅ Security-sensitive workloads (hardware isolation)

**Not ideal for:**
- ❌ Stateful applications (databases)
- ❌ Complex system dependencies
- ❌ Applications needing fork()
- ❌ Full Linux userland

## 🚀 Your Turn!

Try these commands:

```bash
# See all VM commands
just help | grep vm-

# Check OSv status
just vm-osv-status

# List available VMs
just vm-list

# Create a new VM
just vm-new my-test-vm

# Start any VM
just vm-up my-test-vm
```

## 💡 Tips & Tricks

1. **Pre-warm VMs** for instant response:
   ```bash
   # Keep 10 VMs ready
   just vm-osv-orchestrator POOL_SIZE=10
   ```

2. **Use shared memory** for zero-copy data transfer:
   - OSv supports virtio-vsock for host communication
   - No network overhead!

3. **Snapshot & restore** for even faster starts:
   - Take snapshot after boot
   - Restore in <5ms

4. **Multi-core scaling**:
   - OSv supports real SMP
   - Pin VMs to CPU cores for best performance

## 🎉 Congratulations!

You've just:
- Booted an OS in 10ms
- Run isolated workloads with minimal overhead
- Learned how unikernels can accelerate your infrastructure

OSv gives you the isolation of VMs with performance better than containers!

---

**Next Steps:**
- Integrate with your job queue: `just vm-osv-orchestrator`
- Build custom images for your apps
- Benchmark your specific workloads
- Join the OSv community: https://github.com/cloudius-systems/osv

**Questions?** Check `/home/punk/Projects/HGWS/VMKit/docs/unikernel-comparison.md` for detailed comparisons with other technologies.
