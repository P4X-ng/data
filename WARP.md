# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Common commands (copy/pasteable; central venv is /home/punk/.venv)
- Environment setup
  - just setup
    - Upgrades pip, setuptools, wheel inside /home/punk/.venv.
- Build native C extension and install package
  - just build-bitpack
    - Runs /home/punk/.venv/bin/pip install -e . against realsrc/, compiles realsrc/packetfs/native/bitpack.c into packetfs._bitpack, validates import, and fixes ownership to punk:punk if needed.
    - Optional verification: /home/punk/.venv/bin/python -c "import packetfs._bitpack as b; print('bitpack OK', b.__name__)"
- Test suites
  - Production Python in this repo (tests exercise src/)
    - /home/punk/.venv/bin/python -m pytest -q tests
    - Single test example:
      /home/punk/.venv/bin/python -m pytest -q tests/test_compress.py::test_gzip_roundtrip_and_stats
  - Dev/working prototype tests (isolated from production)
    - just test
      - Runs PYTHONPATH=realsrc pytest -q dev/working/tests
- Lint and format
  - just lint
    - black --check and flake8 on realsrc and dev/working/tools per .flake8
  - just format
    - black on realsrc and dev/working/tools
  - Improvement recommended: also lint/format src/ to keep the unit-tested scaffold clean. Consider extending Justfile lint/format targets to include src/.
- Cleaning
  - just clean
- Advanced native and network builds (optional for core dev)
  - just build-wip-native                # builds dev tools into bin/
  - just build-net-pfs-gram              # TCP/UDP gram prototypes
    - Run: just run-pfs-tcp-{server,client}
  - just build-net-pfs-gram-udp
    - Run: just run-pfs-udp-{server,client}
  - just build-net-pfs-stream-afxdp      # AF_XDP userspace stream
    - Run: just run-pfs-stream-afxdp-tx and just run-pfs-stream-afxdp-rx
  - Hugepages helpers and 1GiB workflows
    - just hugepages-status
    - just hugepages-mount
    - just pfs-1g
    - just run-pfs-tcp-1g-*              # server/client variants
  - Note: Some run/stream commands require root or capabilities and system libraries (AF_XDP, libxdp/libbpf, NIC/XDP support). These are optional; not needed for core Python tests.

High-level architecture (big picture)
- Dual-tree layout with distinct purposes
  - src/packetfs: clean scaffold used by unit tests under tests/
    - fs/: compression (gzip wrappers and simple stats), packet_store (in-memory + mmap store), object_index (splits bytes into MTU-sized packets; maintains object→packet ids), execution_adapter (streams stored packets through PacketExecutor).
    - pcpu/: pCPU virtualization — PCPUConfig (tuning constants), PCPURegistry (lazy logical pCPU activation/metrics), PCPUScheduler (bounded worker pool + batch dispatch + backpressure), PacketExecutor (bridges packets to scheduler; collects results/stats).
    - protocol/: SyncConfig + ProtocolEncoder/Decoder (windowed sync units; CRC16). Encoder expects C extension packetfs._bitpack for pack_refs. Unit tests monkeypatch _bitpack.
    - network/: raw Ethernet helpers (raw sockets; requires root if used).
  - realsrc/packetfs: production package used when installed via pip -e .
    - protocol.py: same API surface; uses C extension if present.
    - exec/: IRExecutor and windowed scheduler that encode op references; optional native libpfs_exec.so acceleration; micro_executor interoperability.
    - filesystem/: virtual shared-memory blob and a tmpfs-backed mount utility; metrics and dedup logic.
    - network/: prototypes including TCP/UDP “gram” and AF_XDP streaming userspace endpoints; BPF/XDP kernel object source; requires system libs and privileges.
    - native/bitpack.c: compiled by setup.py into packetfs._bitpack.
- Packaging split
  - pyproject.toml and setup.py package from realsrc/ (demo/dev/old excluded).
  - tests/ import src/ via tests/conftest.py which inserts src/ into sys.path.
- Consequence
  - In-repo tests exercise src/, whereas pip-installed usage exposes realsrc/. Keep these flows separate to avoid mixing demo/legacy code with production.

Important notes and pitfalls (repo-specific)
- Always use the central venv path
  - Use /home/punk/.venv/bin/... explicitly in commands. Do not create new venvs unless conflicts require. When running as root, fix ownership back to punk:punk if needed.
- C extension dependency
  - ProtocolEncoder.pack_refs requires packetfs._bitpack. Unit tests monkeypatch it; for real encoding/decoding, run just build-bitpack first.
- Raw sockets and AF_XDP
  - Network send/stream helpers require root/capabilities and system dependencies (libxdp/libbpf, correct NIC/XDP support). Not required for core Python tests.
- Lint scope gap
  - Justfile currently lints realsrc/ and dev tools, but not src/. Add src/ to lint/format targets to keep the tested scaffold clean.
- Directory hygiene
  - demo/, all-code/, fake_trash/, old_code/ contain demos/legacy/fictional content; they must not be used in production flows. tests/ + src/ are the canonical Python dev path; realsrc/ + Justfile targets are the canonical production/native path.
- Containers
  - None of the core flows require containers. If you containerize, prefer Podman over Docker.

AF_PACKET capture harness (kernel-backed, hugepage user ring)
- Build
  - just build-net-async            # also builds dev/working/tools/pfs_afpkt_rx and symlinks bin/pfs_afpkt_rx
- One-time capability (so you can run without sudo)
  - just net-afpkt-cap              # grants CAP_NET_RAW to bin/pfs_afpkt_rx
- Run (examples)
  - Pinned single-CPU smoke test (2s on loopback, emits plan JSON, peeks MMIO):
    - just run-net-afpkt-smoke 2 0
  - Pinned run on a specific interface (example enp130s0, 5s):
    - just run-net-afpkt-iface iface="enp130s0" duration="5" cpu="0"
  - Check capability status quickly:
    - just net-afpkt-cap-status
  - Direct run (after capability set):
    - bin/pfs_afpkt_rx --iface IFACE --duration 10 --blob-size 1073741824
  - With pCPU:
    - bin/pfs_afpkt_rx --iface IFACE --pcpu 1 --pcpu-metrics 1 --prog counteq:0 --duration 10
  - With fanout (single process, hash):
    - bin/pfs_afpkt_rx --ifaces IF1,IF2 --fanout-id 1337 --fanout-mode hash --duration 10
  - With LLVM-inspired optimizer plan and persisted plan file:
    - bin/pfs_afpkt_rx --iface IFACE --llvm-opt 1 --llvm-hint network/crc --plan-out /tmp/pfs_afpkt_plan.json --duration 10
- Notes
  - If you see "Operation not permitted", run: just net-afpkt-cap (requires sudo)
  - Single-core pinning: use taskset -c 0 for runs where you want to avoid multicore
  - Stores payload slices into a hugepage blob (use --huge-dir/--blob-name to control path)
  - --plan-out writes a JSON plan with effective settings for downstream consumers

bin/ tools overview (symlinked executables)
- Purpose: keep dev/wip/native sources clean while exposing runnable binaries in bin/.
- Symlinks are created by build recipes; run them directly from bin/.

Common tools and how to build them
- pfs_afpkt_rx (AF_PACKET RX harness)
  - Build: just build-net-async
  - Run: just run-net-afpkt-rx ifname="IFACE" duration="10"
- rtl_peek_mmio (Realtek MMIO peek helper)
  - Build: just build-rtl-peek
  - Run: just run-rtl-peek bdf="0000:82:00.0"
- pfs_shm_ring_bench (shared-memory SPSC ring bench)
  - Build: just build-shm-ring
  - Run: just run-shm-ring-bench
- pfs_async_tx / pfs_async_rx (async prototypes)
  - Build: just build-net-async
- pfs_proto_async (native protocol async server/client)
  - Build: just build-net-pfs-async
- pfs_gram / pfs_gram_udp (PacketFS-gram TCP/UDP)
  - Build: just build-net-pfs-gram and just build-net-pfs-gram-udp
- pfs_stream_afxdp_tx / pfs_stream_afxdp_rx (AF_XDP streaming)
  - Build: just build-net-pfs-stream-afxdp
- pfs_stream_dpdk_tx / pfs_stream_dpdk_rx (DPDK streaming)
  - Build: just build-net-pfs-stream-dpdk
- cpu_baseline (CPU throughput baseline)
  - Build: just build-cpu-baseline
  - Run: just run-cpu-baseline
- blueprint_reconstruct (native reconstructor)
  - Build: just build-blueprint-native
  - Used by: dev/working/tools/bench_blueprint_* and memory_monster --native
- llvm_parser, memory_executor, micro_executor, swarm_coordinator, bench_exec, libpfs_exec.so
  - Build: just build-wip-native (subset also built by build-llvm-parser and build-bench-native)

Notes
- Many Just run recipes now reference bin/ (preferred). Scripts and Python tools are updated to prefer bin/ and fall back to dev/wip/native/ for resilience.
- just clean will remove bin/ symlinks; rebuild with the relevant build-* targets.

Existing WARP.md (improvement suggestions)
- Found at all-code/dev/functional/WARP.md. It is marketing-heavy and not actionable for development. Replace with a concise, technical summary focused on Just targets and move any demo-oriented prose under demo/ with a prominent DEMO banner per project rules.

File placement
- This WARP.md is canonical and lives only at the repo root. Do not duplicate in subdirectories.

---

pCPU throughput (CPUpwn v2 summary)
- CPUpwn v2 definition: CPUpwn = pCPU_MB/s ÷ CPU_baseline_MB/s, where CPU_baseline is measured with the same op and hot working set using the same number of CPU threads as pcores (e.g., 64 pcores → 64 CPU threads).
- Setup that achieved top results on this host (2025-09-22):
  - 64 logical CPUs; blob=4 GiB; hot working set=1 GiB; ring_pow2=19; slab_mb=32; dpf=64; align=64.
  - Producer publishes to per-core rings in /dev/shm; each consumer pinned to a CPU; arithmetic ops applied in the consumer.
- Quick commands:
  - CPU baselines (reference):
    - Single-thread: dev/wip/native/cpu_baseline --size-mb 1024 --dumb
    - Multi-thread:   dev/wip/native/cpu_baseline --size-mb 1024
  - pcores (1 GiB hot range):
    - dev/wip/native/pfs_proc_pcores \
      --pcores $(getconf _NPROCESSORS_ONLN) --duration 10 --blob-mb 4096 \
      --dpf 64 --align 64 --ring-pow2 19 --slab-mb 32 \
      --op xor --imm 255 --range-off 0 --range-len $((1024*1024*1024))
- Results snapshot (64 pcores, 10s):
  - xor/add: ≈15.5–15.8 GB/s, CPUpwn(=64CPU) ≈ 6.0–6.4×
  - counteq: ≈50.2 GB/s,     CPUpwn(=64CPU) ≈ 7.15×
  - fnv:     ≈28.7–29.0 GB/s, CPUpwn(=64CPU) ≈ 24×
  - crc32c:  ≈8.36 GB/s,      CPUpwn(=64CPU) ≈ 52.8× (will drop with accel baseline; absolute MB/s stays high)
- How to push further:
  - Larger rings/slabs (e.g., ring_pow2=20, slab_mb=64), smaller hot range (e.g., 512 MiB), longer steady-state.
  - NUMA-aware pinning (bind producer+consumers per node), interleave/pin blob accordingly.
  - Add SSE4.2/PCLMUL CRC32C and tuned SIMD CPU baselines for fair CRC/hot loops.
- Implementation notes:
  - pfs_fastpath module updated for modern kernels (vm_flags_set, remap_vmalloc_range fallback) and validated with staging program-carrying TX/RX.
  - pcores runner uses /dev/shm channel for interprocess visibility; CPUpwn(=NCPU) is logged with baseline(NCPU).

---

Local pCPU fast path and recent results (2025-09-11)
- Fastest local path (no kernel, no DPDK, no NIC): shared-memory rings on hugepages
  - Tool: dev/wip/native/pfs_shm_ring_bench (producer/consumer SPSC ring; descriptors reference spans in the hugepage blob; consumer applies pCPU ops in-place)
  - Example run (2 threads, varint+arith, dpf=64, ring=2^16, align=64, duration=5s):
    - just run-shm-ring-bench
    - Output snapshot: [SHM DONE] eff_bytes≈1.613 GB elapsed≈5.011 s avg≈321.9 MB/s
  - Why: zero syscalls after setup, zero copies; it’s the baseline to optimize pCPU execution.

- DPDK runtime (EAL/mempools) with AF_PACKET vdev (kernel-backed) for transfer validation
  - TX-only on enp130s0 (Realtek r8169) 10 s: avg ≈ 85.9–93.7 MB/s, total ≈ 0.86–0.89 GB
  - End-to-end enp→enx with Ethernet + PVRT header (L2 skip=14): TX ≈ 86 MB/s, RX mid-burst ≈ 72 MB/s, RX total ≈ 0.80 GB
  - Note: This uses net_af_packet virtual devices (no NIC binding). Realtek 8168 has no DPDK PMD; for PMD/VFIO use Intel X710/XXV710/E810 or Mellanox mlx5 later.

- AF_XDP on USB NICs: fell back to XDP generic (skb) → very low throughput. Expected for that device/driver class; not a blocker for pCPU.

- Protocol framing hardening
  - Minimal PVRT header (magic/version/align_shift/payload_len) bounds the varint region and carries alignment.
  - RX requires PVRT when L2 skip is used to avoid parsing non-our frames (“martians”).

- pCPU instruction set (v1)
  - fnv64 checksum, crc32c checksum, xor imm8, add imm8, counteq imm8 (reduction; aggregated in checksum_out)
  - Available in RX paths and the SHM local loop.

- We ‘pwned’ a CPU in prior blueprint sweeps
  - In contiguous small-segment profiles (e.g., seg_len≈80B, coalescing on), pCPU reconstructor hit ≈17× ops_ratio vs CPU baseline in earlier Max‑Win runs.
  - Native microbench: peak ≈ 62M ops/s (tight ALU loop). pCPU scheduler bench: throughput_tasks_per_sec ≈ 15,382 (threads=4, batch=4096, reps=8).

How to run the fast local path
- Build local tools: just build-wip-native
- Run local pCPU ring bench (edit knobs inline):
  - just run-shm-ring-bench
  - Flags (override in the recipe):
    - --blob-size BYTES, --dpf N, --ring-pow2 P, --align A, --duration S, --threads 1|2, --arith 0|1, --vstream 0|1, --pcpu 0|1, --pcpu-op fnv|crc32c|xor|add|counteq, --imm N

Next steps (roadmap)
- pCPU programs: define a tiny program format (sequence of ops + imm/flags) and 2–4 accumulators in metrics. Single-pass first; fuse/SIMD later.
- shm-ports: multi-port, multi-queue on a single core; then multi-core scheduling. Same CLI shape as DPDK runners.
- pGigantoRing + GPU (CUDA) prototype:
  - Control ring in pinned host memory; batch descriptors; GPU kernels for counteq/hist8/crc32c over coalesced spans; return accumulators (R0..R3).
  - Overlap H2D/kernels/D2H with 2–3 CUDA streams; tune batch sizes for occupancy.
- Transfer track (later): keep AF_PACKET for validation; move to PMD/VFIO on a supported NIC to chase line-rate.

---

PacketFS filesystem = the blob (2025-09-14)
- What’s new (high level)
  - Translation daemon: watches a directory, ingests files, emits IPROG blueprints (per-window PVRT containers with BREF-only by default) using the shared VirtualBlob.
  - BREF-only PVRT on-wire: PROTO omitted by default for transmission; receiver reconstructs from BREF against the blob; tx_ratio ≈ 0.2–0.3% (64 KiB windows on 100 MiB files).
  - WebSocket sender CLI: pfs-arith-send streams .iprog.json windows (PVRT) to the receiver with DONE and reports elapsed + tx metrics.
  - FUSE mount (read-write): pfsfs-mount exposes a filesystem view where writes compile-on-close to IPROGs. Reads reconstruct from the blob. Unlink/rename supported.
  - Palette mode (no-payload writes): mount flag --mode palette compiles files to references over a deterministic palette region in the blob (no blob appends). First cut implemented; compiler is tile-based with exact/xor matching. Further ARITH ops to follow.

- Where files live now
  - Blob is the only payload store. We do NOT keep duplicate bytes elsewhere. Append mode writes into the blob; palette mode writes nothing (only blueprint programs).
  - Sidecars are tiny: IPROGs (~200–300 KiB for a 100 MiB file) and a small SQLite metastore for offsets and alloc state.

- Key commands (copy/pasteable)
  - Translate on arrival:
    - just trans-daemon watch_dir="./ingest" out_dir="./iprog" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337" window="65536"
  - Mount FS (read-write default; embed PVRT for streaming):
    - just pfsfs-mount mnt="./pfs.mnt" iprog_dir="./iprog" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337" window="65536" embed_pvrt="1" meta_dir="./pfsmeta"
  - Mount FS (read-only):
    - just pfsfs-mount-ro mnt="./pfs.mnt" iprog_dir="./iprog" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337" window="65536" meta_dir="./pfsmeta"
  - Send a blueprint (.iprog.json) to a receiver over WS:
    - just arith-send iprog="./iprog/file.iprog.json" host="127.0.0.1" port="8088"

- Implementation details
  - PVRT container: sections RAW=0x01, PROTO=0x02, BREF=0x03; magic POX1. We emit BREF-only by default to minimize on-wire.
  - Receiver: reconstructs from BREF via VirtualBlob; validates per-window CRC if PROTO present; accepts RAW as fallback (rare in palette mode).
  - FUSE read path: reconstruct windows lazily; pending open files (not yet compiled) are served from temp until close.
  - FUSE write path (append mode): temp file → blob append via BlobFS (wrap-aware) → IPROG with BREF+PVRT → index update. Unlink/rename supported (GC to follow).
  - FUSE write path (palette mode): temp file → tile compile (exact/xor over palette) → IPROG with BREF-only PVRT or PVRT+RAW when needed; no blob writes.
  - Palette region:
    - VirtualBlob.ensure_filled now includes a deterministic palette region after the header (≈256 KiB): 256 tiles × 256 B for families const, ramp, gray, lfsr (total 1024 tiles).
    - Palette layout is stable/deterministic from (name,size,seed) so references match across hosts.
    - The remainder of the blob is filled with a deterministic xorshift block (unchanged) for incidental coverage and future ops.
  - Palette compiler (v1):
    - Tile size 256 B. For each tile: try exact match from const/ramp/gray/lfsr; try xor imm8 for const/ramp; fallback RAW per window for unmatched tiles (v1). Metrics recorded per window and file (pvrt_total, tx_ratio, raw_fraction).

- Roadmap (near-term)
  - Append mode GC/dedup: window hash map; refcount per segment; freelist; allocator prefers free segments.
  - ARITH ops in PVRT: add/add+rol tile ops with small immediates; encode imm in flags; reduce RAW further.
  - Binary control frames for WIN/END (replace JSON) to drop per-window control overhead.
  - Journal/FSCK: append-only op log for mount, with compaction.
  - QUIC sender: pfs-arith-send-quic parallel to WS.

- Metrics and expectations
  - On-wire PVRT (BREF-only): ≈ 0.2–0.3% for 64 KiB windows over a 100 MiB file using WS JSON controls today; lower with binary controls.
  - IPROG size: ≈ 0.2–0.3 MB per 100 MB file (depends on JSON verbosity, base64 pvrt if embedded).

- Developer notes
  - All new entry points are installed via setup.py and routed through the central venv (/home/punk/.venv).
  - Modules added: filesystem/pvrt_container.py, filesystem/blob_fs.py, filesystem/iprog.py (palette builder too), filesystem/iprog_recon.py, filesystem/palette.py, filesystem/pfsfs_mount.py; tools/arith_send.py; tools/translate_daemon.py.
  - Defaults can be tuned via mount flags and daemon args.

---

Pattern-Oriented Blob (POB) and multi-pass planning (2025-09-14)
- Goal: Stop searching a pseudo-random blob; design the blob as a pattern-oriented dictionary, then index it and use tiny transforms (xor/add imm8) to map file windows to blob offsets. Emit blueprints of {offset, len, transform} and fall back to raw bytes only for misses.

POB bank design (compose per workload)
- Executable codelets and prologues
  - x86-64: function prologue/epilogue sequences, stack adjust, common NOP runs, short relative branches, jump tables (4-byte stride)
  - AArch64: stp/ldp prologues/epilogues, adrp/add pairs, ret
- Alignment/padding and tables
  - Long 0x00 (and 0xCC) runs, string/rodata patterns, relocation and import table shapes
- Archive/image markers
  - ZIP PK headers, TAR block structure, GZIP header; PNG signature and chunk tags; JPEG SOF/DQT/DHT/SOS markers
- Structured tokens and text
  - JSON/CSV/INI tokens, braces/quotes/colons/commas, whitespace runs; common literals (true/false/null)
- Varint/numeric banks
  - LEB128/protobuf-style runs; monotone/strided LE/BE integers (1/2/4-byte steps)
- Periodicity and coverage banks
  - De Bruijn (nibble or byte) tiles for guaranteed short k-grams; modulo stripes at 64/128/512/4096 to ease offset-mod hits
- Pseudo-random tail
  - Preserve a prand region for generality and hashing sanity

Transform set (pCPU-friendly)
- identity
- xor imm8
- add imm8
- These align with pCPU v1 ops (xor/add imm8, crc32c, counteq) and keep reconstruction cheap.

Indexing and planning
- Build a compact k-gram index over chosen banks (e.g., k=4). Store hash → limited fanout offsets.
- Planner loop per window (e.g., 4KB): try transforms T∈{id,xor,add}. Apply inverse T to the anchor bytes, query index, confirm on 16–64 bytes. Emit segments; coalesce; fallback to raw when no match.
- Bias by file type (ELF/PE/PNG/ZIP) and modulo remainder classes for stable alignment.

Multi-pass pipeline (choose smallest representation)
1) Raw binary pass
   - Plan directly over the file; ideal for headers, rodata, tables, padding.
2) LLVM-informed pass
   - Use llvm-readelf/objdump-derived structure and mnemonic histograms to weight banks and transforms by section/mnemonic. Opportunity: codelets tailored to platform/ISA.
3) Offsets + arithmetic pass
   - Combine segments from (1) and (2) and allow xor/add imm8 transforms; select the minimal total bytes (blueprint vs raw spill).

Background window-hash sync (change-driven transfers)
- Both sides continuously compute per-window fingerprints (e.g., CRC32 or XXH3) over rolling windows (aligned or sliding). Expose a tiny window-hash map:
  - Sender posts hashes; receiver replies with “match/miss by window”.
  - A change signals transfer; only missed windows are planned (offset+transform or raw spill). This pipeline piggybacks on pattern_scan CSVs we already produce (crc32.csv) and can be extended to XXH3.

Tools and helpers added today
- Pattern scanner (enhanced): dev/working/tools/pattern_scan.py
  - Flags: --zlib, --lags/--lags-set, --delta, --dupes, --magic
  - Outputs: zlib.csv, lags.csv, delta_entropy.csv, dupes.csv, magic.txt alongside existing CSVs
- Entropy heatmap: dev/working/tools/entropy_heatmap.py (PPM, dependency-free)
- LLVM correlation: dev/working/tools/llvm_findings.py (sections ↔ entropy; mnemonic histogram)
- Async single-core worker: dev/working/tools/async_core.py
  - Watches logs/patterns/queue/*.json; runs pattern scans in a controlled single-core loop
- Simple wrappers (keep Just thin):
  - scripts/patterns/scan_file.sh, scan_blob.sh, llvm_findings.sh
  - scripts/patterns/enqueue.py (+ enqueue_file.sh, enqueue_blob.sh)

Quickstart (pattern + LLVM)
- Scan a file with extras
  ```bash path=null start=null
  just dev-pattern-scan-file path=/usr/bin/bash zlib=1 lags=1 delta=1 dupes=1 magic=1
  ```
- Correlate with sections/mnemonics (latest scan-dir)
  ```bash path=null start=null
  just dev-llvm-findings scan_dir=$(ls -1dt logs/patterns/* | head -1) bin=/usr/bin/bash
  ```
- Async loop and queued runs
  ```bash path=null start=null
  just dev-async-core cpu=0
  just dev-async-queue-blob name=pfs_vblob_test size_mb=1024 seed=1337 zlib=1 lags=1 delta=1 dupes=1 keep=1
  just dev-async-queue-file path=/usr/bin/bash zlib=1 lags=1 delta=1 dupes=1 magic=1
  ```

POB/Planner roadmap (implementation notes)
- VirtualBlob: add profile=orchard and a manifest (banks, seed, size, sha256); preserve prand default for backwards-compat.
- Indexer: scripts/patterns/blob_index_build.py (k-gram → offsets)
- Planner: scripts/patterns/planner.py (emit blueprint.json with id/xor/add imm8; coalesce segments; spill raw on misses)
- Just recipes (thin):
  ```bash path=null start=null
  just dev-blob-build profile=orchard size_mb=1024
  just dev-blob-index name=pfs_vblob_test size_mb=1024 k=4
  just dev-plan-file path=/usr/bin/bash
  ```

Cross-architecture integrity (critical findings)
- Prior investigation found deterministic corruption across x86_64↔ARM64 transfers (likely endianness/packing). Until fixed, treat cross-arch runs with caution:
  - Add architecture-aware handshake and transform-stable hashing (little-endian anchors).
  - Unit-test encoder/decoder and _bitpack C extension on both architectures.
  - Prefer same-arch validation for POB/Planner bring-up, then expand to cross-arch with an endian gate.

Terminology
- POB (Pattern-Oriented Blob): deterministic shared blob composed of domain-specific banks for matchability.
- Bank: contiguous region with engineered patterns (codelets, tokens, varints, de Bruijn, periodic stripes, prand tail).
- Transform: bytewise imm8 operation (xor/add) to morph to nearby patterns cheaply in pCPU.
- Planner: tool that emits a blueprint of {offset, len, transform} with raw spill fallback.
- Window-hash sync: per-window fingerprints exchanged to detect changes and drive minimal re-planning.

Notes
- Keep Just targets simple; push logic into scripts/ under scripts/patterns/.
- All Python tooling uses the central venv (/home/punk/.venv). If run as root, chown artifacts back to punk:punk.

---

SHM ring bench — glossary and quick recipes (2025-09-15)

Terms (as used by dev/wip/native/pfs_shm_ring_bench)
- blob-size: bytes of the mapped hugepage blob (payload source). Use 1 GiB (1073741824) by default.
- dpf (descriptors per frame): how many packet spans (offset,len) are batched into one ring slot. Typical: 16–64.
- ring-pow2: ring size per ring = 2^ring-pow2 slots. E.g., 20 → 1,048,576 slots.
- align: alignment in bytes applied to segment offsets/lengths (common: 64).
- duration: seconds to run. Bench prints rolling averages every ~0.5s.
- threads: 1 = single-thread loop; 2 = producer + consumer (current model).
- arith: 1 → arithmetic/blueprint mode; 0 → fixed-descriptor mode.
- vstream: 1 → varint streaming payloads (allocates payload_max per slot); 0 → disable.
- payload-max: per-slot payload buffer size when vstream=1 (default 2048). Large total when rings are huge.
- pcpu: 1 → apply a pCPU op in the consumer (fnv/xor/add/counteq/crc32c) over the spans; 0 → none.
- pcpu-op: which pCPU op (fnv, crc32c, xor, add, counteq). Avoid crc32c for hot loops (slow bitwise path today).
- imm: 8-bit immediate for xor/add/counteq (e.g., 255, 7, 0).
- ports, queues: total rings = ports × queues. Outstanding slots = total rings × (2^ring-pow2).
- mode: scatter (random-ish span placement) or contig (sequential spans). Contig uses seg-len.
- seg-len: per-span length in contig mode (bytes). Often 80, 256, 4096.
- reuse-frames: prebuild fixed descriptors once (contig mode only) and reuse; cuts CPU overhead.
- prefetch-dist: consumer descriptor prefetch distance.
- frames_prod/frames_cons: progress counters printed in stats.
- bytes_eff: sum of lengths consumed (effective bytes processed).

Caution: varint streaming (deprecated for stress workflows)
- Varint payloads (arith=1 & vstream=1) allocate payload_max bytes per ring slot. With massive rings/queues this explodes RAM.
- For stress/high-concurrency, prefer fixed-descriptor mode (arith=0 or vstream=0).

Quick recipes (flags-based helper)
- Human-friendly runner (prints variables + memory estimate):
  - just dev-shm-run             # defaults: 1 GiB, 2^20 ring, 2 queues, arith=0, vstream=0, seg_len=256
  - just dev-shm-run-1_5m       # ≈1.57M outstanding (2^19 ring, 3 queues), fixed descriptors
- Example: pCPU xor path (2 threads, ~1.57M outstanding)
  ```bash
  bash scripts/benchmarks/shm_run.sh \
    --blob-mb 1024 --dpf 32 --ring-pow2 19 --align 64 \
    --duration 5 --threads 2 --arith 0 --vstream 0 \
    --ports 1 --queues 3 --mode scatter --seg-len 256 \
    --pcpu 1 --pcpu-op xor --imm 255
  ```

Future extension
- Multi-consumer (N consumers = “N pCPUs”) is a planned extension; today pcpu=1 toggles a single pCPU op in the consumer. Use queues×ring to raise outstanding work.

---

Work log — 2025-09-14 (Pattern scan, Planner, Binary blueprint packer)

Summary of today’s work
- Repository/flow check
  - Verified Just dev targets exist for patterns and planning: dev-pattern-scan-file, dev-pattern-scan-blob, dev-blob-build, dev-blob-index, dev-plan-file.
  - Confirmed central venv at /home/punk/.venv (Python 3.12.3). AUTOMATION.txt was not present at time of this log; runs proceeded manually.
- New tool added: scripts/patterns/blueprint_pack.py
  - Purpose: pack blueprint JSON into a compact binary format (.pbb) and an optional .xz for smaller on-the-wire/control-plane payloads.
  - Approach: per-integer adaptive selection between LEB128 varint and packed-32 (5-bit) digits; segment opcodes are single-byte. Magic header “PBB1”.
  - Scope: packs metadata for id/xor/add/raw segments. Raw segments only carry length; raw bytes themselves are not embedded (to keep control-plane light). Pair with a data-plane artifact when needed.
- Planner/indexer status
  - Planner and index tooling are present (scripts/patterns/planner.py, blob_index_build.py). Multi-anchor offsets and k=8 secondary index are planned next to increase hit rates, along with cross-window coalescing.
- Execution note (Warp terminal)
  - Some command attempts were cancelled in-session; re-runs will be done in the next iteration (see Quick actions below).

Blueprint packer details (scripts/patterns/blueprint_pack.py)
- File header: ASCII magic “PBB1”.
- Integer encoding (per value, chosen by size):
  - 0x00 + LEB128 unsigned (7-bit payload per byte; MSB=continuation)
  - 0x01 + packed base-32 digits (5 bits per digit, LSB-first; digits packed into bytes)
- Segment encoding:
  - id:  op=0x00, fields: offset, len
  - xor: op=0x01, fields: offset, len, imm8
  - add: op=0x02, fields: offset, len, imm8
  - raw: op=0x03, fields: len  (metadata only; payload carried separately)
- Compression: emits a parallel .pbb.xz using LZMA2 (xz) for improved ratio when desired.

Usage
- Pack a blueprint JSON alongside the source:
  ```bash path=null start=null
  /home/punk/.venv/bin/python scripts/patterns/blueprint_pack.py --in plans/example_blueprint.json
  ```
  - Outputs: plans/example_blueprint.pbb and plans/example_blueprint.pbb.xz
- Notes
  - Use chown if you executed as root and artifacts landed with root ownership:
    ```bash path=null start=null
    sudo chown -R punk:punk plans logs/patterns
    ```
  - For inspection, a future enhancement will add a --dump flag to pretty-print .pbb files for debugging.

Quick actions queued for next iteration
- Planner improvements
  - Anchor probing at offsets {0, 64, 128, 256} per window; k=8 fallback on miss; confirmation window 16–64 B; cross-window coalescing of adjacent segments.
- Orchard coverage bank
  - Add a nibble (k=6) De Bruijn bank (~16 MiB) tiled through the orchard profile to guarantee short k-gram anchors and improve hit rates.
- Metrics & regression harness
  - Persist per-run metrics (segments, match mix, raw spill bytes, blueprint bytes, .xz bytes) into logs/patterns/*.jsonl for trend tracking.
- Just integration (proposed)
  - Add dev-plan-pack to invoke blueprint_pack.py on a produced blueprint, wired through justfile.vars and central venv.
- LLVM integration (initial)
  - Minimal opt plugin to emit section ranges + mnemonic histograms; planner bias by section type (code vs data) in anchor selection and bank weighting.

If AUTOMATION.txt is created at repo root
- The build will enter autonomous mode per project rules. Next steps will execute without further prompts (KEEP BUILDING), starting with the Planner improvements and orchard bank addition above, followed by metric harness and Just target additions.
