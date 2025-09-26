# PacketFS pCPU Throughput Strategy — CPUpwn v2 (N-core)

This document records the configuration and results for the highest CPUpwn observed to date using the pCPU path, and defines CPUpwn in a way that is apples-to-apples with multi-core CPU baselines.

Definition (CPUpwn v2)
- CPUpwn = pCPU_throughput_MBps / CPU_baseline_MBps
- CPU_baseline_MBps is measured with a CPU implementation using the same operation and the same hot working set, with the number of CPU threads equal to pcores in the pCPU run (e.g., 64 pcores → 64 CPU threads).

Setup used for top results
- Machine: 64 logical CPUs (x86_64 Ubuntu)
- Blob: 4 GiB (anonymous + THP if hugetlbfs not available)
- Hot working set: 1 GiB (range_len=1 GiB)
- Per-core ring: power-of-two slots with 32 MiB slab (ring_pow2=19, slab_mb=32)
- Descriptors per frame (dpf): 64
- Alignment: 64 bytes
- Producer/consumers: process-per-core; producer publishes to per-core rings; each consumer pinned to a CPU
- Kernel helper: pfs_fastpath (/dev/pfs_fastpath) modernized for reliable vmalloc remap; staging TX/RX also validated

Exact commands (examples)
- Build CPU baselines:
  - Single-thread: dev/wip/native/cpu_baseline --size-mb 1024 --dumb
  - Multi-thread (auto threads): dev/wip/native/cpu_baseline --size-mb 1024
- Run pcores (1 GiB hot range):
  ```
  dev/wip/native/pfs_proc_pcores \
    --pcores $(getconf _NPROCESSORS_ONLN) --duration 10 --blob-mb 4096 \
    --dpf 64 --align 64 --ring-pow2 19 --slab-mb 32 \
    --op xor --imm 255 --range-off 0 --range-len $((1024*1024*1024))
  ```
- Full op sweep (same config): xor, add, counteq, fnv, crc32c

Results summary (64 pcores, 1 GiB hot range, 10 s)
- xor:    ~15.5–15.8 GB/s, CPUpwn(=64CPU) ≈ 6.0–6.2×
- add:    ~15.4–15.7 GB/s, CPUpwn(=64CPU) ≈ 6.1–6.4×
- counteq:~50.2 GB/s,      CPUpwn(=64CPU) ≈ 7.15×
- fnv:    ~28.7–29.0 GB/s, CPUpwn(=64CPU) ≈ 24.0×
- crc32c: ~8.36 GB/s,      CPUpwn(=64CPU) ≈ 52.8×

Notes on interpretation
- CPUpwn now compares against a CPU baseline with the same number of threads as pcores (apples-to-apples). For simple bytewise ops (xor/add/counteq) we are memory-bound; pCPU still delivers ~6–7× over the threaded CPU baseline by coalescing work and minimizing per-span overhead.
- For compute-heavy ops (crc32c/fnv), the CPU baseline in this repo is not hardware-accelerated yet. Once SSE4.2/CLMUL CRC32C is wired in, CPUpwn will drop (as intended for a stronger baseline), but absolute pCPU throughput remains high.

Implementation notes
- pfs_fastpath kernel module updated for modern kernels (vm_flags_set, remap_vmalloc_range fallback via vm_insert_page). Sanity with staging program-carrying TX/RX validated.
- pcores runner uses interprocess-visible channel (/dev/shm) to ensure producer/consumers share ring state correctly.
- CPUpwn metric in the runner now logs as CPUpwn(=NCPU) with baseline(NCPU)=… MB/s.

How to push throughput further
- Increase ring capacity and per-ring slab (e.g., ring_pow2=20, slab_mb=64). Memory footprint grows: per ring ≈ 4 MiB slots + slab.
- Reduce hot range (e.g., 512 MiB) to raise cache effectiveness.
- NUMA-aware pinning: bind producer+consumers per node; interleave or pin blob accordingly.
- Optimize CPU baselines:
  - Add SSE4.2 accelerated CRC32C (and PCLMUL), hand-tuned SIMD for XOR/ADD paths.
- Optional: warm-up phase (1–2 s) before measurement window to stabilize MB/s.

Reproducibility
- Logs/CSVs are written under logs/ (one per run). For a sweep, use separate CSVs per op as done during the session (e.g., logs/pcores_xor_mt.csv).