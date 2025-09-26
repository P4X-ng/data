# OSv Yeet — tiny UDP slinger pair (sender/listener)

Purpose
- Minimal unikernel pair for blasting/receiving UDP as fast as possible.
- First iteration uses a very small “raw” header and UDP transport.
- QUIC/WS can be layered later by swapping the transport under the same proto.

Layout
- include/proto.h: common message header (v0)
- src/yeet_sender.c: sends UDP packets at max rate (or rate-limited)
- src/yeet_listener.c: receives UDP packets, prints rolling stats
- scripts/build_host.sh: build Linux host binaries (bin/yeet_sender, bin/yeet_listener)
- scripts/run_host_sender.sh: env-driven wrapper for sender on host
- scripts/run_host_listener.sh: env-driven wrapper for listener on host
- scripts/osv/build_osv.sh: stubbed build wrapper for OSv images (uses capstan if available)
- scripts/osv/Capstanfile.sender / Capstanfile.listener: example Capstan files
- scripts/osv/module/sender/ and module/listener/: content staging for capstan
- scripts/osv/README.md: notes on building OSv images locally
- scripts/vm/launch_swarm_osv.sh: launch a swarm of OSv VMs (no /bin/bash expectations)
- Justfile.osv: helper recipes — build-host, run-host-*, build-osv-*, swarm-osv-*

First iteration
- UDP only (v0). Header fields: magic, version, seq, len.
- Single socket, single thread in both apps.
- Listener prints totals/pps every 500ms (configurable via env).

Next steps
- Add QUIC/WS transports using existing minimal stacks you have; reuse proto.h.
- Add optional CRC32 and drop stats; optional multi-socket fanout.
- Wire swarm sender/receiver split and measurement to compare CPU/pCPU vs GPU.
