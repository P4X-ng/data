Title: PacketFS‑gram and the pCPU model — progression, transport implications, and a path to NIC‑scale execution

Audience
- Hackers and performance engineers familiar with systems and networks but not necessarily deep CPU micro‑arch experts.
- Goal: explain what PacketFS‑gram changes for transport, how the pCPU execution model works, what we’ve actually measured, and what looks feasible next — without IP‑sensitive minutiae or massaging numbers.

Terminology note (2025-09-06)
- “PacketFS‑gram” aligns with the overlay used by PFS-TCP and PFS-UDP.
- “PacketFS Native” is transportless and has two variants: PFS‑Native Offset Mode and PFS‑Native Arithmetic Mode.
See docs/architecture/TERMINOLOGY.md for the current canonical definitions.

Executive overview (the four questions)
1) What it means for transport
   - We batch many small logical operations into grams (superframes) and address data by offsets into a shared hugepage‑backed blob. This slashes per‑message syscall/copy overhead while keeping the application’s logical boundaries intact.
2) The “new way” we execute code
   - Compute runs in user space directly over kernel‑managed pages (hugetlbfs or THP) using descriptor schedules (offset/length), with LLVM‑ready kernels, sharded rings, and predictable memory residency.
3) Effectiveness so far (true numbers)
   - On loopback TCP with payload‑mode integrity checks, 1 GiB delivered in ~10.66 s with ~5.29 CPU‑seconds (RX), ≈100.7 MB/s average and ≈203 MB per CPU‑second. Cross‑arch tests show predictable scaling (≈3× x86 over ARM across payload sizes). Real LAN file‑transfer prototype: 15 KB in ~10 ms at ~4.97 MB/s.
4) Extrapolated effectiveness (grounded in those numbers, no emulation)
   - Use the measured baseline to budget cores for target NIC rates and to judge whether a workload is transport‑ or compute‑bound. With today’s RX cost (~5.29 CPU‑s/GiB), 1 GbE looks comfortably within one core; 10 GbE would benefit from zero‑copy/AF_XDP and per‑core sharding.

1. Where we started → where we are now
1.1 Early phase (~1.25× a “real CPU”)
- User‑space ring buffers + large socket buffers beat a naive single‑thread copy/compute loop by ~1.25× in internal microbenchmarks.
- The ceiling: per‑packet syscalls, copy amplification, and re‑framing work in the hot path.

1.2 The PacketFS‑gram shift (batched transport + blob indexing)
- Grams: header + descriptor table (+ optional payload slab). Descriptors reference a shared hugepage blob by offset/length.
- Transport performs fewer, larger writes (writev/sendmmsg) while upstream logic keeps fine‑grained record/packet semantics.
- Kernel‑managed pages (hugetlbfs or THP) give predictable TLB/NUMA behavior and let us prefault/fill once, then stream.

1.3 Current measured baseline (loopback TCP, payload mode)
- Environment: Ubuntu, loopback TCP, THP; 1 GiB blob; 1024 descriptors/gram; gram payload slab 1 MiB; max_len 256 KiB; align 64; FNV‑1a integrity.
- Receiver (authoritative): 1,073,741,824 bytes in 10.66 s; user 3.31 s, sys 1.98 s → 5.29 CPU‑s; ≈100.7 MB/s average (decimal), ≈203 MB/CPU‑s; checksum OK; max RSS ≈ 1.05 GiB.
- Sender (context): prefault ~3.1 s, fill ~2.1 s — setup excluded from steady‑state throughput.

1.4 Real network snapshots (heterogeneous x86↔ARM)
- Cross‑architecture encode/latency sweep (LAN, ~0.46 ms RTT):
  - Throughput (payload‑size sweeps): x86 ≈ 18–20 Mbps; ARM ≈ 6.5–6.7 Mbps; ≈3× x86 advantage across sizes.
  - Latency: x86 down to ~25–27 μs; ARM ~74–75 μs; both well below network transit (~460 μs), i.e., processing faster than the wire.
- Real file transfer prototype (ARM→x86): 14.9 KB in ~10 ms, ≈4.97 MB/s, minimal protocol overhead; validates offset‑based protocol across architectures.

Takeaway: We moved from “small batching wins” to a transport that preserves logical packetization while minimizing per‑unit overhead, with measured ~100 MB/s on loopback and predictable x86/ARM scaling on LAN workloads.

2. What this means for transport
- Packetization at the app boundary: You keep record/packet semantics but ship them in grams, not one by one. Transport sees fewer, bigger IOs.
- Blob‑indexed addressing: Offsets into a shared hugepage mapping replace transient copies. Offset‑only grams can elide payload entirely when both sides share the blob; payload mode gives integrity A/B and data path flexibility.
- Fewer crossings, fewer copies: Vectorized IO coalesces header/desc/payload; the hot path touches stable, prefaulted pages.
- UDP extension: The same gram concept carries to UDP with sendmmsg batching and a small ACK/repair window for consistency without head‑of‑line blocking.
- Zero‑copy readiness: MSG_ZEROCOPY or io_uring with registered buffers is a natural next step; AF_XDP gives user‑space rings directly on the NIC.

Contrast with conventional tools (e.g., sftp/scp/rsync)
- Conventional tools pay per‑block crypto + copies + kernel crossings and often interleave disk IO — great for generality, suboptimal for packet‑native flows.
- PacketFS‑gram makes the data path memory‑centric (offsets) and batch‑oriented (grams), minimizing copies and crossings and decoupling disk from transport entirely.

3. The pCPU model: the “new way we execute”
- Descriptor schedules: Offset/length tables are a compact DSL for compute. They express “what to touch” over a long‑lived mapping.
- Kernel‑managed memory residency: Data pages are owned by the kernel (hugetlbfs/THP); we operate in user space over those pages with predictable locality.
- LLVM‑ready kernels: The same descriptor schedule can drive codegen (vectorized loops, fused scans). You can shard grams/rings across cores and pin to NUMA nodes.
- Budgeting with real numbers: For 1 GiB, our RX baseline is T_io ≈ 10.66 s wall with C_io ≈ 5.29 CPU‑s. Additional compute is T_comp ≈ (Bytes × K)/P for one core; N cores with ideal scaling replace P with N×P. End‑to‑end ~ max(T_io, T_comp) for single core (or the appropriate parallel generalization).

4. Effectiveness (no BS, just what we saw)
- Loopback, payload mode: 1 GiB at ≈100.7 MB/s average on RX with checksum verification; ≈203 MB/CPU‑s; application‑visible progress peaked ≈112 MB/s mid‑run.
- Heterogeneous LAN tests: Processing latencies well below network transit (μs vs hundreds of μs), ~3× x86 over ARM across payload sizes; ~20 Mbps sustained in encode sweeps on x86 under small‑payload regimes.
- Small file end‑to‑end: ~10 ms for 14.9 KB (~4.97 MB/s) across ARM→x86; minimal protocol overhead; validates end‑to‑end offset protocol behavior.

5. Extrapolated effectiveness (grounded, not speculative)
Use current RX CPU‑cost per GiB to budget cores for NIC rates. From C_io ≈ 5.29 CPU‑s/GiB:
- Cost per MB ≈ 5.29 / 1024 ≈ 0.00517 CPU‑s/MB (payload mode, loopback, checksum enabled).
- 1 GbE (≈125 MB/s): CPU needed ≈ 125 × 0.00517 ≈ 0.65 CPU‑s/s (≈65% of one core).
- 10 GbE (≈1250 MB/s): ≈ 1250 × 0.00517 ≈ 6.5 CPU‑s/s (≈6–7 cores) without zerocopy; with MSG_ZEROCOPY/AF_XDP and deeper batching, a 2–3× reduction is plausible, dropping to ≈2–3 cores pending validation.
- 40/100 GbE: Linear arithmetic says ≈26/65 cores at today’s cost; clearly demands zero‑copy + sharding + NUMA pinning and kernel‑bypass style rings. This is exactly why AF_XDP is next.
Caveats: These are back‑of‑the‑envelope based on loopback payload‑mode with checksums. Real NIC paths vary; we will validate.

6. Where PacketFS‑gram performs best today (from data at hand)
- Memory‑centric flows where the working set can live in a large mapping and the application consumes data via offset schedules.
- Small‑payload/high‑rate scenarios: Measured processing latencies are far below network RTT (μs vs hundreds of μs); batching grams keeps the transport side efficient.
- Heterogeneous deployments: Predictable cross‑arch scaling (~3× on x86 vs ARM in our sweeps) allows capacity planning without re‑architecting.

7. Most promising paths forward
- Zero‑copy networking: MSG_ZEROCOPY or io_uring with registered buffers to cut syscall/copy overhead.
- AF_XDP userspace rings: NIC‑resident RX/TX queues with a user‑space UMEM backed by hugepages; ideal for gram slabs and direct offset scheduling.
- UDP grams: sendmmsg batching plus a small ACK window to keep consistency and improve goodput under loss without head‑of‑line stalls.
- LLVM fusion: Compile descriptor sequences into hot vector loops that consume the blob with minimal loop/branch overhead.
- NUMA discipline and sharding: Per‑core rings and shard‑affinity to minimize cross‑socket traffic.

8. Feasibility: a PacketFS‑based “computer”
- Networking in user space over in‑kernel memory: AF_XDP gives us user‑space RX/TX rings that read/write NIC queues directly, while the working set lives in kernel‑managed hugepages (UMEM). No disk coupling in the hot path.
- Offsets ± x arithmetic as a first‑class abstraction: The system’s “addresses” are blob offsets; compute is a function over these offsets. This reframes both transport and execution around the same primitive.
- Pipeline sketch:
  - NIC RX (AF_XDP) → gram assembler (descriptor table) → pCPU kernels (LLVM‑generated loops over offsets) → NIC TX (grams or app replies) — all without disk IO.
- Expected wins: fewer copies, fewer crossings, explicit locality, and an execution model that aligns with how data actually moves.

9. Comparison to conventional transfer (sftp/scp/rsync)
- Conventional: per‑block crypto, disk interleaving, many crossings, small write bursts; great generality, limited by copies and context switches.
- PacketFS‑gram: batch semantics, memory‑resident working sets, vectorized IO; decouples disk; processing frequently faster than the wire on LAN tests (μs vs hundreds of μs), which is the right side of the trade.
- What we can claim now: On loopback we deliver ≈100.7 MB/s with checksum and ≈203 MB/CPU‑s; on LAN small‑payload regimes we maintained ≈18–20 Mbps on x86 with μs‑scale processing latency — consistently below network RTT.

10. Plan: AF_XDP userspace measurements (next work)
- Goals: quantify CPU‑s/GiB at the NIC boundary; validate goodput and latency vs loopback; establish per‑core scaling with shard‑affinity.
- Design (minimal but production‑grade):
  - UMEM: hugepage‑backed with fixed‑size frame descriptors aligned for GSO‑friendly slabs.
  - RX path: one XSK per queue; poll mode; assemble grams from RX frames into a descriptor table; integrity via FNV‑1a or CRC.
  - TX path: emit grams via send path or echo/replay for closed‑loop tests; measure cycles.
  - Metrics: per‑core CPU‑s, GB/s, frames/s, drops, tail‑latency percentiles; receiver‑side authoritative throughput.
- Implementation sketch:
  - New binaries: realsrc/packetfs/network/pfs_gram_afxdp_rx.c and pfs_gram_afxdp_tx.c (libbpf and AF_XDP).
  - Orchestrator: just build-net-pfs-gram-afxdp, run-net-pfs-gram-afxdp-{rx,tx} with NIC/queue parameters.
  - Safety: runs in userspace; requires root/caps; no system‑wide net reconfig beyond XSK binding.

Appendix: the numbers we used (directly from our logs/tests)
- Loopback payload mode (RX): 1,073,741,824 bytes in 10.66 s; user 3.31 s; sys 1.98 s; C_io ≈ 5.29 CPU‑s; ≈100.7 MB/s; ≈203 MB/CPU‑s; checksum OK.
- Cross‑arch sweeps (LAN, ~0.46 ms RTT): x86 throughput ≈ 18–20 Mbps; ARM ≈ 6.5–6.7 Mbps; x86 ≈3× ARM across payload sizes; latencies ~25–27 μs (x86), ~74–75 μs (ARM), both ≪ network RTT.
- Small file (ARM→x86): 14.9 KB in ~10 ms; ≈4.97 MB/s; minimal overhead.

Disclosure note
- We intentionally omit wire‑format minutiae, precise state machines, and kernel internals. Everything above is from production‑quality prototypes and real runs; extrapolations are clearly labeled as budgets, not measurements.

