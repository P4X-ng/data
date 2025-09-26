# PacketFS — Repository Overview and Fast Paths

Executive summary
- This repo implements a local, high-throughput “pCPU” execution model where programs are arithmetic transforms over byte ranges (descriptors) in a shared hugepage blob.
- The fastest current path is shared-memory SPSC rings (one ring per pcore/consumer) over 1 GiB hugepages, executed entirely in user space — no NICs.
- We added a prototype kernel char device (/dev/pfs_fastpath) that exports an mmap-able shared ring region for user/user experiments; it is not a NIC TX/RX path.
- Two user-space drivers exist today:
  - pfs_stream_fastpath_tx/rx: shared ring TX/RX between two processes
  - pfs_proc_pcores: multi-process pcore benchmark (one process per pcore) with CPUpwn metric and arbitrary program support via --prog
- AF_PACKET (PACKET_TX_RING) is available as a baseline network path for experiments. AF_XDP/DPDK paths exist but are secondary to the local pCPU path.

Normalized repository structure (target model)
- src/           — Production code (stable APIs). Example: src/packetfs/{ring,memory,pcpu,gram}
- staging/       — “Almost done” code stabilizing before promotion to src/
- dev/           — Active development, prototypes, research utilities
- utils/         — Project utilities and standalone helpers
- bin/           — Built/linked executables (symlinks preferred where possible)
- tests/         — Tests for production code (pytest or native test runners)
- theoretical/   — Design notes, research, ideas
- full_apps/     — Complete applications built on PacketFS primitives
- docs/          — Documentation, how-tos, and architecture notes

Current highlights (what’s where)
- Production library code (stable)
  - src/packetfs/memory/pfs_hugeblob.{c,h}: hugepage-backed blob mapping/filling
  - src/packetfs/ring/pfs_shm_ring.{c,h}: SPSC ring (SPSC indices, lock-free)
  - src/packetfs/pcpu/pfs_pcpu.{c,h}: pCPU operations (xor/add/counteq/crc32c/fnv)
  - src/packetfs/gram/{pfs_gram.c,pfs_gram.h,pfs_insn.h}: descriptors and minimal instruction/gram headers
- Kernel modules (diagnostics + prototype shared ring)
  - src/dev/kernel/pfs_fastpath/pfs_fastpath.c
    - Char device /dev/pfs_fastpath
    - UAPI: docs in src/packetfs/uapi/pfs_fastpath.h
    - ioctls: PFS_FP_IOC_SETUP (allocate/mmap ring region), PFS_FP_IOC_RESET
    - mmap: remap_vmalloc_range; maps [pfs_fp_ring_hdr][u32 slots][slab]
    - Note: No NIC TX/RX here; this is a shared-memory channel for experiments
  - src/dev/kernel/pfs_ringpeek (miscdevice /dev/pfs_ringpeek)
    - Read-only MMIO window into NIC BAR for diagnostics; UAPI at src/packetfs/uapi/pfs_ringpeek.h
  - src/dev/kernel/r816x_peek (read-only peek of RTL816x ring base registers)
- User-space fast paths and runners
  - dev/wip/native/pfs_shm_ring_bench.c — two-thread SPSC producer+consumer benchmark over shared blob
  - dev/wip/native/pfs_stream_fastpath_tx.c — writes descriptor records to /dev/pfs_fastpath ring slab
  - dev/wip/native/pfs_stream_fastpath_rx.c — reads records from ring and applies pCPU ops
  - dev/wip/native/pfs_proc_pcores.c — process-per-pcore runner, region-limited descriptor generation, --prog arbitrary programs, CPUpwn metric, CSV logs
- Network baselines
  - full_apps/osv-yeet/src/yeet_afp_tx.c — PACKET_TX_RING baseline TX with native PFS header
  - full_apps/osv-yeet/src/yeet_afp_rx.c — PACKET_RX_RING (TPACKET_V3) with optional CPU-side ops

Execution model (pCPU programs and data)
- Data = descriptors (PfsGramDesc[]) into a shared blob: {offset, len, flags}. Offsets are absolute and typically aligned (64B).
- Program = tiny sequence of ops: xor/add/counteq/crc32c/fnv (optional imm8), expressed today via --op/--imm or --prog "xor:255,add:7,...".
- Execution = apply the op sequence over each descriptor range. This is AOT-compiled (clang/LLVM -O3/-flto) — no JIT.
- Memory-level programs (recommended)
  - Keep programs inline with the records (future: PfsInsnHdr + PfsInsn[] carried with slab record), so listeners act without network, with maximum locality.

Fast paths (fastest to slowest in practice)
1) Shared memory SPSC rings (no NIC)
   - pfs_proc_pcores (process-per-pcore): one process per ring; zero coordination; best isolation; highest scalability on local host.
   - pfs_shm_ring_bench (threads): two-thread model, good for microbench but less isolation.
2) Shared ring via pfs_fastpath char device
   - Userspace TX/RX binding to the same vmalloc’d mapping via mmap
   - Good for prototyping where two independent processes exchange records; still no NIC
3) AF_PACKET (PACKET_TX_RING / PACKET_RX_RING)
   - Baseline user-space ring to L2; adds socket stack and driver overhead; useful for validation, not the pCPU fast path.
4) AF_XDP / DPDK
   - Potentially faster NIC paths if hardware supports zerocopy; not required for the pCPU local path.

What’s slower and why
- UDP for arithmetic streams: incurs L4 stack overhead and copies; slower than AF_PACKET frames carrying native PFS headers.
- OSv unikernels for this phase: good isolation but adds virtualization/virtio overhead; local-only pCPU testing is faster without VMs.
- AF_XDP on certain Realtek devices falls back to SKB/generic path → limited benefit.

CPUpwn metric (how we report it)
- Baseline: single-process MB/s using the same op over random/region-limited descriptors (≈2 s)
- Aggregate: total MB/s across all pcores
- CPUpwn = (aggregate MB/s) / (baseline MB/s)
- Reported live and final by pfs_proc_pcores; CSV written to logs/pcores_metrics.csv

How to run (copy/paste)
- Build multi-process pcores runner
  - just build-proc-pcores
- Run on a real file (local-only, no NICs), single op example
  - dev/wip/native/pfs_proc_pcores \
    --pcores 256 --duration 10 \
    --blob-mb 4096 --dpf 64 --align 64 --ring-pow2 16 \
    --file /usr/bin/bash --range-off 0 \
    --op fnv
- Multi-op program
  - dev/wip/native/pfs_proc_pcores \
    --pcores 256 --duration 10 \
    --blob-mb 4096 --dpf 64 --align 64 --ring-pow2 16 \
    --file /usr/bin/bash --range-off 0 \
    --prog "xor:255,add:7,counteq:0"

pfs_fastpath (kernel) — what it is today
- Not a NIC fastpath. It’s a prototype char device exporting a vmalloc’d region that contains:
  - pfs_fp_ring_hdr — slots/mask/head/tail/region_bytes/data_offset
  - u32 slots[slots]
  - slab space for variable-length records (descriptor tables and optional instruction payloads)
- User-space responsibilities (via TX/RX tools):
  - Build records in the slab and publish indices in slots (TX)
  - Read indices from slots, parse records, and execute (RX)

Organization roadmap (suggested moves; do after sign-off)
- Promote stable libraries to src/ (already there for memory/ring/pcpu/gram)
- Move nearly-stable runners to staging/ with docs and help targets
  - pfs_proc_pcores once CLI freezes
  - pfs_stream_fastpath_* once UAPI stabilizes
- Keep exploratory tools in dev/
- Ensure all binaries are linked in bin/ (symlinks ok) with Just help
- Add tests/ for core libs (pcpu/ring/memory) and smoke tests for runners

Next steps
- Add program-carrying records: slab record = [PfsInsnHdr + PfsInsn[] + u32 dpf + PfsGramDesc[dpf]]
- Add fused single-pass kernels for common op chains (reduce memory passes)
- Add per-pcore CSV logs; retain aggregate logs/pcores_metrics.csv
- Optional: bring AF_XDP/DPDK back for transfer validation once hardware allows; keep pCPU path local-only for performance validation.