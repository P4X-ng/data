# WARP.md — PacketFS Infinity (Edge pCPU + Packet-Native FS)

This repo turns caches, edges, and firewalls you own into a global “virtual CPU” that computes on bytes without downloading them. Files become formulas. Transfer is packets. Execution is packets.

Core ideas
- Compute at the edge: run tiny streaming ops (counteq/xor/add/fnv/crc32c) over 1 MiB Range windows right at POPs (Cloudflare Workers, micro-servers behind CDNs). Return tiny results (counts/proofs); never pull full files.
- Internet-as-blob: for public/owned assets, fetch aligned windows from caches (HITs) and assemble results locally. The planner aligns to 1 MiB and coalesces adjacent ranges.
- Virtual pCPU: register assets you own (Workers, edge servers, nftables counters, AWS Flow Logs) and schedule jobs by latency/cost/concurrency. Report CPUpwn (GB/s) and cache HIT ratio.
- Storage is formulas: the filesystem is packets. PacketFS translates reads/writes into packet programs and arithmetic proofs rather than bulk bytes.

Quickstart (local)
- Start local edge server (already added):
  - python path: /home/punk/.venv
  - Run: nohup /home/punk/.venv/bin/python edge-compute/pfs_edge_server.py > server.log 2>&1 &
  - Health: curl -s localhost:5000/health | jq .

- Generate a fast tmpfs blob and bench locally (for raw streaming):
  - just dev-data-blob /dev/shm/pfs_blob.bin 256 zero
  - just dev-bench-local /dev/shm/pfs_blob.bin 8 256 counteq 0

- Run a compute job against the local server:
  - just dev-vpcpu-compute kind=edge_http endpoint=http://localhost:5000 data_url=file:///dev/shm/pfs_blob.bin instructions='[{"op":"counteq","imm":0,"offset":0,"length":1048576}]'

Edge compute — Cloudflare Worker
- Code: edge-compute/cloudflare-worker.js (streaming + Range)
- Deploy: wrangler publish (add a wrangler.toml for your zone)
- Test:
  - curl -s -X POST https://YOUR.workers.dev/compute -H 'content-type: application/json' -d '{"data_url":"https://example.com/big.bin","instructions":[{"op":"counteq","imm":0,"offset":0,"length":1048576}]}' | jq .
- Response includes: results, timing (bytes_processed, elapsed_ms), and CF-Cache-Status.

Range planner
- scripts/edge/range_planner.py: coalesces windows to 1 MiB aligned ranges.
- Example: /home/punk/.venv/bin/python scripts/edge/range_planner.py --windows '[{"offset":0,"length":65536},{"offset":65536,"length":65536}]'

Asset spider (allowlist only)
- scripts/spider/asset_spider.py; wrapper scripts/spider/run_spider.sh
- Discover Accept-Ranges, ETag/size, vendor, cache headers, and a small 64 KiB compute bps estimate.
- Example: just dev-spider-assets seeds=https://releases.ubuntu.com/ allow=releases.ubuntu.com range=1 compute_kind=edge_http compute_endpoint=http://localhost:5000
- Catalog: var/vpcpu/data_assets.db

Virtual pCPU registry
- Init DB: just dev-vpcpu-init
- Add assets:
  - just dev-vpcpu-add name=local-edge kind=edge_http endpoint=http://localhost:5000 attrs='{"latency_ms":5,"concurrency":16}'
  - just dev-vpcpu-add name=cf-worker kind=worker endpoint=https://YOUR.workers.dev attrs='{"latency_ms":25,"region":"SJC","concurrency":32}'
- List: just dev-vpcpu-list
- Run: just dev-vpcpu-compute kind=worker endpoint=https://YOUR.workers.dev data_url=https://… instructions='[...]'

Milkshake (firewall compute you own)
- Local nftables: scripts/milkshake/*; run: just dev-milkshake port=51999 seconds=2 pps=10000
- AWS Flow Logs “word program”: setup/query/word targets in Justfile.dev (dev-milkshake-aws-setup, dev-milkshake-aws-query, dev-milkshake-aws-word); slow, cheap oracle for consensus.

Budgets and etiquette
- Legal/ethical only. Only assets and infra you own/control/are permitted to use. Respect robots/ToS.
- Cache-friendly always: 1 MiB aligned windows; coalesce; 2–10 concurrent streams per origin; back off on MISS.
- Immutable content: content-addressed URLs and signatures; long TTL; polite pre-warm.
- Budgets: set daily caps for requests and bytes. Track CPUpwn and HIT ratio.

Packet-native filesystem (vision)
- The PacketFS FUSE filesystem represents files as packet programs and arithmetic proofs; storage is symbolic; execution is packet flow.
- This repo’s edge pCPU complements PacketFS by providing compute surfaces to validate/execute these programs at or near the data.

Documented local benchmark (2025-09-17)
- Environment
  - Local Flask edge server at http://localhost:5000 (streaming, range-aware)
  - Blob stored in tmpfs (/dev/shm)
  - Window size: 1 MiB; Concurrency: 8; Total windows: 256 (256 MiB total)
- Commands executed
  - just dev-data-blob /dev/shm/pfs_blob.bin 256 zero
  - just dev-bench-local /dev/shm/pfs_blob.bin 8 256 counteq 0
- Result
  - windows=256 bytes=268,435,456 elapsed_s=0.275 throughput=932.1 MB/s cpupwn≈0.91 GB/s
- Notes
  - This is a Python/Flask implementation; switching to a native hot loop or ASGI + uvloop typically pushes multi‑GB/s locally. At the POP (Cloudflare Worker), capacity scales with streams and POP count.

Roadmap (parallel tracks)
- A) Worker deploy + bench (CPUpwn baseline per POP)
- B) Regional micro-servers behind CloudFront (2–3 regions)
- C) Planner + pfs-cli runner (plan → run → combine)
- D) Spider catalog + allowlist policy
- E) vPCPU scheduler + budgets
- F) OSv/VMKit microVM (self-fetching, content-hash image)
- G) Security (sign/verify manifests and plans)

Notes
- Central venv: /home/punk/.venv; prefer Podman over Docker.
- Just targets are thin; complex logic is in scripts/.
- Demo scripts belong in demo/; production code elsewhere.