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

Existing WARP.md (improvement suggestions)
- Found at all-code/dev/functional/WARP.md. It is marketing-heavy and not actionable for development. Replace with a concise, technical summary focused on Just targets and move any demo-oriented prose under demo/ with a prominent DEMO banner per project rules.

File placement
- This WARP.md is canonical and lives only at the repo root. Do not duplicate in subdirectories.
