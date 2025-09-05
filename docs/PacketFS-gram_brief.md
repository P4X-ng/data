Title: PacketFS‑gram: From 1.25× a “real CPU” to a batched, blob‑indexed transport with LLVM‑ready execution

Audience
Performance engineering stakeholders evaluating transport and execution models; this document is intentionally high‑level to avoid IP leakage while preserving enough specificity to judge impact and trajectory.

1) Where we started: ~1.25× a “real CPU” and the limits of per‑message work
- Early stage: We pursued raw throughput with user‑space ring buffers and simple async TX/RX prototypes. These paths validated that careful batching and large socket buffers could push beyond a single “baseline” CPU’s naive copy loop by roughly 1.25× on our internal microbenchmarks, but they also exposed the headwinds:
  - Per‑packet syscall overhead and kernel crossings dominated with small messages.
  - Copy amplification: data touched multiple times before reaching the application/useful compute.
  - Loss of logical boundaries when streaming as undifferentiated bytes, forcing re‑framing in the hot path.
- Key lesson: Sustained wins require (a) fewer crossings, (b) fewer copies, and (c) preserving the application’s small logical units without paying per‑unit overhead.

2) The architectural shift: PacketFS‑gram
PacketFS‑gram keeps the application’s small logical packet semantics while batching them into “superframes” (grams) for transport. Each gram carries a compact header, a descriptor table, and, when desired, a payload slab. Descriptors point into a large, shared, hugepage‑backed blob by offset/length; the application reconstructs or verifies data by touching those offsets.

What this means for transport protocol
- Reframe “packetization” at the app boundary: Hundreds to thousands of logical operations ride in a single gram. The transport moves fewer, larger writes, slashing per‑message overhead without sacrificing logical granularity upstream.
- Blob‑indexed addressing: Offsets into a pre‑mapped hugepage blob replace copying opaque byte slices. Offset‑only grams can avoid payload entirely; payload mode is available for A/B and integrity.
- Kernel‑friendly memory: The blob lives in kernel‑managed pages (hugetlbfs preferred; THP fallback), leading to better TLB behavior and predictable NUMA interactions.
- Framing discipline: A minimal outer frame (for HELLO/control/data) wraps an inner gram header + descriptor table (+ optional payload slab). IO is vectorized (writev) so header/desc/payload are emitted together.
- UDP and zero‑copy pathfinding: The same gram concept extends to UDP (sendmmsg batching + light ACK/repair windows). Zero‑copy variants (MSG_ZEROCOPY, io_uring with registered buffers) are straightforward follow‑ons.

3) The execution model this unlocks (LLVM, sharding, ring buffers, kernel‑managed memory)
- Kernel‑managed memory execution: Work operates over a long‑lived mapping whose pages are owned/managed by the kernel (hugetlbfs or THP). We execute user‑space compute directly over those pages via offset/length descriptors, eliminating transient allocation/copy churn.
- LLVM‑ready compute path: The repository includes a pipeline for LLVM IR parsing and native codegen (llvm_parser, bench_exec, libpfs_exec). The practical implication: the same descriptor sequences that drive data motion can drive code generation (e.g., vectorized micro‑ops, fused scans), keeping compute “near” the blob without shuttling data.
- Sharded rings: At runtime, grams or their descriptor sets can be sharded across cores (e.g., consistent hashing or round‑robin) with per‑shard rings and affinity pinning, minimizing cross‑core cache traffic and enabling steady‑state pipelines.
- Separation of concerns: Transport concerns (framing, pacing, integrity) are cleanly decoupled from compute concerns (LLVM pipelines, ALU kernels). Both meet at the descriptor abstraction over the blob.
- Important clarification: We are not executing code in kernel mode; we execute in user space over kernel‑managed pages. This yields the benefits of “in‑kernel memory residency” for the data without the risk profile of kernel execution.

4) Measured effectiveness (latest loopback run, payload mode)
Environment: Ubuntu Linux, loopback TCP, THP in effect; no CPU pinning. Parameters: 1 GiB blob; 1024 descriptors/gram; gram payload slab 1 MiB; max_len 256 KiB; align 64; integrity via FNV‑1a.
- Receiver (authoritative):
  - Bytes: 1,073,741,824 (1 GiB)
  - Wall time: 10.66 s
  - CPU time: user 3.31 s, sys 1.98 s → 5.29 CPU‑s
  - Average throughput: ≈ 100.7 MB/s (decimal) ≈ 96.1 MiB/s (binary)
  - Instantaneous (mid‑run) samples: up to ≈ 112 MB/s
  - CPU efficiency: ≈ 203 MB per CPU‑second (decimal) ≈ 194 MiB/CPU‑s
  - Max RSS: ≈ 1.05 GiB (the mapped blob)
  - Context switches: ~5,205 voluntary, 40 involuntary
- Sender (context only): Prefault ≈ 3.1 s; fill ≈ 2.1 s (excluded from steady‑state throughput).
- Integrity: checksum OK (end‑to‑end data validation over payload slab).

Trajectory: from ~1.25× CPU to blob‑indexed grams
- The initial ~1.25× CPU gain (vs. a naive single‑thread copy/compute loop) came from coarse batching and big socket buffers.
- PacketFS‑gram advanced this by (a) collapsing many logical operations into single transport writes, (b) cutting copies via offset‑based reconstruction, and (c) structuring the data path for compute adjacency (LLVM‑ready descriptors over a hot blob).
- Result: Lowered host overhead to ≈ 5.29 CPU‑s per GiB on RX with integrity checks, while delivering ≈ 100 MB/s class end‑to‑end on loopback without zero‑copy offloads.

5) Practical implications for transport engineers
- Think “gram‑sized” not “packet‑sized”: Tune descriptors/gram and gram bytes (e.g., 1 MiB) to saturate ring and socket efficiencies while preserving upstream logical boundaries.
- Prefer blob‑indexed offsets over ad‑hoc copies: It concretely reduces copy pressure and aligns reconstruct/verify with compute kernels.
- Pace for consistency: With grams, pacing decisions move from “per packet” to “per batch,” making feedback‑based pacing and repair windows (for UDP) simpler and more stable.
- Observe the right numbers: Receiver‑side bytes/time and CPU‑seconds are the authoritative measures. Exclude setup phases (mmap/prefault/fill) from steady‑state throughput accounting.

6) Practical implications for compute (the “new way we execute code”)
- Descriptors as a compute DSL: Offset/length sequences form a compact, deterministic schedule for kernels. They can be compiled (LLVM) into coalesced loops that match the memory layout the transport already optimized.
- Sharding first, vectorize second: Partition grams across cores to minimize cross‑core interference; within shards use SIMD‑friendly kernels. Rings remain an internal scheduling tool, not a wire‑level contract.
- Kernel‑managed residency: Keep the working set hot in hugetlbfs/THP pages; explicitly prefault/fill once, then iterate with minimal page‑fault noise.

7) Extrapolated effectiveness (grounded in measured baselines)
Use the measured IO baseline to scope compute vs transport.
- Measured IO (RX, 1 GiB):
  - Wall time T_io ≈ 10.66 s
  - CPU‑seconds C_io ≈ 5.29 s → ≈ 203 MB/CPU‑s (decimal)
- Additional compute per 1 GiB on one core:
  - T_comp ≈ (Bytes × K) / P, with Bytes = 1,073,741,824
  - Single‑core end‑to‑end ≈ max(T_io, T_comp)
  - With perfect scaling across N cores, use N×P in the denominator for T_comp.
- Interpreting regimes:
  - Transport‑bound: T_comp ≪ T_io ⇒ total time near ~10–11 s per GiB (current config), CPU headroom remains.
  - Compute‑bound: T_comp ≫ T_io ⇒ total time driven by compute; PacketFS‑gram’s ≈ 5.29 CPU‑s/GiB overhead leaves most CPU for kernels.
- What moves the needle next:
  - Raise T_io (throughput) via MSG_ZEROCOPY/io_uring, UDP sendmmsg + GSO, and NUMA pinning.
  - Reduce C_io (CPU‑s/GiB) via deeper batching, fewer syscalls, and header/payload checksum fusion.

8) Where this can go (safely stated)
- Zero‑copy networking: Register buffers and/or enable kernel‑assisted zerocopy to cut TX/RX CPU further.
- UDP grams: Add ACK windows and bounded repair to retain integrity without head‑of‑line blocking; leverage GSO for slab‑friendly payloads.
- LLVM fusion: Co‑generate transport‑adjacent kernels that consume descriptor schedules directly, minimizing loop overhead and branches.
- NUMA discipline: Affinity pin grams to memory locality domains; pre‑place shards to avoid cross‑socket TLB churn.

Appendix A: Current measurement snapshot (payload mode, loopback)
- Receiver: 1,073,741,824 bytes in 10.66 s; user 3.31 s, sys 1.98 s; ≈ 100.7 MB/s average (decimal); ≈ 203 MB/CPU‑s; checksum OK.
- Sender: prefault ≈ 3.1 s; fill ≈ 2.1 s (setup only).

Appendix B: Operational knobs (sharing‑safe)
- CLI flags: --huge-dir, --blob-name, --no-prefault, --no-fill, --blob-keep, --verbose, --log-interval
- Tunables: descriptors/gram (e.g., 1024), gram_bytes (e.g., 1 MiB), max_len (e.g., 256 KiB), align (e.g., 64)
- Methodology: report receiver‑side bytes/time/CPU, separate setup vs steady‑state.

Notes on disclosure
This document intentionally omits wire‑format minutiae, exact state machines, and low‑level kernel details. It conveys the pattern, controls, and observed behavior sufficient for evaluation without enabling trivial re‑implementation.

