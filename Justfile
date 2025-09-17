# PacketFS root orchestrator (single-target steps, no inline chaining)

# Import split justfiles (network, builds, tests, cleanup, dev) if present

# (Variables imported from Justfile.vars)

# Standard targets

# Log management
# - dev-logs-index: summarize latest pattern/plan runs into reports/
# - dev-logs-archive: move old runs under logs/archive/<YYYY-MM>/ (dry-run by default)

default: help
    @:

help:
    @echo "Usage: just <recipe>. Categories: tests, dev-builds, staging/prod builds, experimental, env"
    just --list
    @echo ""
    @echo "Merge service (Podman):"
    @echo "  just dev-build-pfs-merge      # Build Podman image"
    @echo "  just dev-run-pfs-merge        # Run local service container"
    @echo "  just dev-merge <peer>         # Connect to peer (host shell)"
    @echo "  just dev-stop-pfs-merge       # Stop container"

# No-op alias to absorb accidental invocations like `just just build`
just:
    @echo "Tip: Use 'just <recipe>'. Ignoring stray 'just'."

setup:
    @echo "Setting up PacketFS dev environment"
    {{VENV_PATH}}/bin/python -m pip install -q -U pip setuptools wheel
    @echo "Done"

build:
    @echo "Build: compile native extensions if packaging is configured"
    @echo "(skipping: provide setup.py/pyproject to enable)"

# Run full working tests
test:
    @echo "Running production unit tests (src/)"
    {{VENV_PATH}}/bin/python -m pytest -q tests

test-dev:
    @echo "Running dev/prototype tests (PYTHONPATH={{PKG_PYTHONPATH}})"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python -m pytest -q dev/working/tests

lint:
    @echo "Linting"
    {{VENV_PATH}}/bin/python -m black --check src realsrc dev/working/tools
    {{VENV_PATH}}/bin/python -m flake8 src realsrc dev/working/tools

format:
    @echo "Formatting"
    {{VENV_PATH}}/bin/python -m black src realsrc dev/working/tools

ci:
    @echo "CI: lint then production tests"
    {{VENV_PATH}}/bin/python -m black --check src realsrc dev/working/tools
    {{VENV_PATH}}/bin/python -m flake8 src realsrc dev/working/tools
    {{VENV_PATH}}/bin/python -m pytest -q tests

bench:
    @echo "Benchmarks"
    {{VENV_PATH}}/bin/python dev/working/tools/perf_benchmark.py

# pCPU sweep (threads x batch x reps)
bench-pcpu-sweep:
    @echo "Running pCPU sweep -> logs/pcpu_sweep.csv"
    {{VENV_PATH}}/bin/python dev/working/tools/pcpu_sweep.py

bench-dpdk-pcpu-sweep:
    @echo "Running DPDK pCPU veth sweep -> logs/dpdk_pcpu_sweep_<ts>.csv"
    {{VENV_PATH}}/bin/python dev/working/tools/dpdk_pcpu_sweep.py

bench-shm-pcpu-sweep:
    @echo "Running SHM pCPU arithmetic sweep -> logs/shm_pcpu_sweep_<ts>.csv"
    {{VENV_PATH}}/bin/python dev/working/tools/shm_pcpu_sweep.py

# IR quicksort windows sweep (window_pow2 variants)
bench-ir-windows-sweep:
    @echo "Running IR quicksort windows sweep -> logs/ir_quicksort_windows.csv"
    {{VENV_PATH}}/bin/python dev/working/tools/ir_windows_sweep.py

# Build shared-memory ring bench only
build-shm-ring:
    @echo "Building shared-memory SPSC ring bench"
    {{CC}} -O3 -march=native -DNDEBUG -pthread -Irealsrc/packetfs -o dev/wip/native/pfs_shm_ring_bench \
      src/dev/wip/native/pfs_shm_ring_bench.c \
      realsrc/packetfs/ring/pfs_shm_ring.c \
      realsrc/packetfs/memory/pfs_hugeblob.c \
      realsrc/packetfs/pcpu/pfs_pcpu.c

# Run shared-memory ring bench (positional args)
# usage: just run-shm-ring-bench BLOB_BYTES DPF RING_POW2 ALIGN DURATION_S THREADS
run-shm-ring-bench blob_bytes="2147483648" dpf="64" ring_pow2="16" align="64" duration="5" threads="2" pcpu_threads="1" arith="0" pcpu="0" op="fnv" imm="0" ports="1" queues="1" mode="scatter" seg_len="80" reuse="0":
    @echo "Running SHM ring bench (blob={{blob_bytes}} dpf={{dpf}} ring=2^{{ring_pow2}} align={{align}} dur={{duration}}s threads={{threads}} cthreads={{pcpu_threads}} arith={{arith}} pcpu={{pcpu}} op={{op}} imm={{imm}} ports={{ports}} queues={{queues}} mode={{mode}} seg={{seg_len}} reuse={{reuse}})"
    taskset -c 0-3 dev/wip/native/pfs_shm_ring_bench --blob-size {{blob_bytes}} --dpf {{dpf}} --ring-pow2 {{ring_pow2}} --align {{align}} --duration {{duration}} --threads {{threads}} --pcpu-threads {{pcpu_threads}} --arith {{arith}} --vstream 0 --payload 2048 --huge-dir /mnt/huge1G --pcpu {{pcpu}} --pcpu-op {{op}} --imm {{imm}} --ports {{ports}} --queues {{queues}} --mode {{mode}} --seg-len {{seg_len}} --reuse-frames {{reuse}}

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
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_windows_core.py 8388608 16 60

clean:
    @echo "Cleaning work artifacts"
    find . -name "__pycache__" -type d -prune -exec rm -rf {} +
    find . -name "*.pyc" -delete
    @echo "Note: containers are not removed here; use dev-stop-pfs-merge to stop the merge container"
    @echo "Cleaning bin symlinks"
    find bin -maxdepth 1 -type l -delete 2>/dev/null || true

# Build and install the C extension into the central venv, then fix ownership
build-bitpack:
    @echo "Building packetfs._bitpack C extension"
    {{VENV_PATH}}/bin/python -m pip install -U pip setuptools wheel
    {{VENV_PATH}}/bin/python -m pip install -e .
    {{VENV_PATH}}/bin/python -c "import packetfs._bitpack; print('bitpack import OK')"
    chown -R punk:punk {{VENV_PATH}}

# Packaging / install (staging/prod)
build-wheel:
    @echo "Building wheel"
    {{VENV_PATH}}/bin/python -m pip install -U build
    {{VENV_PATH}}/bin/python -m build -w

install:
    @echo "Editable install from realsrc/"
    {{VENV_PATH}}/bin/python -m pip install -e .

# Encode files into PacketFS arithmetic (PROTO ops per window)
arith-encode file="" out="" window="65536":
    @bash -eu -o pipefail -c '
    if [ -z "{{file}}" ]; then echo "usage: just arith-encode file=PATH [out=PATH] [window=65536]" >&2; exit 2; fi; \
    if [ -x "{{VENV_PATH}}/bin/pfs-arith-encode" ]; then \
      {{VENV_PATH}}/bin/pfs-arith-encode --window {{window}} ${out:+--out "{{out}}"} "{{file}}"; \
    else \
      PYTHONPATH=realsrc {{VENV_PATH}}/bin/python -m packetfs.tools.arith_encode --window {{window}} ${out:+--out "{{out}}"} "{{file}}"; \
    fi'

# Translation daemon: ingest files into blob and emit IPROG
trans-daemon watch_dir="./ingest" out_dir="./iprog" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337" window="65536" meta_dir="./pfsmeta":
    @bash -eu -o pipefail -c '
    mkdir -p "{{watch_dir}}" "{{out_dir}}" "{{meta_dir}}"; \
    if [ -x "{{VENV_PATH}}/bin/pfs-translate-daemon" ]; then \
      {{VENV_PATH}}/bin/pfs-translate-daemon --watch-dir "{{watch_dir}}" --out-dir "{{out_dir}}" --blob-name "{{blob_name}}" --blob-size "{{blob_size}}" --blob-seed "{{blob_seed}}" --meta-dir "{{meta_dir}}" --window "{{window}}"; \
    else \
      PYTHONPATH=realsrc {{VENV_PATH}}/bin/python -m packetfs.tools.translate_daemon --watch-dir "{{watch_dir}}" --out-dir "{{out_dir}}" --blob-name "{{blob_name}}" --blob-size "{{blob_size}}" --blob-seed "{{blob_seed}}" --meta-dir "{{meta_dir}}" --window "{{window}}"; \
    fi'

# Send an IPROG plan over WebSocket to a receiver
arith-send iprog="" host="127.0.0.1" port="8088":
    @bash -eu -o pipefail -c '
    if [ -z "{{iprog}}" ]; then echo "usage: just arith-send iprog=PATH [host=H port=P]" >&2; exit 2; fi; \
    if [ -x "{{VENV_PATH}}/bin/pfs-arith-send" ]; then \
      {{VENV_PATH}}/bin/pfs-arith-send --iprog "{{iprog}}" --host "{{host}}" --port "{{port}}"; \
    else \
      PYTHONPATH=realsrc {{VENV_PATH}}/bin/python -m packetfs.tools.arith_send --iprog "{{iprog}}" --host "{{host}}" --port "{{port}}"; \
    fi'

# FUSE filesystem: mount IPROG views as regular files (read-write by default)
pfsfs-mount mnt="./pfs.mnt" iprog_dir="./iprog" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337" window="65536" embed_pvrt="1" meta_dir="./pfsmeta":
    @bash -eu -o pipefail -c '
    mkdir -p "{{mnt}}"; \
    if [ -x "{{VENV_PATH}}/bin/pfsfs-mount" ]; then \
      {{VENV_PATH}}/bin/pfsfs-mount --iprog-dir "{{iprog_dir}}" --mount "{{mnt}}" --blob-name "{{blob_name}}" --blob-size "{{blob_size}}" --blob-seed "{{blob_seed}}" --meta-dir "{{meta_dir}}" --window "{{window}}" ${embed_pvrt:+--embed-pvrt} --foreground; \
    else \
      PYTHONPATH=realsrc {{VENV_PATH}}/bin/python -m packetfs.filesystem.pfsfs_mount --iprog-dir "{{iprog_dir}}" --mount "{{mnt}}" --blob-name "{{blob_name}}" --blob-size "{{blob_size}}" --blob-seed "{{blob_seed}}" --meta-dir "{{meta_dir}}" --window "{{window}}" ${embed_pvrt:+--embed-pvrt} --foreground; \
    fi'

# Read-only mount variant
pfsfs-mount-ro mnt="./pfs.mnt" iprog_dir="./iprog" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337" window="65536" meta_dir="./pfsmeta":
    @bash -eu -o pipefail -c '
    mkdir -p "{{mnt}}"; \
    if [ -x "{{VENV_PATH}}/bin/pfsfs-mount" ]; then \
      {{VENV_PATH}}/bin/pfsfs-mount --iprog-dir "{{iprog_dir}}" --mount "{{mnt}}" --blob-name "{{blob_name}}" --blob-size "{{blob_size}}" --blob-seed "{{blob_seed}}" --meta-dir "{{meta_dir}}" --window "{{window}}" --read-only --foreground; \
    else \
      PYTHONPATH=realsrc {{VENV_PATH}}/bin/python -m packetfs.filesystem.pfsfs_mount --iprog-dir "{{iprog_dir}}" --mount "{{mnt}}" --blob-name "{{blob_name}}" --blob-size "{{blob_size}}" --blob-seed "{{blob_seed}}" --meta-dir "{{meta_dir}}" --window "{{window}}" --read-only --foreground; \
    fi'

pfsfs-umount mnt="./pfs.mnt":
    @bash -eu -o pipefail -c 'fusermount -u "{{mnt}}" 2>/dev/null || sudo umount "{{mnt}}" 2>/dev/null || true'

uninstall:
    @echo "Uninstalling packetfs"
    -{{VENV_PATH}}/bin/python -m pip uninstall -y packetfs || true

reinstall:
    @echo "Reinstalling packetfs"
    -{{VENV_PATH}}/bin/python -m pip uninstall -y packetfs || true
    {{VENV_PATH}}/bin/python -m pip install -e .

# Build WIP native tools into bin/
build-wip-native:
    @echo "Building WIP native executables"
    mkdir -p bin
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/memory_executor dev/wip/native/memory_executor.c
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/micro_executor dev/wip/native/micro_executor.c
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/swarm_coordinator dev/wip/native/swarm_coordinator.c
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/llvm_parser dev/wip/native/llvm_parser.c dev/wip/native/llvm_cli.c
    {{CC}} -O3 -march=native -DNDEBUG -pthread -Irealsrc/packetfs -o dev/wip/native/pfs_shm_ring_bench \
      src/dev/wip/native/pfs_shm_ring_bench.c \
      realsrc/packetfs/ring/pfs_shm_ring.c \
      realsrc/packetfs/memory/pfs_hugeblob.c \
      realsrc/packetfs/pcpu/pfs_pcpu.c

# Build async network saturator tools (real source under realsrc)
build-net-async:
    @echo "Building AF_PACKET RX harness (dev/working/tools) and PacketFS async TX/RX"
    mkdir -p dev/wip/native bin
    make -C dev/working/tools pfs_afpkt_rx
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_async_tx realsrc/packetfs/network/pfs_async_tx.c
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_async_rx realsrc/packetfs/network/pfs_async_rx.c
    @# Symlink/organize common binaries into bin/
    ln -sf ../dev/wip/native/pfs_gram bin/pfs_gram 2>/dev/null || true
    ln -sf ../dev/wip/native/pfs_gram_udp bin/pfs_gram_udp 2>/dev/null || true
    ln -sf ../dev/wip/native/pfs_stream_afxdp_tx bin/pfs_stream_afxdp_tx 2>/dev/null || true
    ln -sf ../dev/wip/native/pfs_stream_afxdp_rx bin/pfs_stream_afxdp_rx 2>/dev/null || true
    ln -sf ../dev/wip/native/pfs_stream_dpdk_tx bin/pfs_stream_dpdk_tx 2>/dev/null || true
    ln -sf ../dev/wip/native/pfs_stream_dpdk_rx bin/pfs_stream_dpdk_rx 2>/dev/null || true
    ln -sf ../dev/wip/native/pfs_shm_ring_bench bin/pfs_shm_ring_bench 2>/dev/null || true
    ln -sf ../dev/working/tools/pfs_afpkt_rx bin/pfs_afpkt_rx 2>/dev/null || true

# Grant CAP_NET_RAW to AF_PACKET RX so it can run without sudo (one-time)
net-afpkt-cap:
    @echo "Granting CAP_NET_RAW to bin/pfs_afpkt_rx (requires sudo)"
    @# Try bin path first, then fallback to dev path if symlink not present
    sudo -n setcap cap_net_raw+ep bin/pfs_afpkt_rx || sudo -n setcap cap_net_raw+ep dev/working/tools/pfs_afpkt_rx

# AF_PACKET RX smoke test on loopback, pinned to a single CPU (no multicore)
# Defaults: 2s, CPU 0, plan to logs/plan_afpkt_smoke.json, hint network/crc
run-net-afpkt-smoke duration="2" cpu="0" plan="logs/plan_afpkt_smoke.json" hint="network/crc" snaplen="64" align="64":
    @echo "[smoke] AF_PACKET RX on lo for {{duration}}s pinned to CPU {{cpu}}. If you see 'Operation not permitted', run: just net-afpkt-cap"
    just build-net-async
    mkdir -p logs
    taskset -c {{cpu}} bin/pfs_afpkt_rx --iface lo --duration {{duration}} --blob-size $((64<<20)) \
      --huge-dir /dev/hugepages --llvm-opt 1 --llvm-hint "{{hint}}" --peek-mmio 1 \
      --plan-out "{{plan}}" --snaplen {{snaplen}} --align {{align}} --pin-cpu-list "{{cpu}}"

# Show capability status quickly
net-afpkt-cap-status:
    @echo "Capability status for bin/pfs_afpkt_rx:"
    @getcap bin/pfs_afpkt_rx || true
    @echo "Real binary (if symlink):"
    @ls -l bin/pfs_afpkt_rx || true
    @getcap dev/working/tools/pfs_afpkt_rx || true

# Run AF_PACKET RX on a specified interface, pinned to a CPU, with plan path
run-net-afpkt-iface iface="enp130s0" duration="5" cpu="0" plan="logs/plan_afpkt_iface.json" hint="network/crc" snaplen="64" align="64":
    @echo "[run] iface={{iface}} duration={{duration}}s pinned CPU {{cpu}}"
    just build-net-async
    mkdir -p logs
    taskset -c {{cpu}} bin/pfs_afpkt_rx --iface "{{iface}}" --duration {{duration}} --blob-size $((256<<20)) \
      --huge-dir /dev/hugepages --llvm-opt 1 --llvm-hint "{{hint}}" --peek-mmio 1 \
      --plan-out "{{plan}}" --snaplen {{snaplen}} --align {{align}} --pin-cpu-list "{{cpu}}"

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

# Aliases using current terminology (kept separate to avoid recipe chaining)
build-pfs-tcp:
    @echo "Building PFS-TCP (alias of PacketFS-gram TCP)"
    mkdir -p dev/wip/native
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_gram \
      realsrc/packetfs/network/pfs_gram_proto.c \
      realsrc/packetfs/memory/pfs_hugeblob.c \
      realsrc/packetfs/gram/pfs_gram.c

build-pfs-udp:
    @echo "Building PFS-UDP (alias of PacketFS-gram UDP)"
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
      realsrc/packetfs/pcpu/pfs_pcpu.c \
      -lxdp -lbpf -lelf -lz

# Build DPDK streaming executables (varint streaming, INIT+hash, same CLI shape)
build-net-pfs-stream-dpdk:
    @echo "Building PacketFS DPDK streaming TX/RX"
    mkdir -p dev/wip/native
    @bash -eu -o pipefail -c ' \
      cflags=$(pkg-config --cflags libdpdk 2>/dev/null || pkgconf --cflags libdpdk 2>/dev/null || true); \
      libs=$(pkg-config --libs libdpdk 2>/dev/null || pkgconf --libs libdpdk 2>/dev/null || true); \
      if [ -z "$libs" ]; then echo "DPDK dev not found (libdpdk). On Ubuntu: sudo apt-get install -y dpdk libdpdk-dev"; exit 1; fi; \
      echo "Using DPDK libs: $libs"; \
      {{CC}} -O3 -march=native -DNDEBUG -pthread -Irealsrc/packetfs $cflags -o dev/wip/native/pfs_stream_dpdk_tx \
        realsrc/packetfs/network/pfs_stream_dpdk_tx.c \
        realsrc/packetfs/memory/pfs_hugeblob.c \
        realsrc/packetfs/gram/pfs_gram.c \
        $libs; \
      {{CC}} -O3 -march=native -DNDEBUG -pthread -Irealsrc/packetfs $cflags -o dev/wip/native/pfs_stream_dpdk_rx \
        realsrc/packetfs/network/pfs_stream_dpdk_rx.c \
        realsrc/packetfs/memory/pfs_hugeblob.c \
        realsrc/packetfs/gram/pfs_gram.c \
        realsrc/packetfs/pcpu/pfs_pcpu.c \
        $libs'

# Build AF_PACKET streaming tools (fixed-size frames, arithmetic mode)
build-net-pfs-stream-afpacket:
    @echo "Building PacketFS AF_PACKET TX/RX"
    mkdir -p dev/wip/native
    {{CC}} -O3 -march=native -DNDEBUG -pthread -Irealsrc/packetfs \
      -o dev/wip/native/pfs_stream_afpacket_tx \
      realsrc/packetfs/network/pfs_stream_afpacket_tx.c \
      realsrc/packetfs/memory/pfs_hugeblob.c
    {{CC}} -O3 -march=native -DNDEBUG -pthread -Irealsrc/packetfs \
      -o dev/wip/native/pfs_stream_afpacket_rx \
      realsrc/packetfs/network/pfs_stream_afpacket_rx.c \
      realsrc/packetfs/memory/pfs_hugeblob.c

# Run AF_PACKET TX/RX (PCIe NIC recommended)
dev-run-pfs-stream-afpacket-tx ifname="enp130s0" dst="ff:ff:ff:ff:ff:ff" frame="4096" duration="10" cpu="auto" pcpu_op="fnv" imm="0":
    @bash -eu -o pipefail -c '
    IF="{{ifname}}"; CPU="{{cpu}}"; if [ "$CPU" = "auto" ]; then CPU=$(bash scripts/choose_cpu_for_iface.sh "$IF"); fi; \
    echo "[pin] IF=$IF -> CPU=$CPU"; \
    taskset -c "$CPU" sudo -n dev/wip/native/pfs_stream_afpacket_tx --ifname "$IF" --dst "{{dst}}" --frame-size "{{frame}}" --duration "{{duration}}" --cpu "$CPU" --pcpu-op "{{pcpu_op}}" --imm "{{imm}}"'

dev-run-pfs-stream-afpacket-rx ifname="enp130s0" frame="4096" duration="10" cpu="auto" pcpu_op="fnv" imm="0":
    @bash -eu -o pipefail -c '
    IF="{{ifname}}"; CPU="{{cpu}}"; if [ "$CPU" = "auto" ]; then CPU=$(bash scripts/choose_cpu_for_iface.sh "$IF"); fi; \
    echo "[pin] IF=$IF -> CPU=$CPU"; \
    taskset -c "$CPU" sudo -n dev/wip/native/pfs_stream_afpacket_rx --ifname "$IF" --frame-size "{{frame}}" --duration "{{duration}}" --cpu "$CPU" --pcpu-op "{{pcpu_op}}" --imm "{{imm}}"'

# Sweep AF_PACKET RX+TX across frames/ops/imm with CPU auto-pinning
sweep-afpacket ifname="enp130s0" frames="1024,4096" ops="fnv,crc32c,counteq" imm="0,255" duration="3" cpu="auto" dst="ff:ff:ff:ff:ff:ff":
    scripts/sweep_afpacket.sh {{ifname}} {{frames}} {{ops}} {{imm}} {{duration}} {{cpu}} {{dst}}

# Grant CAP_NET_RAW to AF_PACKET RX to allow running without sudo
cap-net-afpkt:
    @echo "Granting CAP_NET_RAW to dev/working/tools/pfs_afpkt_rx"
    sudo setcap cap_net_raw+ep dev/working/tools/pfs_afpkt_rx

# Kernel MMIO peek (Realtek 8168/8169)
build-rtl-peek:
    @echo "Building rtl_peek_mmio in dev/kernel/rtl_peek_mmio"
    $(MAKE) -C dev/kernel/rtl_peek_mmio
    mkdir -p bin
    ln -sf ../dev/kernel/rtl_peek_mmio/rtl_peek_mmio bin/rtl_peek_mmio

run-rtl-peek bdf="0000:82:00.0":
    @echo "Running rtl_peek_mmio on BDF={{bdf}} (sudo needed for /dev/mem fallback)"
    sudo -n dev/kernel/rtl_peek_mmio/rtl_peek_mmio {{bdf}}

# Run AF_XDP TX/RX (requires root/capabilities and a NIC that supports XDP)
# Note: lo (loopback) typically does not support XDP. Use a physical NIC (e.g., enp3s0, eth0).
run-net-pfs-stream-afxdp-tx ifname="" queue="0" blob_bytes="2147483648" seed="305419896" dpf="64" total="0" duration="10" align="64" zc="1" mode="auto" arith="1" vstream="1" streams="4" cpu="auto":
    @bash -eu -o pipefail -c '
    IF="{{ifname}}"; CPU="{{cpu}}"; if [ "$CPU" = "auto" ]; then CPU=$(bash scripts/choose_cpu_for_iface.sh "$IF"); fi; \
    echo "[pin] IF=$IF -> CPU=$CPU"; \
    taskset -c "$CPU" sudo dev/wip/native/pfs_stream_afxdp_tx --ifname "$IF" --queue "{{queue}}" --blob-size "{{blob_bytes}}" --seed "{{seed}}" --desc-per-frame "{{dpf}}" --duration "{{duration}}" --align "{{align}}" --zerocopy "{{zc}}" --mode "{{mode}}" --arith "{{arith}}" --vstream "{{vstream}}" --streams "{{streams}}"'

# Sweep streams over powers of two up to 128
sweep-afxdp-streams ifname="" queue="0" blob_bytes="2147483648" seed="305419896" duration="10" align="64" zc="1" mode="auto" arith="1" vstream="1" cpu="auto":
    @bash -eu -o pipefail -c '
    IF="{{ifname}}"; CPU="{{cpu}}"; if [ "$CPU" = "auto" ]; then CPU=$(bash scripts/choose_cpu_for_iface.sh "$IF"); fi; \
    echo "[pin] IF=$IF -> CPU=$CPU"; \
    for s in 1 2 4 8 16 32 64 128; do \
      echo "\n=== STREAMS=$s ==="; \
      taskset -c "$CPU" sudo dev/wip/native/pfs_stream_afxdp_tx --ifname "$IF" --queue "{{queue}}" --blob-size "{{blob_bytes}}" --seed "{{seed}}" --desc-per-frame 64 --duration "{{duration}}" --align "{{align}}" --zerocopy "{{zc}}" --mode "{{mode}}" --arith "{{arith}}" --vstream "{{vstream}}" --streams "$s"; \
    done'

run-net-pfs-stream-afxdp-rx ifname="" queue="0" blob_bytes="2147483648" zc="1" mode="auto" cpu="auto":
    @bash -eu -o pipefail -c '
    IF="{{ifname}}"; CPU="{{cpu}}"; if [ "$CPU" = "auto" ]; then CPU=$(bash scripts/choose_cpu_for_iface.sh "$IF"); fi; \
    echo "[pin] IF=$IF -> CPU=$CPU"; \
    taskset -c "$CPU" sudo dev/wip/native/pfs_stream_afxdp_rx --ifname "$IF" --queue "{{queue}}" --blob-size "{{blob_bytes}}" --zerocopy "{{zc}}" --mode "{{mode}}"'

# Run DPDK TX/RX (requires DPDK dev + a bound port)
run-net-pfs-stream-dpdk-tx ports="0" pcis="" txq="1" eal="-l 0 -n 4" blob_bytes="2147483648" seed="305419896" dpf="64" duration="10" align="64" arith="1" vstream="1" streams="4":
    @echo "Starting DPDK TX on ports={{ports}} pcis={{pcis}} txq={{txq}} eal='{{eal}}' for {{duration}}s (arith={{arith}} vstream={{vstream}} streams={{streams}})"
    sudo dev/wip/native/pfs_stream_dpdk_tx --ports "{{ports}}" --pcis "{{pcis}}" --tx-queues {{txq}} --eal "{{eal}}" --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-frame {{dpf}} --duration {{duration}} --align {{align}} --arith {{arith}} --vstream {{vstream}} --streams {{streams}}

# Header-enabled convenience wrappers (non-interactive sudo)
run-net-pfs-stream-dpdk-tx-eth ports="0" pcis="" txq="1" eal="-l 0 -n 4" blob_bytes="2147483648" seed="305419896" dpf="64" duration="10" align="64" arith="1" vstream="1" streams="4":
    @echo "Starting DPDK TX (eth+proto-hdr) on ports={{ports}} pcis={{pcis}} txq={{txq}} eal='{{eal}}' for {{duration}}s"
    sudo -n dev/wip/native/pfs_stream_dpdk_tx --ports "{{ports}}" --pcis "{{pcis}}" --tx-queues {{txq}} --eal "{{eal}}" --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-frame {{dpf}} --duration {{duration}} --align {{align}} --arith {{arith}} --vstream {{vstream}} --streams {{streams}} --eth 1 --proto-hdr 1

run-net-pfs-stream-dpdk-rx ports="0" pcis="" rxq="1" eal="-l 1 -n 4" blob_bytes="2147483648":
    @echo "Starting DPDK RX on ports={{ports}} pcis={{pcis}} rxq={{rxq}} eal='{{eal}}'"
    sudo dev/wip/native/pfs_stream_dpdk_rx --ports "{{ports}}" --pcis "{{pcis}}" --rx-queues {{rxq}} --eal "{{eal}}" --blob-size {{blob_bytes}}

run-net-pfs-stream-dpdk-rx-l2 ports="0" pcis="" rxq="1" eal="-l 1 -n 4" blob_bytes="2147483648" l2="14" pcpu="1" op="fnv" imm="0":
    @echo "Starting DPDK RX (l2-skip={{l2}} pcpu={{pcpu}} op={{op}} imm={{imm}}) on ports={{ports}} pcis={{pcis}} rxq={{rxq}} eal='{{eal}}'"
    sudo -n dev/wip/native/pfs_stream_dpdk_rx --ports "{{ports}}" --pcis "{{pcis}}" --rx-queues {{rxq}} --eal "{{eal}}" --blob-size {{blob_bytes}} --l2-skip {{l2}} --pcpu {{pcpu}} --pcpu-op {{op}} --imm {{imm}}

# Sweep streams (DPDK TX), powers of two up to 128
sweep-dpdk-streams ports="0" pcis="" txq="1" eal="-l 0 -n 4" blob_bytes="2147483648" seed="305419896" duration="10" align="64" arith="1" vstream="1":
    @bash -eu -o pipefail -c '
    for s in 1 2 4 8 16 32 64 128; do \
      echo "\n=== STREAMS=$s ==="; \
      sudo dev/wip/native/pfs_stream_dpdk_tx --ports "{{ports}}" --pcis "{{pcis}}" --tx-queues {{txq}} --eal "{{eal}}" --blob-size "{{blob_bytes}}" --seed "{{seed}}" --desc-per-frame 64 --duration "{{duration}}" --align "{{align}}" --arith "{{arith}}" --vstream "{{vstream}}" --streams "$s"; \
    done'

# Run PacketFS-gram server/client (TCP)
run-net-pfs-gram-server port="8433" blob_bytes="1073741824" seed="305419896" dpg="16" grams="2048" max_len="65536" align="64":
    @echo "Starting PacketFS-gram server on port {{port}}"
    dev/wip/native/pfs_gram --mode server --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --gram-count {{grams}} --max-len {{max_len}} --align {{align}}

run-net-pfs-gram-client host="127.0.0.1" port="8433" blob_bytes="1073741824" seed="305419896" dpg="16" grams="2048" max_len="65536" align="64":
    @echo "Starting PacketFS-gram client to {{host}}:{{port}}"
    dev/wip/native/pfs_gram --mode client --host {{host}} --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --gram-count {{grams}} --max-len {{max_len}} --align {{align}}

# Aliases using current terminology
run-pfs-tcp-server port="8433" blob_bytes="1073741824" seed="305419896" dpg="16" grams="2048" max_len="65536" align="64":
    @echo "Starting PFS-TCP server on port {{port}}"
    dev/wip/native/pfs_gram --mode server --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --gram-count {{grams}} --max-len {{max_len}} --align {{align}}

run-pfs-tcp-client host="127.0.0.1" port="8433" blob_bytes="1073741824" seed="305419896" dpg="16" grams="2048" max_len="65536" align="64":
    @echo "Starting PFS-TCP client to {{host}}:{{port}}"
    dev/wip/native/pfs_gram --mode client --host {{host}} --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --gram-count {{grams}} --max-len {{max_len}} --align {{align}}

# Run UDP PacketFS-gram server/client
run-net-pfs-gram-udp-server port="8533" blob_bytes="1073741824" seed="305419896" dpg="16" total="1073741824" gram_bytes="60000" align="64":
    @echo "Starting UDP PacketFS-gram server on port {{port}}"
    dev/wip/native/pfs_gram_udp --mode server --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --total-bytes {{total}} --gram-bytes {{gram_bytes}} --align {{align}}

run-net-pfs-gram-udp-client host="127.0.0.1" port="8533" blob_bytes="1073741824" seed="305419896" dpg="16" total="1073741824" gram_bytes="60000" align="64":
    @echo "Starting UDP PacketFS-gram client to {{host}}:{{port}}"
    dev/wip/native/pfs_gram_udp --mode client --host {{host}} --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --total-bytes {{total}} --gram-bytes {{gram_bytes}} --align {{align}}

# Aliases using current terminology
run-pfs-udp-server port="8533" blob_bytes="1073741824" seed="305419896" dpg="16" total="1073741824" gram_bytes="60000" align="64":
    @echo "Starting PFS-UDP server on port {{port}}"
    dev/wip/native/pfs_gram_udp --mode server --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --total-bytes {{total}} --gram-bytes {{gram_bytes}} --align {{align}}

run-pfs-udp-client host="127.0.0.1" port="8533" blob_bytes="1073741824" seed="305419896" dpg="16" total="1073741824" gram_bytes="60000" align="64":
    @echo "Starting PFS-UDP client to {{host}}:{{port}}"
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
    mkdir -p dev/wip/native
    {{CC}} -O3 -march=native -DNDEBUG -pthread -DHAVE_LIBNUMA -o dev/wip/native/blueprint_reconstruct src/dev/wip/native/blueprint_reconstruct.c -lnuma
    @echo "Built dev/wip/native/blueprint_reconstruct"

# Build only the LLVM IR parser CLI
build-llvm-parser:
    @echo "Building llvm_parser CLI"
    mkdir -p bin
    {{CC}} {{CFLAGS}} {{INCLUDES}} -o bin/llvm_parser dev/wip/native/llvm_parser.c dev/wip/native/llvm_cli.c

# Build CPU baseline benchmark
build-cpu-baseline:
    @echo "Building CPU baseline"
    mkdir -p dev/wip/native
    {{CC}} -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/cpu_baseline src/dev/wip/native/cpu_baseline.c

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
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/memory_monster.py --size-mb 100

# Run blueprint-only Memory Monster using VirtualBlob shared memory (100MB)
run-memory-monster-blueprint:
    @echo "Running Memory Monster (blueprint mode, 100MB, loopback, shared memory)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/memory_monster.py --blueprint --size-mb 100 --blob-size-mb 100 --blob-name pfs_vblob_test --base-units 262144 --seg-len 384 --stride 8191 --delta 0

# Run blueprint-only Memory Monster using native reconstructor (100MB)
run-memory-monster-blueprint-native:
    @echo "Running Memory Monster (blueprint mode, native reconstructor, 100MB)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/memory_monster.py --blueprint --size-mb 100 --blob-size-mb 100 --blob-name pfs_vblob_test --base-units 262144 --seg-len 384 --stride 8191 --delta 0 --native

# Sweep benchmark across pCPU and segment sizes
# Description:
#   Runs blueprint-only reconstruction locally using the native reconstructor and prints CSV:
#   mode,seg_len,pcpu,threads,batch,elapsed_s,MBps,pcpu_units_per_s,eff_ops_per_s,cpu_MBps,cpu_ops_per_s,ops_ratio
#   Defaults: size=400MB, threads=16, batch=16, huge pages hint on, pCPU=200k,800k,1.3M; seg=80,256,4096; includes scatter.
bench-blueprint-sweep:
    @echo "Running blueprint sweep (size=400MB, pCPU=200k,800k,1.3M; seg=80,256,4096; contig + scatter; ops/s vs CPU)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --threads 16 --batch 16 --hugehint --pcpu 200000,800000,1300000 --seg 80,256,4096 --include-scatter --ops-per-byte 1 --cpu-baseline --out logs/bp_sweep.csv

# Sweep with coalescing explicitly disabled
bench-blueprint-sweep-nocoalesce:
    @echo "Running blueprint sweep (no coalesce)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --threads 16 --batch 16 --hugehint --pcpu 200000,800000,1300000 --seg 80,256,4096 --include-scatter --ops-per-byte 1 --cpu-baseline --no-coalesce --out logs/bp_sweep_nocoalesce.csv

# Parameterized sweep (override defaults without editing files)
# Usage example:
#   just bench-blueprint-sweep-custom 800 100 "400000,1300000,2600000" "80,256" 32 8 auto false true 2
#   meaning: size_mb=800, blob=100MB, pcpu list, seg list, threads=32, batch=8, numa=auto, interleave=false, hugehint=true, ops-per-byte=2
bench-blueprint-sweep-custom size_mb="400" blob_mb="100" pcpu="200000,800000,1300000" seg="80,256,4096" threads="16" batch="16" numa="auto" opspb="1" extra_flags="--hugehint --include-scatter --cpu-baseline":
    @echo "Blueprint sweep custom: size={{size_mb}}MB, blob={{blob_mb}}MB, pcpu={{pcpu}}, seg={{seg}}, threads={{threads}}, batch={{batch}}, numa={{numa}}, ops/byte={{opspb}}"
    @echo "Extra flags: {{extra_flags}} (e.g., --numa-interleave, --ops-per-byte 2, --cpu-baseline, --hugehint, --include-scatter)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py --size-mb {{size_mb}} --blob-size-mb {{blob_mb}} --blob-name pfs_vblob_test --threads {{threads}} --batch {{batch}} --pcpu {{pcpu}} --seg {{seg}} --numa {{numa}} --ops-per-byte {{opspb}} {{extra_flags}}

# Pass raw extra flags to sweep (ultimate flexibility)
# Usage: just bench-blueprint-sweep-args "--size-mb 800 --threads 32 --batch 8 --pcpu 400000,1300000 --seg 80,256 --ops-per-byte 2 --cpu-baseline --hugehint --include-scatter"
bench-blueprint-sweep-args flags="":
    @echo "Running blueprint sweep with extra flags: {{flags}}"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py {{flags}}

# Save + report convenience
bench-blueprint-report:
    @echo "Generating report from logs/bp_sweep.csv"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_sweep.csv --top 10

# Max-win search across combos (contig/scatter, pCPU list, seg list, threads, batch)
# Example: just bench-blueprint-maxwin (defaults: size=400MB, pCPU=200k..2.6M, seg=80,256,4096, threads=8,16,32, batch=8,16,32, ops/byte=1)
bench-blueprint-maxwin:
    @echo "Max-win sweep (size=400MB, broad grid, CPU baseline multi-thread)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --out logs/bp_maxwin.csv
    @echo "Report top wins (ops_ratio >= 1.0 likely in contig 80B range)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin.csv --top 15

# Max-win with coalescing off
bench-blueprint-maxwin-nocoalesce:
    @echo "Max-win sweep (no coalesce, broad grid)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --no-coalesce --out logs/bp_maxwin_nocoalesce.csv
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin_nocoalesce.csv --top 15

# Max-win with dumb CPU baseline (single-threaded)
bench-blueprint-maxwin-dumbcpu:
    @echo "Max-win sweep (CPU baseline single-thread dumb for comparison)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --cpu-dumb --out logs/bp_maxwin_dumbcpu.csv
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin_dumbcpu.csv --top 15

# Max-win with CPU measurement enabled (multi-threaded CPU baseline)
bench-blueprint-maxwin-measured:
    @echo "Max-win sweep (with CPU measurement enabled)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --measure-cpu --out logs/bp_maxwin_measured.csv
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin_measured.csv --top 15

# Max-win with dumb CPU baseline and CPU measurement
bench-blueprint-maxwin-dumbcpu-measured:
    @echo "Max-win sweep (dumb CPU baseline + CPU measurement)"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --cpu-dumb --measure-cpu --out logs/bp_maxwin_dumbcpu_measured.csv
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin_dumbcpu_measured.csv --top 15

# Fast contiguous profile (handy defaults to lean into winning conditions)
#  - size=400MB, seg=80, pCPU=200k, coalescing on, hugehint on, CPU baseline
bench-blueprint-fast-contig:
    @echo "Fast contiguous profile (size=400MB, seg=80, pCPU=200k, threads=16, batch=16, ops/byte=1)"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_sweep.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --threads 16 --batch 16 --pcpu 200000 --seg 80 --numa auto --hugehint --ops-per-byte 1 --cpu-baseline --out logs/bp_fast_contig.csv
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python dev/working/tools/blueprint_report.py --in logs/bp_fast_contig.csv --top 5

# Unit test for blueprint reconstruction
test-blueprint:
    @echo "Running blueprint reconstruction unit tests"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python -m pytest -q dev/working/tests/test_blueprint_transfer.py

# Build IR sample (requires clang)
build-ir-sample:
    @echo "Building IR sample (add4)"
    test -x "$(which clang)" || (echo "clang not found" && exit 1)
    clang -O3 dev/working/samples/add4.c -o dev/wip/samples/add4
    clang -O3 -S -emit-llvm dev/working/samples/add4.c -o dev/wip/samples/add4.ll

# Run IR execution pipeline test
test-ir-exec:
    @echo "Running IR execution pipeline tests"
    PYTHONPATH={{PKG_PYTHONPATH}} {{VENV_PATH}}/bin/python -m pytest -q dev/working/tests/test_ir_exec_pipeline.py

# Run the production IR executor CLI on a .ll file (clean wrapper)
run-ir-exec ll="dev/working/samples/llvm/compute/hello_world.ll" mode="both" windows="1":
    @echo "Running IR executor on {{ll}} (mode={{mode}}, windows={{windows}})"
    dev/working/tools/run_ir_exec.sh "{{ll}}" "{{mode}}" "{{windows}}"

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

# === 1GiB hugetlbfs helpers ===

hugepages-status:
    @echo "[STATUS] Verifying hugepages and mounts"
    bash scripts/hugepages/verify_hugepages.sh

hugepages-mount:
    @echo "[MOUNT] mount -a then verify"
    sudo mount -a
    bash scripts/hugepages/verify_hugepages.sh

# Typo-friendly alias
hugepagess-mount:
    @echo "[MOUNT] (alias) mount -a then verify"
    sudo mount -a
    bash scripts/hugepages/verify_hugepages.sh

pfs-1g:
    @echo "1GiB hugetlbfs workflow:"
    @echo "  1) just hugepages-status"
    @echo "  2) just build-net-pfs-gram; just build-blueprint-native; just build-cpu-baseline"
    @echo "  3) just run-pfs-tcp-1g-server port=8433 blob_bytes=1073741824"
    @echo "  4) just run-pfs-tcp-1g-client host=127.0.0.1 port=8433 blob_bytes=1073741824"
    @echo "  5) just bench-blueprint-fast-1g"

run-pfs-tcp-1g-server port="8433" blob_bytes="1073741824" seed="305419896" dpg="16" grams="2048" max_len="65536" align="64":
    @echo "Starting PFS-TCP server on 1GiB hugetlbfs (/mnt/huge1g)"
    dev/wip/native/pfs_gram --mode server --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --gram-count {{grams}} --max-len {{max_len}} --align {{align}} --huge-dir /mnt/huge1g

run-pfs-tcp-1g-client host="127.0.0.1" port="8433" blob_bytes="1073741824" seed="305419896" dpg="16" grams="2048" max_len="65536" align="64":
    @echo "Starting PFS-TCP client to {{host}}:{{port}} using 1GiB hugetlbfs (/mnt/huge1g)"
    dev/wip/native/pfs_gram --mode client --host {{host}} --port {{port}} --blob-size {{blob_bytes}} --seed {{seed}} --desc-per-gram {{dpg}} --gram-count {{grams}} --max-len {{max_len}} --align {{align}} --huge-dir /mnt/huge1g

bench-blueprint-maxwin-1g out="logs/bp_maxwin_huge1g_dumbcpu.csv":
    @echo "Max-win sweep (1GiB hugetlbfs) -> {{out}}"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --cpu-dumb --out {{out}} --out-hugefs-dir /mnt/huge1g --blob-hugefs-dir /mnt/huge1g

bench-blueprint-fast-1g out="logs/bp_fast_huge1g.csv":
    @echo "Fast profile (1GiB hugetlbfs) -> {{out}}"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 200 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 800000,1300000,2600000 --seg 256,4096 --threads 8,16 --batch 8,16 --modes contig --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --out {{out}} --out-hugefs-dir /mnt/huge1g --blob-hugefs-dir /mnt/huge1g

# AF_PACKET fixed-frame streaming (TX/RX) with arithmetic + CPU pinning
build-net-pfs-stream-afpacket:
    @echo "Building AF_PACKET TX/RX (fixed frames)"
    mkdir -p dev/wip/native
    {{CC}} -O3 -march=native -DNDEBUG -D_GNU_SOURCE -pthread -o dev/wip/native/pfs_stream_afpacket_tx \
      realsrc/packetfs/network/pfs_stream_afpacket_tx.c
    {{CC}} -O3 -march=native -DNDEBUG -D_GNU_SOURCE -pthread -o dev/wip/native/pfs_stream_afpacket_rx \
      realsrc/packetfs/network/pfs_stream_afpacket_rx.c

# Run AF_PACKET RX
# usage: just dev-run-pfs-stream-afpacket-rx ifname=enp130s0 frame=4096 duration=10 cpu=0 pcpu_op=fnv imm=0
dev-run-pfs-stream-afpacket-rx ifname="" frame="4096" duration="10" cpu="0" pcpu_op="fnv" imm="0":
    @echo "Starting AF_PACKET RX on {{ifname}} (frame={{frame}}, cpu={{cpu}}, op={{pcpu_op}}, imm={{imm}})"
    taskset -c {{cpu}} sudo -n dev/wip/native/pfs_stream_afpacket_rx --ifname {{ifname}} --frame-size {{frame}} --duration {{duration}} --cpu {{cpu}} --pcpu-op {{pcpu_op}} --imm {{imm}}

# Run AF_PACKET TX
# usage: just dev-run-pfs-stream-afpacket-tx ifname=enp130s0 dst=<mac> frame=4096 duration=10 cpu=0 pcpu_op=fnv imm=0
dev-run-pfs-stream-afpacket-tx ifname="" dst="ff:ff:ff:ff:ff:ff" frame="4096" duration="10" cpu="0" pcpu_op="fnv" imm="0":
    @echo "Starting AF_PACKET TX on {{ifname}} -> {{dst}} (frame={{frame}}, cpu={{cpu}}, op={{pcpu_op}}, imm={{imm}})"
    taskset -c {{cpu}} sudo -n dev/wip/native/pfs_stream_afpacket_tx --ifname {{ifname}} --dst {{dst}} --frame-size {{frame}} --duration {{duration}} --cpu {{cpu}} --pcpu-op {{pcpu_op}} --imm {{imm}}

# Async single-core helper
dev-async-core cpu="0":
    @echo "Starting single-core async loop on CPU {{cpu}} (queue: logs/patterns/queue)"
    {{VENV_PATH}}/bin/python dev/working/tools/async_core.py --cpu {{cpu}}

dev-async-queue-file path="" win="4096" k="50" mods="64,128,256,512,4096" zlib="0" lags="0" lags_set="" delta="0" dupes="0" magic="0":
    @if [ -z "{{path}}" ]; then echo "Usage: just dev-async-queue-file path=<file> [win=4096] [k=50] [mods=64,128,256,512,4096] [zlib=1] [lags=1 lags_set=...] [delta=1] [dupes=1] [magic=1]"; exit 1; fi
    @mkdir -p logs/patterns/queue
    WIN={{win}} K={{k}} MODS={{mods}} ZLIB={{zlib}} LAGS={{lags}} LAGS_SET={{lags_set}} DELTA={{delta}} DUPES={{dupes}} MAGIC={{magic}} PATH_ARG={{path}} bash scripts/patterns/enqueue_file.sh

dev-async-queue-blob name="pfs_vblob_test" size_mb="100" seed="1337" win="4096" k="50" mods="64,128,256,512,4096" keep="0" zlib="0" lags="0" lags_set="" delta="0" dupes="0" magic="0":
    @mkdir -p logs/patterns/queue
    NAME={{name}} SIZE_MB={{size_mb}} SEED={{seed}} WIN={{win}} K={{k}} MODS={{mods}} KEEP={{keep}} ZLIB={{zlib}} LAGS={{lags}} LAGS_SET={{lags_set}} DELTA={{delta}} DUPES={{dupes}} MAGIC={{magic}} bash scripts/patterns/enqueue_blob.sh

dev-llvm-findings scan_dir="" bin="" win="4096":
    @if [ -z "{{scan_dir}}" ] || [ -z "{{bin}}" ]; then echo "Usage: just dev-llvm-findings scan_dir=<logs/patterns/...> bin=<path to binary> [win=4096]"; exit 1; fi
    bash scripts/patterns/llvm_findings.sh --scan-dir "{{scan_dir}}" --bin "{{bin}}" --win "{{win}}"

dev-blob-build name="pfs_vblob_test" size_mb="1024" seed="1337" profile="orchard" snapshot="":
    @echo "[blob] build name={{name}} size={{size_mb}}MB seed={{seed}} profile={{profile}}"
    NAME={{name}} SIZE_MB={{size_mb}} SEED={{seed}} PROFILE={{profile}} SNAPSHOT={{snapshot}} bash scripts/patterns/blob_build.sh

dev-logs-index:
    @echo "Indexing logs into reports/ (latest patterns and plans)"
    @mkdir -p logs/reports
    {{VENV_PATH}}/bin/python scripts/logs/index_logs.py

dev-logs-archive months="1" dry="1":
    @echo "Archiving logs older than {{months}} month(s) (dry={{dry}})"
    @bash -eu -o pipefail -c '
    shopt -s nullglob; \
    now=$(date +%s); cutoff=$(( now - {{months}}*30*24*3600 )); \
    mkdir -p logs/archive; \
    for d in logs/patterns/* logs/plans/*; do \
      [ -d "$d" ] || continue; \
      ts=$(date -r "$d" +%s); \
      if [ "$ts" -lt "$cutoff" ]; then \
        ym=$(date -r "$d" +%Y-%m); \
        dest="logs/archive/$ym/$(basename "$d")"; \
        echo "Move $d -> $dest"; \
        if [ "{{dry}}" != "1" ]; then mkdir -p "$(dirname "$dest")" && mv "$d" "$dest"; fi; \
      fi; \
    done'

dev-blob-index snapshot="" out="":
    @if [ -z "{{snapshot}}" ]; then echo "Usage: just dev-blob-index snapshot=<path/to/blob.bin> [out=<path.pkl>]"; exit 1; fi
    {{VENV_PATH}}/bin/python scripts/patterns/blob_index_build.py --snapshot "{{snapshot}}" $([ -n "{{out}}" ] && echo --out "{{out}}" || true)

dev-plan-file path="" snapshot="" index="" win="4096":
    @if [ -z "{{path}}" ] || [ -z "{{snapshot}}" ] || [ -z "{{index}}" ]; then echo "Usage: just dev-plan-file path=<file> snapshot=<blob.bin> index=<blob.kg4.pkl> [win=4096]"; exit 1; fi
    {{VENV_PATH}}/bin/python scripts/patterns/planner.py --path "{{path}}" --snapshot "{{snapshot}}" --index "{{index}}" --win "{{win}}"

# Pattern analysis workflows
dev-pattern-scan-file path="" win="4096" k="50" mods="64,128,512,4096" zlib="0" lags="0" lags_set="" delta="0" dupes="0" magic="0":
    @if [ -z "{{path}}" ]; then echo "Usage: just dev-pattern-scan-file path=<file> [win=4096] [k=50] [mods=64,128,512,4096] [zlib=1] [lags=1 lags_set=1,2,4,8,16] [delta=1] [dupes=1] [magic=1]"; exit 1; fi
    @echo "[pattern] file={{path}} win={{win}} k={{k}} mods={{mods}} zlib={{zlib}} lags={{lags}} delta={{delta}} dupes={{dupes}} magic={{magic}}"
    @mkdir -p logs/patterns
    ZLIB={{zlib}} LAGS={{lags}} LAGS_SET={{lags_set}} DELTA={{delta}} DUPES={{dupes}} MAGIC={{magic}} bash scripts/patterns/scan_file.sh --path "{{path}}" --win "{{win}}" --k "{{k}}" --mods "{{mods}}"

dev-pattern-scan-blob name="pfs_vblob_test" size_mb="100" seed="1337" win="4096" k="50" mods="64,128,512,4096" keep="0" zlib="0" lags="0" lags_set="" delta="0" dupes="0" magic="0":
    @echo "[pattern] blob name={{name}} size={{size_mb}}MB seed={{seed}} win={{win}} k={{k}} mods={{mods}} keep={{keep}} zlib={{zlib}} lags={{lags}} delta={{delta}} dupes={{dupes}} magic={{magic}}"
    @mkdir -p logs/patterns
    KEEP={{keep}} ZLIB={{zlib}} LAGS={{lags}} LAGS_SET={{lags_set}} DELTA={{delta}} DUPES={{dupes}} MAGIC={{magic}} bash scripts/patterns/scan_blob.sh --name "{{name}}" --size-mb "{{size_mb}}" --seed "{{seed}}" --win "{{win}}" --k "{{k}}" --mods "{{mods}}"

dev-shm-run blob_mb="1024" dpf="32" ring_pow2="20" align="64" duration="5" threads="2" arith="0" vstream="0" ports="1" queues="2" mode="scatter" seg_len="256" reuse="0" pcpu="0" pcpu_op="fnv" imm="0" payload_max="2048":
    @echo "[shm-run] printing variables and memory estimate, then launching"
    bash scripts/benchmarks/shm_run.sh --blob-mb "{{blob_mb}}" --dpf "{{dpf}}" --ring-pow2 "{{ring_pow2}}" --align "{{align}}" --duration "{{duration}}" --threads "{{threads}}" --arith "{{arith}}" --vstream "{{vstream}}" --ports "{{ports}}" --queues "{{queues}}" --mode "{{mode}}" --seg-len "{{seg_len}}" --reuse-frames "{{reuse}}" --pcpu "{{pcpu}}" --pcpu-op "{{pcpu_op}}" --imm "{{imm}}" --payload-max "{{payload_max}}"

dev-shm-run-1_5m:
    @echo "[shm-run-1_5m] ~1.57M outstanding (ring=2^19, queues=3), fixed-descriptor path"
    bash scripts/benchmarks/shm_run.sh --blob-mb 1024 --dpf 32 --ring-pow2 19 --align 64 --duration 5 --threads 2 --arith 0 --vstream 0 --ports 1 --queues 3 --mode scatter --seg-len 256 --pcpu 0 --pcpu-op fnv --imm 0 --payload-max 2048

# =====================
dev-shm-queue-sweep ring_pow2="19" queues="1,2,4,8" dpf="32" seg_len="256" duration="5" threads="2" pcpu_op="xor" imm="255":
    @echo "[sweep] queues=\"{{queues}}\" ring=2^{{ring_pow2}} dpf={{dpf}} seg={{seg_len}} dur={{duration}}s threads={{threads}} pcpu_op={{pcpu_op}} imm={{imm}}"
    bash scripts/benchmarks/shm_queue_sweep.sh --ring-pow2 "{{ring_pow2}}" --queues "{{queues}}" --dpf "{{dpf}}" --seg-len "{{seg_len}}" --duration "{{duration}}" --threads "{{threads}}" --pcpu-op "{{pcpu_op}}" --imm "{{imm}}"

# Kernel fastpath helper (module)
# =====================

kmod-build-fastpath:
    @echo "Building pfs_fastpath kernel module"
    make -C dev/kernel/pfs_fastpath

kmod-load-fastpath:
    @echo "Loading pfs_fastpath"
    sudo insmod dev/kernel/pfs_fastpath/pfs_fastpath.ko || sudo modprobe pfs_fastpath || true
    dmesg | tail -n 20 | sed -n 's/.*pfs_fastpath.*/&/p'

kmod-unload-fastpath:
    @echo "Unloading pfs_fastpath"
    sudo rmmod pfs_fastpath || true

# Big sweep of SHM bench across multiple parameters
dev-shm-big-sweep rp2="18,19" ports="1" queues="1,3" cthreads="1,4" seg_lens="80,256,4096" duration="5" dpf="32" out="logs/reports/shm_big_sweep.csv":
    @echo "[big-sweep] rp2={{rp2}} ports={{ports}} queues={{queues}} cthreads={{cthreads}} seg_lens={{seg_lens}} dpf={{dpf}} duration={{duration}}s -> {{out}}"
    bash scripts/benchmarks/shm_big_sweep.sh --ring-pow2-list "{{rp2}}" --ports-list "{{ports}}" --queues-list "{{queues}}" --pcpu-threads-list "{{cthreads}}" --seg-len-list "{{seg_lens}}" --duration "{{duration}}" --dpf "{{dpf}}" --out "{{out}}"

dev-shm-maxwin-sweep queues="1,3" cthreads="1,2,4,8" seg_len="80" rp2="19" dpf="64" duration="5" out="logs/reports/shm_maxwin_sweep.csv":
    @echo "[maxwin] rp2={{rp2}} queues={{queues}} cthreads={{cthreads}} seg_len={{seg_len}} dpf={{dpf}} -> {{out}}"
    bash scripts/benchmarks/shm_maxwin_sweep.sh --ring-pow2 "{{rp2}}" --queues-list "{{queues}}" --pcpu-threads-list "{{cthreads}}" --seg-len "{{seg_len}}" --dpf "{{dpf}}" --duration "{{duration}}" --out "{{out}}"

# =====================
# Merge service (Podman)
# =====================

# Build image with Podman (per repo rule: Podman > Docker)
# Image tag: packetfs/pfs-merge:latest
_dev_build_pfs_merge_internal:
    @echo "[build] containers/pfs-merge/Containerfile -> packetfs/pfs-merge:latest"
    podman build -t packetfs/pfs-merge:latest -f containers/pfs-merge/Containerfile .

dev-build-pfs-merge: _dev_build_pfs_merge_internal

# Run service container exposing port 9876 and with /boot/efi and /data mounted read-only/with write where needed
# Note: FUSE mounts will require --cap-add SYS_ADMIN and /dev/fuse if/when we enable the union view
# For now, we only run the TCP service
_dev_run_pfs_merge_internal:
    @bash -eu -o pipefail -c '
    echo "[run] packetfs/pfs-merge:latest";
    extra_mounts="";
    if [ -d /etc/letsencrypt ]; then extra_mounts="-v /etc/letsencrypt:/etc/letsencrypt:ro"; fi;
    podman run -d --name pfs-merge \
      --pull=never \
      --net=host \
      --cap-add NET_ADMIN \
      -e PFS_MERGE_ROOT=/data/local \
      -e PFS_TLS_LE_NAME="${PFS_TLS_LE_NAME:-}" \
      -e PFS_TLS_CERT="${PFS_TLS_CERT:-}" \
      -e PFS_TLS_KEY="${PFS_TLS_KEY:-}" \
      -e PFS_TLS_CA="${PFS_TLS_CA:-}" \
      -e PFS_TLS_DISABLE="${PFS_TLS_DISABLE:-0}" \
      -e PFS_TLS_SUBJ="${PFS_TLS_SUBJ:-/CN=pfs-merge}" \
      -e PFS_TLS_DAYS="${PFS_TLS_DAYS:-365}" \
      -v /data/local:/data/local:Z \
      $extra_mounts \
      packetfs/pfs-merge:latest'

dev-run-pfs-merge: dev-build-pfs-merge _dev_run_pfs_merge_internal
    @echo "Tip: enable jumbo frames and turn off GRO/LRO on enp130s0:"
    @echo "  sudo ip link set enp130s0 mtu 9000 && sudo ethtool -K enp130s0 gro off lro off tso off gso off"
    @echo "Consider pinning IRQs and threads to the same core for enp130s0"

# Stop and remove container
_dev_stop_pfs_merge_internal:
    -podman rm -f pfs-merge >/dev/null 2>&1 || true

dev-stop-pfs-merge: _dev_stop_pfs_merge_internal

# Host-side CLI to connect to a peer
# Usage: just dev-merge host=10.0.0.2 port=9876
# Requires realsrc installed in central venv

dev-merge host="127.0.0.1" port="9876":
    {{VENV_PATH}}/bin/python -c "from packetfs.merge.cli import run_merge; import sys; sys.exit(run_merge('{{host}}', int('{{port}}')))"
