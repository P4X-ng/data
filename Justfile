# PacketFS root orchestrator (single-target steps, no inline chaining)

VENV_PATH := "/home/punk/.venv"

# C build toolchain
CC := "cc"
CFLAGS := "-O2 -g -Wall -Wextra -pthread"
INCLUDES := "-Idev/wip/native -Idev/wip/packet_cpu"

# LLVM toolchain (override by environment if needed)
CLANG := "clang"
LLVMLINK := "llvm-link"
OPT := "opt"
LLVMDIS := "llvm-dis"
LLVMNM := "llvm-nm"

BC_DIR := "dev/wip/bc"

# Standard targets

setup:
    @echo "Setting up PacketFS dev environment"
    {{VENV_PATH}}/bin/python -m pip install -q -U pip setuptools wheel
    @echo "Done"

build:
    @echo "Build: compile native extensions if packaging is configured"
    @echo "(skipping: provide setup.py/pyproject to enable)"

# Run full working tests
test:
    @echo "Running tests"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python -m pytest -q dev/working/tests

lint:
    @echo "Linting"
    {{VENV_PATH}}/bin/python -m black --check realsrc dev/working/tools
    {{VENV_PATH}}/bin/python -m flake8 realsrc dev/working/tools

format:
    @echo "Formatting"
    {{VENV_PATH}}/bin/python -m black realsrc dev/working/tools

bench:
    @echo "Benchmarks"
    {{VENV_PATH}}/bin/python dev/working/tools/perf_benchmark.py

# Run async NIC saturation prototype (receiver)
run-net-async-rx port="9107":
    @echo "Starting async RX on port {{port}}"
    dev/wip/native/pfs_async_rx --port {{port}}

# Run PacketFS native protocol server/client
run-net-pfs-server port="8337":
    @echo "Starting PacketFS native server on port {{port}}"
    dev/wip/native/pfs_proto_async --mode server --port {{port}}

run-net-pfs-blueprint host="127.0.0.1" port="8337" blueprint="dev/wip/native/sample_blueprint.json":
    @echo "Sending native PacketFS blueprint to {{host}}:{{port}}"
    dev/wip/native/pfs_proto_async --mode client --host {{host}} --port {{port}} --blueprint-file {{blueprint}}

# Run async NIC saturation prototype (sender)
run-net-async-tx host="127.0.0.1" port="9107" seconds="10" buf_kb="64" flows="1" zerocopy="0" bdp_mb="8":
    @echo "Starting async TX to {{host}}:{{port}} for {{seconds}}s (buf={{buf_kb}}KB, flows={{flows}}, zc={{zerocopy}}, bdp={{bdp_mb}}MB)"
    dev/wip/native/pfs_async_tx --host {{host}} --port {{port}} --seconds {{seconds}} --buf-kb {{buf_kb}} --flows {{flows}} --zerocopy {{zerocopy}} --bdp-mb {{bdp_mb}}

# Windowed benchmark (ops, window_pow2)
bench-windows:
    @echo "Windowed benchmark (ops=131072, window_pow2=16)"
    {{VENV_PATH}}/bin/python dev/working/tools/bench_windows.py 131072 16

# Extended windowed benchmark: start at 8,388,608 ops, window=2^16, 60s budget
bench-windows-extended:
    @echo "Extended windowed benchmark (start_ops=8388608, window_pow2=16, budget=60s)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_windows_core.py 8388608 16 60

clean:
    @echo "Cleaning work artifacts"
    find . -name "__pycache__" -type d -prune -exec rm -rf {} +
    find . -name "*.pyc" -delete

# Build and install the C extension into the central venv, then fix ownership
build-bitpack:
    @echo "Building packetfs._bitpack C extension"
    {{VENV_PATH}}/bin/python -m pip install -U pip setuptools wheel
    {{VENV_PATH}}/bin/python -m pip install -e .
    {{VENV_PATH}}/bin/python -c "import packetfs._bitpack; print('bitpack import OK')"
    chown -R punk:punk {{VENV_PATH}}

# Build WIP native tools into bin/
build-wip-native:
    @echo "Building WIP native executables"
    mkdir -p bin
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/memory_executor dev/wip/native/memory_executor.c
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/micro_executor dev/wip/native/micro_executor.c
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/swarm_coordinator dev/wip/native/swarm_coordinator.c
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/llvm_parser dev/wip/native/llvm_parser.c dev/wip/native/llvm_cli.c

# Build async network saturator tools (real source under realsrc)
build-net-async:
    @echo "Building PacketFS async TX/RX (single-threaded async prototype)"
    mkdir -p dev/wip/native
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_async_tx realsrc/packetfs/network/pfs_async_tx.c
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_async_rx realsrc/packetfs/network/pfs_async_rx.c

# Build PacketFS native async protocol (HELLO/BLUEPRINT) with ring-buffered TX
build-net-pfs-async:
    @echo "Building PacketFS native protocol async (server/client)"
    mkdir -p dev/wip/native
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_proto_async realsrc/packetfs/network/pfs_proto_async.c

# Build PacketFS-gram prototype (TCP, hugepage blob, offset-only grams)
build-net-pfs-gram:
    @echo "Building PacketFS-gram (TCP, hugepage blob, grams)"
    mkdir -p dev/wip/native
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_gram \
      realsrc/packetfs/network/pfs_gram_proto.c \
      realsrc/packetfs/memory/pfs_hugeblob.c \
      realsrc/packetfs/gram/pfs_gram.c

# Build UDP PacketFS-gram prototype
build-net-pfs-gram-udp:
    @echo "Building PacketFS-gram UDP"
    mkdir -p dev/wip/native
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_gram_udp \
      realsrc/packetfs/network/pfs_gram_udp.c \
      realsrc/packetfs/memory/pfs_hugeblob.c \
      realsrc/packetfs/gram/pfs_gram.c

# Build AF_XDP streaming executables (pfs-pure streaming)
build-net-pfs-stream-afxdp:
    @echo "Building PacketFS AF_XDP streaming TX/RX (userspace-only rings over kernel memory)"
    mkdir -p dev/wip/native
    # Build XDP kernel object with CO-RE friendly target macro
    sh -c 'arch=$(uname -m); case "$arch" in \
      x86_64) TGT=__TARGET_ARCH_x86;; \
      aarch64|arm64) TGT=__TARGET_ARCH_arm64;; \
      *) TGT=__TARGET_ARCH_x86;; esac; \
      clang -O2 -g -target bpf -D$TGT -I"/usr/include/$(gcc -dumpmachine)" -c realsrc/packetfs/network/bpf/pfs_xdp_redirect_kern.c -o dev/wip/native/pfs_xdp_redirect_kern.o'
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_stream_afxdp_tx \
      realsrc/packetfs/network/pfs_stream_afxdp_tx.c \
      realsrc/packetfs/network/pfs_stream_afxdp_common.c \
      realsrc/packetfs/memory/pfs_hugeblob.c \
      realsrc/packetfs/gram/pfs_gram.c \
      -lxdp -lbpf -lelf -lz
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_stream_afxdp_rx \
      realsrc/packetfs/network/pfs_stream_afxdp_rx.c \
      realsrc/packetfs/network/pfs_stream_afxdp_common.c \
      realsrc/packetfs/memory/pfs_hugeblob.c \
      realsrc/packetfs/gram/pfs_gram.c \
      -lxdp -lbpf -lelf -lz

# Run AF_XDP TX/RX (requires root/capabilities and a NIC that supports XDP)
run-net-pfs-stream-afxdp-tx ifname="{{ifname}}" queue="0" blob_bytes="2147483648" seed="305419896" dpf="64" total="0" duration="10" align="64":
    @echo "Starting AF_XDP TX on {{ifname}} q{{queue}} for {{duration}}s"
    sudo dev/wip/native/pfs_stream_afxdp_tx --ifname {{ifname}} --queue {{queue}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-frame {{dpf}} --duration {{duration}} --align {{align}}

run-net-pfs-stream-afxdp-rx ifname="{{ifname}}" queue="0" blob_bytes="2147483648":
    @echo "Starting AF_XDP RX on {{ifname}} q{{queue}}"
    sudo dev/wip/native/pfs_stream_afxdp_rx --ifname {{ifname}} --queue {{queue}} --blob-size {{blob_bytes}}

# Run PacketFS-gram server/client (TCP)
run-net-pfs-gram-server port="8433" blob_bytes="1073741824" seed="305419896" dpg="16" grams="2048" max_len="65536" align="64":
    @echo "Starting PacketFS-gram server on port {{port}}"
    dev/wip/native/pfs_gram --mode server --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --gram-count {{grams}} --max-len {{max_len}} --align {{align}}

run-net-pfs-gram-client host="127.0.0.1" port="8433" blob_bytes="1073741824" seed="305419896" dpg="16" grams="2048" max_len="65536" align="64":
    @echo "Starting PacketFS-gram client to {{host}}:{{port}}"
    dev/wip/native/pfs_gram --mode client --host {{host}} --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --gram-count {{grams}} --max-len {{max_len}} --align {{align}}

# Run UDP PacketFS-gram server/client
run-net-pfs-gram-udp-server port="8533" blob_bytes="1073741824" seed="305419896" dpg="16" total="1073741824" gram_bytes="60000" align="64":
    @echo "Starting UDP PacketFS-gram server on port {{port}}"
    dev/wip/native/pfs_gram_udp --mode server --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --total-bytes {{total}} --gram-bytes {{gram_bytes}} --align {{align}}

run-net-pfs-gram-udp-client host="127.0.0.1" port="8533" blob_bytes="1073741824" seed="305419896" dpg="16" total="1073741824" gram_bytes="60000" align="64":
    @echo "Starting UDP PacketFS-gram client to {{host}}:{{port}}"
    dev/wip/native/pfs_gram_udp --mode client --host {{host}} --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --total-bytes {{total}} --gram-bytes {{gram_bytes}} --align {{align}}

# Build in-process ALU endpoints as a shared library
build-exec-lib:
    @echo "Building PacketFS in-process ALU library"
    mkdir -p bin
    {{CC}} -O3 -march=native -DNDEBUG -fPIC -shared -o bin/libpfs_exec.so dev/wip/native/packet_exec_lib.c

# Build native windowed batch benchmark (no Python)
build-bench-native:
    @echo "Building native windowed batch benchmark"
    mkdir -p bin
    {{CC}} -O3 -march=native -DNDEBUG -o bin/bench_exec dev/wip/native/bench_exec.c dev/wip/native/packet_exec_lib.c

# Build native blueprint reconstructor
build-blueprint-native:
    @echo "Building native blueprint reconstructor"
    {{CC}} -O3 -march=native -DNDEBUG -pthread -DHAVE_LIBNUMA -o dev/wip/native/blueprint_reconstruct dev/wip/native/blueprint_reconstruct.c -lnuma
    @echo "Built dev/wip/native/blueprint_reconstruct"

# Build only the LLVM IR parser CLI
build-llvm-parser:
    @echo "Building llvm_parser CLI"
    mkdir -p bin
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/llvm_parser dev/wip/native/llvm_parser.c dev/wip/native/llvm_cli.c

# Build CPU baseline benchmark
build-cpu-baseline:
    @echo "Building CPU baseline"
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/cpu_baseline dev/wip/native/cpu_baseline.c

# Run CPU baseline (multi-thread)
run-cpu-baseline:
    @echo "Running CPU baseline (100MB, threads=auto)"
    dev/wip/native/cpu_baseline --size-mb 100

# Run CPU baseline (single-thread dumb mode)
run-cpu-baseline-dumb:
    @echo "Running CPU baseline dumb (100MB, single-thread)"
    dev/wip/native/cpu_baseline --size-mb 100 --dumb

# Run Memory Monster loopback transfer (default 100MB)
run-memory-monster:
    @echo "Running Memory Monster (100MB, loopback)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/memory_monster.py --size-mb 100

# Run blueprint-only Memory Monster using VirtualBlob shared memory (100MB)
run-memory-monster-blueprint:
    @echo "Running Memory Monster (blueprint mode, 100MB, loopback, shared memory)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/memory_monster.py --blueprint --size-mb 100 --blob-size-mb 100 --blob-name pfs_vblob_test --base-units 262144 --seg-len 384 --stride 8191 --delta 0

# Run blueprint-only Memory Monster using native reconstructor (100MB)
run-memory-monster-blueprint-native:
    @echo "Running Memory Monster (blueprint mode, native reconstructor, 100MB)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/memory_monster.py --blueprint --size-mb 100 --blob-size-mb 100 --blob-name pfs_vblob_test --base-units 262144 --seg-len 384 --stride 8191 --delta 0 --native

# Sweep benchmark across pCPU and segment sizes
# Description:
#   Runs blueprint-only reconstruction locally using the native reconstructor and prints CSV:
#   mode,seg_len,pcpu,threads,batch,elapsed_s,MBps,pcpu_units_per_s,eff_ops_per_s,cpu_MBps,cpu_ops_per_s,ops_ratio
#   Defaults: size=400MB, threads=16, batch=16, huge pages hint on, pCPU=200k,800k,1.3M; seg=80,256,4096; includes scatter.
bench-blueprint-sweep:
    @echo "Running blueprint sweep (size=400MB, pCPU=200k,800k,1.3M; seg=80,256,4096; contig + scatter; ops/s vs CPU)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --threads 16 --batch 16 --hugehint --pcpu 200000,800000,1300000 --seg 80,256,4096 --include-scatter --ops-per-byte 1 --cpu-baseline --out logs/bp_sweep.csv

# Sweep with coalescing explicitly disabled
bench-blueprint-sweep-nocoalesce:
    @echo "Running blueprint sweep (no coalesce)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --threads 16 --batch 16 --hugehint --pcpu 200000,800000,1300000 --seg 80,256,4096 --include-scatter --ops-per-byte 1 --cpu-baseline --no-coalesce --out logs/bp_sweep_nocoalesce.csv

# Parameterized sweep (override defaults without editing files)
# Usage example:
#   just bench-blueprint-sweep-custom 800 100 "400000,1300000,2600000" "80,256" 32 8 auto false true 2
#   meaning: size_mb=800, blob=100MB, pcpu list, seg list, threads=32, batch=8, numa=auto, interleave=false, hugehint=true, ops-per-byte=2
bench-blueprint-sweep-custom size_mb="400" blob_mb="100" pcpu="200000,800000,1300000" seg="80,256,4096" threads="16" batch="16" numa="auto" opspb="1" extra_flags="--hugehint --include-scatter --cpu-baseline":
    @echo "Blueprint sweep custom: size={{size_mb}}MB, blob={{blob_mb}}MB, pcpu={{pcpu}}, seg={{seg}}, threads={{threads}}, batch={{batch}}, numa={{numa}}, ops/byte={{opspb}}"
    @echo "Extra flags: {{extra_flags}} (e.g., --numa-interleave, --ops-per-byte 2, --cpu-baseline, --hugehint, --include-scatter)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py --size-mb {{size_mb}} --blob-size-mb {{blob_mb}} --blob-name pfs_vblob_test --threads {{threads}} --batch {{batch}} --pcpu {{pcpu}} --seg {{seg}} --numa {{numa}} --ops-per-byte {{opspb}} {{extra_flags}}

# Pass raw extra flags to sweep (ultimate flexibility)
# Usage: just bench-blueprint-sweep-args "--size-mb 800 --threads 32 --batch 8 --pcpu 400000,1300000 --seg 80,256 --ops-per-byte 2 --cpu-baseline --hugehint --include-scatter"
bench-blueprint-sweep-args flags="":
    @echo "Running blueprint sweep with extra flags: {{flags}}"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py {{flags}}

# Save + report convenience
bench-blueprint-report:
    @echo "Generating report from logs/bp_sweep.csv"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_sweep.csv --top 10

# Max-win search across combos (contig/scatter, pCPU list, seg list, threads, batch)
# Example: just bench-blueprint-maxwin (defaults: size=400MB, pCPU=200k..2.6M, seg=80,256,4096, threads=8,16,32, batch=8,16,32, ops/byte=1)
bench-blueprint-maxwin:
    @echo "Max-win sweep (size=400MB, broad grid, CPU baseline multi-thread)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --out logs/bp_maxwin.csv
    @echo "Report top wins (ops_ratio >= 1.0 likely in contig 80B range)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin.csv --top 15

# Max-win with coalescing off
bench-blueprint-maxwin-nocoalesce:
    @echo "Max-win sweep (no coalesce, broad grid)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --no-coalesce --out logs/bp_maxwin_nocoalesce.csv
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin_nocoalesce.csv --top 15

# Max-win with dumb CPU baseline (single-threaded)
bench-blueprint-maxwin-dumbcpu:
    @echo "Max-win sweep (CPU baseline single-thread dumb for comparison)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --cpu-dumb --out logs/bp_maxwin_dumbcpu.csv
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin_dumbcpu.csv --top 15

# Fast contiguous profile (handy defaults to lean into winning conditions)
#  - size=400MB, seg=80, pCPU=200k, coalescing on, hugehint on, CPU baseline
bench-blueprint-fast-contig:
    @echo "Fast contiguous profile (size=400MB, seg=80, pCPU=200k, threads=16, batch=16, ops/byte=1)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --threads 16 --batch 16 --pcpu 200000 --seg 80 --numa auto --hugehint --ops-per-byte 1 --cpu-baseline --out logs/bp_fast_contig.csv
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_fast_contig.csv --top 5

# Unit test for blueprint reconstruction
test-blueprint:
    @echo "Running blueprint reconstruction unit tests"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python -m pytest -q dev/working/tests/test_blueprint_transfer.py

# Build IR sample (requires clang)
build-ir-sample:
    @echo "Building IR sample (add4)"
    test -x "$(which clang)" || (echo "clang not found" && exit 1)
    clang -O3 dev/working/samples/add4.c -o dev/wip/samples/add4
    clang -O3 -S -emit-llvm dev/working/samples/add4.c -o dev/wip/samples/add4.ll

# Run IR execution pipeline test
test-ir-exec:
    @echo "Running IR execution pipeline tests"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python -m pytest -q dev/working/tests/test_ir_exec_pipeline.py

# Run the production IR executor CLI on a .ll file
run-ir-exec ll="dev/working/samples/llvm/compute/hello_world.ll" windows="1" mode="both":
    @echo "Running IR executor on {{ll}} (mode={{mode}}, windows={{windows}})"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/ir_exec.py {{ll}} --mode {{mode}} {{if windows == '1'}}--windows{{endif}}

# === Whole-program LLVM bitcode pipeline (freestanding, no libc) ===
# 1) Compile sources to .bc (freestanding, no builtins)
build-bc:
    @echo "Compiling to LLVM bitcode (.bc)"
    test -x "$(which {{CLANG}})" || (echo "clang not found" && exit 1)
    mkdir -p {{BC_DIR}}
    {{CLANG}} -O3 -ffreestanding -fno-builtin -emit-llvm -c dev/working/samples/add4.c -o {{BC_DIR}}/add4.bc

# 2) Link into a single module
link-bc:
    @echo "Linking bitcode modules"
    mkdir -p {{BC_DIR}}
    sh -c 'if command -v {{LLVMLINK}} >/dev/null 2>&1; then \
      {{LLVMLINK}} {{BC_DIR}}/*.bc -o {{BC_DIR}}/program.bc; \
    else \
      cnt=$(ls -1 {{BC_DIR}}/*.bc 2>/dev/null | wc -l); \
      if [ "$cnt" -eq 1 ]; then \
        cp $(ls {{BC_DIR}}/*.bc) {{BC_DIR}}/program.bc; \
      else \
        echo "llvm-link not found and multiple .bc present"; exit 1; \
      fi; \
    fi'

# 3) Optimize and emit textual IR
opt-bc:
    @echo "Optimizing bitcode and emitting textual IR"
    sh -c 'optbin=$(command -v {{OPT}} || command -v opt-18 || command -v opt-17 || command -v opt-16); \
      disbin=$(command -v {{LLVMDIS}} || command -v llvm-dis-18 || command -v llvm-dis-17 || command -v llvm-dis-16); \
      if [ -z "$optbin" ]; then echo "opt not found"; exit 1; fi; \
      if [ -z "$disbin" ]; then echo "llvm-dis not found"; exit 1; fi; \
      "$optbin" -O3 {{BC_DIR}}/program.bc -o {{BC_DIR}}/program.opt.bc && \
      "$disbin" {{BC_DIR}}/program.opt.bc -o {{BC_DIR}}/program.opt.ll'

# 4) Verify no undefined symbols remain
verify-bc:
    @echo "Verifying no undefined symbols in optimized bitcode"
    sh -c 'nmbin=$(command -v {{LLVMNM}} || command -v llvm-nm-18 || command -v llvm-nm-17 || command -v llvm-nm-16); \
      if [ -z "$nmbin" ]; then echo "llvm-nm not found"; exit 1; fi; \
      "$nmbin" --undefined-only {{BC_DIR}}/program.opt.bc > {{BC_DIR}}/undefined.txt; \
      test ! -s {{BC_DIR}}/undefined.txt || (echo "Undefined symbols remain:" && cat {{BC_DIR}}/undefined.txt && exit 1)'
