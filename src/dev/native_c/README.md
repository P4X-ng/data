Native C Engine Scaffold
========================

This directory holds candidate sources for future accelerated components:

- packet_cpu_core.c / packet_cpu_engine.c: logical pCPU low-level primitives
- packet_sharding.c: instruction sharding / mapping logic (to be refactored)
- memory_executor.c / micro_executor.c: execution microkernels (review needed)
- llvm_parser.c: eventual LLVM IR size extraction (stub state)

Refactor Plan (incremental):
1. Identify minimal ABI surface (offset_resolve, packet_execute_batch, stats_snapshot)
2. Remove marketing and unused symbols; consolidate headers
3. Introduce a single `packetfs_engine.h` with opaque handle types
4. Provide Python bindings via cffi or limited CPython extension

Current State: Raw legacy code; NOT compiled in build. See top-level README.
