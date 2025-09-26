# WINNING_STRATEGY.md

============================================================
=                   W I N N I N G   S T R A T E G Y        =
============================================================

Purpose
- Capture the end-to-end approach that delivered strong multi-core PacketFS performance and establish a reproducible, documented workflow for planning, benchmarking, and continuous improvement.
- This document is canonical for performance methodology and planner evolution (Orchard profile and Round 3 roadmap).

Environment and repo conventions
- Host: Ubuntu Linux, bash 5.2.21
- Working dir: /home/punk/Projects/packetfs
- Central venv: /home/punk/.venv (use absolute paths, do not create new envs; fix ownership to punk:punk if root is used)
- Container policy: Podman preferred over Docker
- Security: prefer TLS and good security practices; no plaintext secrets in commands
- Repo hygiene:
  - No demo data/code in production flows; demos live under demo/ with an explicit DEMO banner
  - Just help is the default target; shared variables live in justfile.vars
  - RULE: Always check WARP.md, PROJECT.txt, and Justfile before starting

CPUpwn metric (house definition)
- CPUpwn measures effective processing vs a single-core baseline (tight loop). It is a unitless ratio >= 1.0. Larger is better.
- For multi-core/process runs, we report aggregate throughput and CPUpwn for comparability across workloads.

============================================================
1) Multicore SHM ring bench — 64-core “process-per-core” result
============================================================

Summary of the successful run
- Cores: 64 logical CPUs (one process per core)
- Blob: 4 GiB, hugepage-backed (user ring)
- Ring: 2^16 slots per ring, 64 descriptors per frame
- Work: producer publishes descriptors; per-core consumer applies XOR over random spans
- Duration: ~11+ seconds
- Throughput: ~254 MB/s aggregate by the end of the run (rising throughout)
- Frames: >237,000 total across cores
- CPUpwn: ~1950× vs baseline CPU loop
- System: handled full concurrency and memory footprint cleanly (no errors)

How to reproduce (short smoke vs full-scale)
- Short smoke (5s, conservative footprint):
  ```bash
  bash scripts/benchmarks/shm_run.sh \
    --blob-mb 1024 --dpf 32 --ring-pow2 19 --align 64 \
    --duration 5 --threads 2 --arith 0 --vstream 0 \
    --ports 1 --queues 3 --mode scatter --seg-len 256 \
    --pcpu 1 --pcpu-op xor --imm 255
  ```
- Scale-up (process-per-core; tune to your topology):
  ```bash
  # See Justfile dev-shm-run* recipes or invoke scripts/benchmarks/shm_run.sh directly
  # Keep hugepages and memory capacity in mind; rebuild artifacts after large changes per repo policy
  ```

Notes
- For high-concurrency testing, prefer fixed-descriptor mode (arith=0 or vstream=0) to avoid RAM blow-ups.
- If running under root for capabilities, chown -R punk:punk the generated artifacts.

============================================================
2) Orchard profile planner — v3 overview (current state)
============================================================

High-level pipeline
- Snapshot: deterministic Pattern-Oriented Blob (POB) composed of banks (ELF text/data motifs, PLT/GOT/relocs, numeric/ASCII, periodic stripes, de Bruijn tiles, prand tail)
- Index: k-gram indexes (k=4 step=2, k=8 step=8) with bounded fanout
- Hints: section-aware JSON hints (e.g., from llvm-readelf/objdump) inform bank gating per window (.text, .rodata, .data)
- Planner: emits blueprint segments {op,offset,len[,imm8]} with transform set {id, xor, add}, falling back to raw spill when no match
- Packer: scripts/patterns/blueprint_pack.py → .pbb (compact, .xz optional)

Recent improvements
- Orchard bank: increased ELF/text coverage; added common section strings; simulated reloc/PLT/GOT stubs; expanded de Bruijn share for anchor density
- Soft identity matching: optional approximate-equality path (≈92%) in .text windows to reduce raw spill when close matches exist

Artifacts (example from a synthetic JSON run)
- Snapshot: logs/patterns/2025-09-23T17-36-21Z/snapshot.bin
- Index:    logs/patterns/2025-09-23T17-36-21Z/snapshot.kg{4,8}.pkl
- Blueprint: logs/patterns/2025-09-23T13-42-35Z/synth.json.blueprint.{json,pbb,pbb.xz}

Result (synthetic JSON, baseline):
- raw_ratio: 1.000000 (segments=2, id=0, xor=0, add=0, raw=2)
- json_bytes=298, pbb_bytes=15 (control-plane tiny; no matches yet without Round 3 features)

============================================================
3) Round 3 roadmap — planner capability jumps
============================================================

Goals
- Drive raw_ratio down on text-heavy and structured binaries by smarter anchoring and section-aware gating; keep planning fast.

Planned changes
1) Cleanup and resource hygiene
   - Place demo artifacts under demo/ with DEMO banner; keep them out of production flows
   - Resolve Python shared_memory resource-tracker warnings by explicit close/unlink
2) Explicit bank map in manifest
   - Emit snapshot.manifest.json mapping regions → {bank_id, kind}; include in packed metadata
3) Multi-projection anchoring per window
   - Projections: ascii class, nibble, numeric, opcode-like (coarse code-histogram)
   - Build per-projection k-gram keys; choose by section gating
4) Section-aware gating
   - Restrict candidate banks by section kind (.text vs .rodata vs .data); widen only when persistent misses occur
5) Sweep fallback pass (bounded)
   - Linear sweep confirmation on gated banks when the index misses; confirm with 16–64B checks
6) Soft identity splits (half-window)
   - Attempt id/xor/add with soft-id≈92% on halves; coalesce adjacent hits; spill only uncovered regions
7) Index/fanout tuning
   - Raise fanout for .text windows under gating (e.g., k=4 fanout=16) while preserving k=8 for confirmations
8) Metrics and regression harness
   - Persist segments mix, raw_ratio, json_bytes, pbb_bytes, and planner timings to logs/patterns/*.jsonl; track CPUpwn deltas where applicable
9) Just integration (dev- namespace; thin)
   - dev-blob-build, dev-blob-index, dev-plan-file, dev-plan-pack; variables centralized in justfile.vars

============================================================
4) Runbook — commands and paths (copy/pasteable)
============================================================

Pattern + LLVM hints
- Build orchard + indexes (example sizes shown by the tool):
  ```bash
  scripts/patterns/run_orchard_plan.sh --target /usr/bin/bash --hints logs/patterns/<ts>/bash.hints.json
  ```
- Generate LLVM-informed hints (if wrapper present):
  ```bash
  scripts/patterns/llvm_findings.sh --bin /usr/bin/bash --out logs/patterns/$(date -u +%Y-%m-%dT%H-%M-%SZ)/bash.hints.json
  ```

DEMO synthetic JSON (do not use in production)
- Generate:
  ```bash
  /home/punk/.venv/bin/python demo/scripts/generate_synth_json.py --out /tmp/synth.json --size-mb 100
  ```
- Plan (as rodata):
  ```bash
  scripts/patterns/run_orchard_plan.sh --target /tmp/synth.json --hints logs/patterns/<ts>/synth.hints.json
  ```

SHM ring bench
- Conservative smoke (5s):
  ```bash
  bash scripts/benchmarks/shm_run.sh \
    --blob-mb 1024 --dpf 32 --ring-pow2 19 --align 64 \
    --duration 5 --threads 2 --arith 0 --vstream 0 \
    --ports 1 --queues 3 --mode scatter --seg-len 256 \
    --pcpu 1 --pcpu-op xor --imm 255
  ```

============================================================
5) Known caveats and validation
============================================================
- Cross-arch integrity: earlier x86_64↔ARM64 corruption reports; add endian/packing gates for cross-arch until fixed
- Raw sockets/AF_XDP flows require capabilities and system libs (optional for core workflows)
- Keep large ring params in check; varint payload streaming is RAM-heavy (avoid for stress)

============================================================
Appendix A — CPUpwn definition and reporting
============================================================
- Baseline: tight single-core loop on the same class of work (documented in bench harness)
- Report both absolute throughput (MB/s) and CPUpwn; for multi-core, CPUpwn reflects aggregate vs baseline

============================================================
Appendix B — Repro artifact paths (examples)
============================================================
- Snapshot: logs/patterns/2025-09-23T17-36-21Z/snapshot.bin
- Indexes: logs/patterns/2025-09-23T17-36-21Z/snapshot.kg{4,8}.pkl
- Blueprint: logs/patterns/2025-09-23T13-42-35Z/synth.json.blueprint.{json,pbb,pbb.xz}

============================================================
Results — Latest Orchard run (2025-09-23)
============================================================
Target: /usr/bin/bash
- Hints: logs/patterns/2025-09-23T21-27-48Z/bash.hints.json (fallback synthesized: kind=text; llvm_findings wrapper missing Python tool)
- Snapshot: /home/punk/Projects/packetfs/logs/patterns/2025-09-23T21-28-14Z/snapshot.bin
- Indexes:  k4 step=2 fanout=8 entries=53,777,728; k8 step=8 fanout=8 entries=15,502,150
- Window: 4096 bytes
- Result: segments=8  (id=5, xor=0, add=0, raw=3)
  - file_bytes=1,446,024   raw_spill=1,425,544   raw_ratio=0.985837
  - blueprint: logs/patterns/2025-09-23T17-33-19Z/bash.blueprint.json (json_bytes=725)
  - packed:    logs/patterns/2025-09-23T17-33-19Z/bash.blueprint.pbb (pbb_bytes=49); .pbb.xz=96 bytes
Notes
- This confirms modest id matches with most windows still spilling raw on this binary under current Orchard v3.
- Round 3 features (multi-projection anchoring, section-aware gating, sweep fallback, soft-id halves) remain the next lever to drive raw_ratio down.

End of document.
