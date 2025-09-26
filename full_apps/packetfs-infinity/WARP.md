# WARP.md — PacketFS Infinity (Edge pCPU + Packet-Native FS)

This repo turns caches, edges, and firewalls you own into a global “virtual CPU” that computes on bytes without downloading them. Files become formulas. Transfer is packets. Execution is packets.

Core ideas

- Compute at the edge: run tiny streaming ops (counteq/xor/add/fnv/crc32c) over 1 MiB Range windows right at POPs (Cloudflare Workers, micro-servers behind CDNs). Return tiny results (counts/proofs); never pull full files.
- Internet-as-blob: for public/owned assets, fetch aligned windows from caches (HITs) and assemble results locally. The planner aligns to 1 MiB and coalesces adjacent ranges.
- Virtual pCPU: register assets you own (Workers, edge servers, nftables counters, AWS Flow Logs) and schedule jobs by latency/cost/concurrency. Report CPUpwn (GB/s) and cache HIT ratio.
- Storage is formulas: the filesystem is packets. PacketFS translates reads/writes into packet programs and arithmetic proofs rather than bulk bytes.

Quickstart (local)

- Start local dev server (Hypercorn; WS_PORT=8811 by default):

  - Run: just dev up
  - Note: endpoint base http://127.0.0.1:8811 unless you override WS_PORT
- Alternative edge server (port 5000) if you prefer the standalone script:

  - nohup /home/punk/.venv/bin/python edge-compute/pfs_edge_server.py > server.log 2>&1 &
  - Health: curl -s localhost:5000/health | jq .
- Generate a fast tmpfs blob and bench locally:

  - just dev-data-blob /dev/shm/pfs_blob.bin 256 zero
  - just dev-bench-local /dev/shm/pfs_blob.bin 8 256 counteq 0
- Run a compute job against the local server:

  - just dev-vpcpu-compute kind=edge_http endpoint=http://localhost:8811 data_url=file:///dev/shm/pfs_blob.bin instructions='[{"op":"counteq","imm":0,"offset":0,"length":1048576}]'

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

---

## PacketFS Native Arithmetic Mode (Production, strict no-RAW)

This section documents the current production arithmetic setup, options, and how to run it locally and in SaaS mode.

### Summary (what we implemented)
- Deterministic 1 GiB VirtualBlob with a 256 KiB palette region (constant tiles 0..255 + mixed banks: ramp, gray, LFSR, periodic stripes, numeric stride, ASCII tokens). Both sides must share the same (name,size,seed).
- Palette-only compiler (server-side) that builds BREF-only IPROGs strictly (no RAW fallback). If a window cannot be expressed via identity or imm5 transforms (XOR/ADD) against the palette, the compile fails with HTTP 422.
- Two content modes over the same frames (preface/MFST/WIN/END/DONE):
  - PVRT (default): BREF-only PVRT container per window (no RAW section).
  - OFFS (backup): raw offset tuples (OFFS) per window with imm5 flags and optional relative-to-anchor deltas.
- WebSocket multi-channel sender/receiver support PVRT and OFFS. Receiver reconstructs strictly from the shared blob and applies imm5 transforms.
- SaaS preflight can be disabled (PFS_BLOB_PREFLIGHT=0) to simplify central-only flows.
- UI enhancements: content-mode dropdown (PVRT | OFFS) and “Send to self” button.

### Strict policy (no RAW)
- No RAW bytes are ever embedded or sent by arithmetic transfers.
- The compiler (/objects/from-palette) returns HTTP 422 on unmatchable tiles instead of falling back.

### Key env options (content + transport)
- PFS_TX_MODE: pvrt (default) | offs
  - Controls the content mode used by WS sender.
- PFS_WS_CHANNELS: integer (default 10)
  - Parallel WS channels for speed.
- PFS_BLOB_PREFLIGHT: 1 (default) | 0
  - If 1, /transfers preflights the peer’s blob fingerprint; if 0 (SaaS), skip preflight.
- PFS_QUIC_ENABLE: 1 (default) | 0
  - Set 0 to silence QUIC bind logs in prod if not using QUIC.
- PFS_BLOB_NAME / PFS_BLOB_SIZE_BYTES / PFS_BLOB_SEED
  - VirtualBlob identity. Palette lives right after header; both sides must match exactly for reconstruction.

### Endpoints (arithmetic)
- POST /objects/from-palette (multipart/form-data)
  - Input: file (bytes)
  - Output: { object_id, size, sha256, compressed_size, tx_ratio, policy: "palette-only" }
  - Behavior: builds BREF-only IPROG; fails 422 on unmatchable tiles; no RAW fallback.
- POST /transfers (application/json)
  - Body: { object_id, mode: "ws" | "auto" | …, peer: { host, https_port }, tx_mode: "pvrt" | "offs" }
  - Starts an arithmetic transfer over WS using the selected content mode. SaaS preflight is disabled if PFS_BLOB_PREFLIGHT=0.
- GET /transfers/{transfer_id}
  - Returns state + metrics (bytes_sent, speedup, throughput_mbps, windows, protocol).
- POST /blob/setup, GET /blob/status
  - Attach/inspect the VirtualBlob on the server.
- POST /auth/disable, POST /auth/enable
  - Toggle auth during local testing.

### Production start (443)
- Script: `start-production.sh` now sets SaaS-friendly defaults:
  - PFS_AUTH_ENABLED=1 (auth on)
  - PFS_BLOB_PREFLIGHT=0 (skip peer preflight for SaaS central)
  - PFS_BLOB_NAME=pfs_vblob_palette, PFS_BLOB_SIZE_BYTES=1073741824, PFS_BLOB_SEED=1337
  - Runs Hypercorn on 443 with TLS certs under ./certs
- Optional: set `PFS_QUIC_ENABLE=0` to silence QUIC bind warnings.
- Optional: set `PFS_TX_MODE=offs` to force OFFS globally (recommended only for experiments; keep PVRT as default in prod).

### Local “full on” PVRT test (recommended)
1) Health
```bash
curl -k https://localhost/health
```
2) Ensure palette blob
```bash
curl -k -X POST https://localhost/blob/setup \
  -H 'Content-Type: application/json' \
  -d '{"name":"pfs_vblob_palette","size_bytes":1073741824,"seed":1337}'
curl -k https://localhost/blob/status
```
3) Compile a small file (BREF-only; no RAW) and send to self over WS
```bash
# zeros
dd if=/dev/zero bs=8192 count=1 of=/tmp/palette_zero.bin status=none
OBJ_ID=$(curl -k -sS -F file=@/tmp/palette_zero.bin https://localhost/objects/from-palette \
  | tee /dev/stderr | python3 -c 'import sys, json; print(json.load(sys.stdin)["object_id"])')

curl -k -sS -X POST https://localhost/transfers \
  -H 'Content-Type: application/json' \
  -d "{ \"object_id\": \"$OBJ_ID\", \"mode\": \"ws\", \"peer\": { \"host\": \"127.0.0.1\", \"https_port\": 443 }, \"tx_mode\": \"pvrt\" }"
```
4) UI path
- Open https://localhost/, upload a file, choose PVRT in the dropdown, click “Send to self”.

### OFFS (backup) quick test
- Same as PVRT test, but set `"tx_mode": "offs"` in the /transfers body.
- Or choose OFFS in the UI dropdown before clicking “Send to self”.
- Notes: OFFS frames carry only offset tuples (with imm5 transforms and optional relative deltas). The receiver reconstructs strictly from the blob.

### Failure semantics
- If a file cannot be compiled strictly from the palette with identity/XOR imm5/ADD imm5, /objects/from-palette returns HTTP 422.
- No fallback to RAW or byte streaming is implemented anywhere in arithmetic paths.

### Internals and file map
- Palette + compiler
  - Palette fill: `packetfs/filesystem/virtual_blob.py` (constant tiles 0..255 + mixed banks)
  - Compiler (strict): `app/routes/palette_build.py` (identity + imm5 transforms; 4-byte k‑gram index for identity/prefix matches)
- WS
  - Sender: `app/services/transports/ws_proxy.py` (PVRT or OFFS, env or API-controlled)
  - Receiver: `app/routes/websockets.py` (OFFS + PVRT decode; imm5 transforms applied; relative deltas via anchor)
- Endpoints
  - `app/core/routes/objects.py` (upload → strict IPROG build; no raw store)
  - `app/core/routes/transfers.py` (tx_mode plumbed)
  - `app/routes/iprog.py` (validates BREF-only windows; rejects RAW)
- UI
  - `app/static/index.html` (content-mode dropdown, send-to-self button)

### Roadmap (transport experiments; still no RAW)
- WebRTC DataChannels fallback (same frames):
  - ctrl DC: reliable ordered; data DC: partial reliability, unordered
  - Expose transport dropdown in UI (WS default, WebRTC optional)
- UDP prototype (offset-only):
  - Header + CRC16 + NAK-based control over WS
  - MTU 1200, no fragmentation, strict offsets-only

---

## PacketFS Native Arithmetic Mode (What changed)

Goal: send programs, not bytes. Sender and receiver agree on a middle-of-blob anchor; all BREF offsets are sent as +/- deltas relative to that anchor. The receiver reconstructs from a shared VirtualBlob.

What’s implemented

- WebSocket endpoint `/ws/pfs-arith` handles arithmetic mode: PVRT preface includes anchor, MFST/NEED handshake, per-window WIN/END/DONE controls, and PVRT BREF-only payloads with relative offsets (flags bit0 set).
- QUIC “iprog” path mirrors the same arithmetic semantics.
- Transfer orchestrator prefers arithmetic first in `mode: "auto"`, and exposes strict modes:
  - `iprog-only` (alias `pfs-only`): try QUIC IPROG then WS IPROG; if both fail, do not fall back to legacy/raw paths.
- Browser/Node client library (served from `/static/pfs-arith`) formalizes PVRT preface/framing + container and sends IPROG with relative BREF.

How to verify

- Use strict mode and read the path:
  - POST `/transfers` with `{ "mode": "iprog-only", ... }`.
  - GET `/transfers/{id}` → `details.path` is `ws-iprog` or `quic-iprog` and `tx_ratio > 1.0`.
- Manual E2E from the page:
  - Open `/`, upload a file (builds IPROG), then in console: `await window.pfsSendIprog(iprogJson, 'demo-xfer')`.

Key internals

- Preface anchor = mid-blob; offsets transmitted as two’s-complement deltas modulo 2^64 with flags |= 0x01 (relative).
- Legacy “plan” path encodes RAW sections and will “send all bytes”; arithmetic path never includes RAW.

---

## Simplified workflow (3 commands)

- Rebuild (no cache):

  - `just rebuild`
  - Runs a clean build of the TypeScript arithmetic library and container image(s) with `--no-cache`.
- Up:

  - `just up`
  - Starts the backend with TLS (self-signed), auto-attached VirtualBlob, and arithmetic mode enabled.
  - Open https://localhost:${PORT:-8811}/ (root serves the SPA).
- Down:

  - `just down`
  - Stops and removes the running container.

Notes

- The build steps ensure `/static/pfs-arith` is available by building `app/web/pfs-arith` before the container image.
- Environment flags like `PFS_BLOB_SIZE_BYTES`, `PFS_ARITH`, `PFS_SIMPLE_XFER` are documented in `just docs-env`.
