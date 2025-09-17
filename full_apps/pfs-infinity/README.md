# pfs-infinity

Infinity storage front-end for PacketFS.
- Core idea: files are programmatic representations; we persist compact plans and reconstruct on demand.
- MVP: upload a file -> derive a compact “blueprint” (hashes, arithmetic ops, refs), store blueprint; download reconstructs via PacketFS pipeline.

Endpoints (MVP)
- GET /health -> {status: ok}
- POST /blueprints/from-bytes -> returns blueprint (JSON) for input bytes (dev-only path; uses in-repo PacketFS ‘src’ scaffold for consistent tests)
- POST /objects -> store blueprint, return object_id
- GET /objects/{id} -> returns reconstructed bytes (dev-only path; in prod: stream from pfs executor)

Static pages
- /static/transfer.html — transfer-only UI (Uppy Dashboard “Upload” triggers /objects and then auto-transfer)
- /static/spider.html — spider-only UI for plans and leases

Dev quickstart
- just up (dev server)
- just test

Two apps layout
- Transfer app (default): `app.main:app` — basic fast transfer endpoints, QUIC/WebRTC/WS/TCP, no spider.
- Spider app (optional): `app_spider.main:app` — enables spider coordinator routes and any background tasks.

How to run
- Transfer app (default):
  - Hypercorn: `PYTHONPATH=. .venv/bin/hypercorn -b 127.0.0.1:8811 app.main:app --reload`
  - Uvicorn: `PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8811 --reload`
- Spider app:
  - Hypercorn: `PYTHONPATH=. .venv/bin/hypercorn -b 127.0.0.1:8811 app_spider.main:app --reload`
  - Uvicorn: `PYTHONPATH=. .venv/bin/uvicorn app_spider.main:app --host 127.0.0.1 --port 8811 --reload`

Modes
- Basic transfer (default): focuses on transfer protocol and endpoints.
  - Run: just up
- Spider-enabled: mounts crawler/coordinator routes at /spider/*.
  - Run: just up-spider (or set PFS_ENABLE_SPIDER=1)

Prod (Podman)
- just prod-image-build
- just prod-run

Notes

Quick IPROG/PVRT test (with PacketFS repo installed in /home/punk/.venv)
- Start this receiver: just up (serves at http://127.0.0.1:8811)
- Generate a blueprint via PacketFS (two options):
  1) Translation daemon watches ./ingest and writes ./iprog/*.iprog.json
     - In /home/punk/Projects/packetfs: just trans-daemon watch_dir="./ingest" out_dir="./iprog" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337" window="65536"
     - Drop a file into ./ingest; it produces ./iprog/<file>.iprog.json
  2) FUSE mount compiles on close (palette or append mode)
     - In /home/punk/Projects/packetfs: just pfsfs-mount mnt="./pfs.mnt" iprog_dir="./iprog" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337" window="65536" embed_pvrt="1" meta_dir="./pfsmeta"
     - cp big.bin ./pfs.mnt/; result in ./iprog/big.bin.iprog.json
- Send to this receiver over WebSocket:
  - In this project: just send-iprog iprog="/path/to/iprog.json" host="127.0.0.1" port="8811"
- Receiver reconstructs windows from BREF against the blob and acknowledges DONE.
- Uses central venv at /home/punk/.venv
- No demo data used; tests use synthetic data
