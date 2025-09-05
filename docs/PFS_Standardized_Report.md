Title: PacketFS — Terminology, Metrics, and Labeled Benchmarks (Transfer vs pCPU)

Legend (authoritative labels and meanings)
- Conventional
  - Plain kernel-transport byte-stream transfer using standard tools (e.g., scp/sftp/rsync/curl). No PacketFS concepts. Payload bytes are transferred end-to-end, with tool-specific overhead (e.g., SSH crypto).
- PFS-With-Payload-<Transport> (Benchmark)
  - Our protocol framing/grams while still shipping payload bytes. This is a reference/baseline only (not PacketFS proper). Purpose: show why “send-all-bytes” is inferior to offset-only.
  - Examples: PFS-With-Payload-TCP, PFS-With-Payload-UDP.
- Native PFS Offset-only Mode - <Transport>
  - Real PacketFS. No payload. A shared hugepage-backed blob is assumed; we send offset/length schedules (grams), and the receiver executes immediately by touching offsets in the blob.
  - Examples: Native PFS Offset-only Mode - TCP, Native PFS Offset-only Mode - UDP.
- Native PFS Arithmetic Mode - <Transport>
  - Offset-only plus arithmetic deltas: one absolute offset, subsequent offsets expressed as +/- relative deltas. Further reduces descriptor bytes and loop overhead.
  - Examples: Native PFS Arithmetic Mode - TCP.
- pCPU Offset-mode
  - Packet-native compute model where “instructions” are offset/length schedules over the shared blob. Execution occurs in user space over kernel-managed hugepages (hugetlbfs or THP). No payload transfers.
- pCPU Arithmetic-mode
  - Same as pCPU Offset-mode, but descriptor streams are normalized/compacted via +/- arithmetic for better descriptor density and simpler compute loops.
- Streaming-mode (aka “yeet mode”)
  - Production high-rate path using Native PFS Offset-only Mode or Native PFS Arithmetic Mode (no payload) with batching, sharding, and transport-specific optimizations (TCP/UDP/io_uring/AF_XDP).

Measurement axes and units
- As Transfer Mode (human-impact metric): Effective (P|T|G|M|K)B/s
  - The average rate at which a file (or effective data) is transferred over the line. For Offset-only/Arithmetic modes, “effective” is the implied payload-equivalent amount reconstructed via offsets.
- As a Computational Model (pCPU): MB per CPU-second (MB/CPU-s)
  - How many effective MB are processed per CPU-second, including integrity checks used in the run. This is the “pCPU vs conventional CPU” comparability metric.
- pThreads (convention-in-progress)
  - Conceptual parallelization degree for pCPU. Today’s runs are single-threaded pCPU (pThreads=1). We will introduce a meaningful pThreads definition (e.g., optimum concurrent packets) as the streaming schedule stabilizes.

Methodology (apples-to-apples fairness)
- Conventional baseline uses scp over a veth pair pfs0<->pfs1 (pfs1 in a netns with sshd) with endpoints on tmpfs (/dev/shm) to avoid disk skew. No compression: -o Compression=no.
- PFS baselines run on loopback (127.0.0.1) for high-confidence local pCPU execution over a persistent hugepage-backed blob (/dev/hugepages/pfs_stream_blob). Integrity via FNV-1a checksum.
- Setup phases (map/prefault/fill) are reported but excluded from steady-state transfer metrics.

System snapshot (for these results)
- OS: Ubuntu Linux (loopback for PFS runs, veth+netns for Conventional)
- Blob (PFS): 2 GiB under /dev/hugepages (THP in effect when hugetlbfs mount not used)
- Default grams: 1 MiB per gram slab, 1024 descriptors/gram, max_len=256 KiB, align=64
- Integrity: FNV-1a 64-bit checksum on effective payload bytes

Labeled results (decimal MB)

Compact summary table

| Label | Purpose | Size (MB) | Elapsed (s) | Effective (MB/s) | user_s | sys_s | MB/CPU-s | Integrity | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| Conventional (scp,veth,no-compress) | Transfer | 2,147.48 | 3.69 | 582.0 | 2.13 | 1.26 | 633.3 | NA | /dev/shm endpoints; 10.77.0.1→10.77.0.2; SSH |
| PFS-With-Payload-TCP (Benchmark) | Transfer | 1,073.74 | 10.66 | 100.7 | 3.31 | 1.98 | 202.9 | OK | Loopback; 1 MiB grams; 1024 desc/gram |
| Native PFS Offset-only Mode - TCP | Transfer|pCPU | 549,588.92 | 517.6 | 1,062.3 | 509.40 | 1.85 | 1,075.0 | OK | Loopback; blob=/dev/hugepages; 1 MiB grams; 1024 desc/gram; pThreads=1 |
1) Conventional — scp (veth pfs0→pfs1, no compression, 2 GiB)
- Purpose: As Transfer Mode
- Size: 2,147.48 MB (2 GiB)
- Elapsed: 3.69 s → Effective throughput ≈ 582 MB/s
- CPU (client): user 2.13 s, sys 1.26 s → 3.39 CPU-s → ≈ 633 MB/CPU-s
- Notes: SSH encryption; fully kernel transport; /dev/shm endpoints; no PacketFS ideas.

2) PFS-With-Payload-TCP (Benchmark, loopback, 1 GiB)
- Purpose: As Transfer Mode (reference-only; NOT PacketFS proper)
- Size: 1,073.74 MB (1 GiB)
- Elapsed: 10.66 s → Effective throughput ≈ 100.7 MB/s
- CPU (receiver): 5.29 CPU-s → ≈ 203 MB/CPU-s
- Notes: Validates framing/integrity; demonstrates why “payload mode” is not the target model.

3) Native PFS Offset-only Mode - TCP (loopback, pCPU Offset-mode)
- Purpose: As Transfer Mode and as pCPU model (execution over shared blob)
- Effective bytes: 549,588.92 MB
- Elapsed: 517.6 s → Effective throughput ≈ 1,062 MB/s
- CPU (client): user 509.40 s, sys 1.85 s → 511.25 CPU-s → ≈ 1,075 MB/CPU-s
- Integrity: checksum OK
- Notes: No payload; the receiver executes direct over /dev/hugepages mapping (pThreads=1).

Human-impact view (time-to-move 1 GB)
- Conventional (scp, veth): 1,000 MB / 582 MB/s ≈ 1.72 s
- PFS-With-Payload-TCP: 1,000 MB / 100.7 MB/s ≈ 9.93 s
- Native PFS Offset-only Mode - TCP: 1,000 MB / 1,062 MB/s ≈ 0.94 s

Interpretation
- As Transfer Mode
  - Native PFS Offset-only Mode - TCP is ~1.8× faster than Conventional (scp) on this host and ~10× faster than PFS-With-Payload (benchmark-only).
  - This reflects the fundamental win: don’t ship payload; ship offsets and execute over a shared, hot mapping.
- As pCPU (compute model)
  - Native PFS Offset-only Mode exhibits ≈ 1,075 MB/CPU-s efficiency (including checksum), indicating strong headroom for fused/LLVM-optimized kernels and arithmetic descriptor compression.

Arithmetic mode (next)
- Native PFS Arithmetic Mode - TCP and pCPU Arithmetic-mode
  - Send one absolute offset per gram, express subsequent offsets as +/- deltas; vectorize loops for normalized strides; reduce descriptor bytes.
  - Expect improved MB/CPU-s, especially when combined with large grams and light-touch integrity (or sampled NAK/repair plane).

Corrections plane (repair without polluting the primary)
- Keep the primary stream in Native PFS Offset-only (or Arithmetic) mode; when integrity sampling detects a mismatch, RX emits a NAK on a secondary channel, and TX replies with a minimal payload gram for just the requested offsets.
- Transport options: UDP with small ACK/repair windows, or TCP. This maintains execution-first semantics while ensuring end-to-end correctness.

Scaling guidance (grounded budgets; decimal MB)
- At ~0.00093 CPU-s/MB (Native PFS Offset-only - TCP):
  - 1 GbE (125 MB/s): ~0.12 CPU
  - 10 GbE (1,250 MB/s): ~1.16 CPU
  - 40 GbE (5,000 MB/s): ~4.65 CPU
  - 100 GbE (12,500 MB/s): ~11.6 CPU
- These are local execution budgets; actual NIC-bound results will benefit from AF_XDP/io_uring/MSG_ZEROCOPY and per-queue sharding.

Standardized comparison framing to include with each experiment
- Label: One of {Conventional, PFS-With-Payload-<Transport>, Native PFS Offset-only Mode - <Transport>, Native PFS Arithmetic Mode - <Transport>, pCPU Offset-mode, pCPU Arithmetic-mode}
- Purpose: As Transfer Mode or As pCPU Model (or both)
- Size (MB), Elapsed (s), Effective throughput (MB/s)
- CPU: user_s, sys_s, total, and MB/CPU-s
- Integrity status
- pThreads: current (1) and chosen plan
- Notes: transport, buffer sizes, descriptor count, etc.

Next actions (concrete)
- Update brief/whitepaper to use these labels consistently.
- Emit CSV for current runs with the standardized fields above (Conventional scp; PFS-With-Payload-TCP; Native PFS Offset-only Mode - TCP) and include a compact table in the docs.
- Implement Native PFS Arithmetic Mode (relative offsets) plus a corrections plane (UDP NAK/repair) on loopback to demonstrate end-to-end correctness with offset-only primary.
- When ready, move Native PFS Offset-only/Arithmetic Modes to AF_XDP on a real NIC with queue sharding and measure per-core scaling.

Appendix: run snapshots
- Conventional (scp, veth pfs0→pfs1): 2.13s user, 1.26s sys, 3.69s wall; ≈ 582 MB/s; ≈ 633 MB/CPU-s
- PFS-With-Payload-TCP (loopback): 10.66s wall (1 GiB); ≈ 100.7 MB/s; ≈ 203 MB/CPU-s
- Native PFS Offset-only Mode - TCP (loopback): 517.6s wall (549,588.9 MB effective); ≈ 1,062 MB/s; ≈ 1,075 MB/CPU-s; checksum OK

