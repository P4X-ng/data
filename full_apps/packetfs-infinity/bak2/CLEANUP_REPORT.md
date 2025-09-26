# Cleanup plan (proposed)

This document lists bulky, legacy, or developer-only artifacts we can move to `bak/` (archive) or `utils/` (still useful but not core) to keep the repo lean and human-ingestible. Nothing below is required by the current build/run path for the arithmetic-first demo and SPA at `/`.

If you rely on any of these, say the word and I’ll keep or re-home them appropriately.

## Candidates to archive in bak/

- Top-level release archives and vendor tarballs:
  - `pfs-infinity.tar.gz`
  - `just-mcp-v0.2.0-x86_64-unknown-linux-gnu.tar.gz`
- Conversational and historical notes:
  - `convo.txt`
  - `README.old.md`
- Old references and experiments:
  - `ref/` (old-justfiles, old-scripts, kube-stuff, spider-stuff)
  - `new_optimize/` (empty dir)
- Edge compute playground (not used by core SPA/WS arithmetic flow):
  - `edge-compute/` (Cloudflare worker, wrangler.toml, server script, assorted demos)
- VM/unikernel experiments (not in current container build or Justfile path):
  - `VMKit/`
  - `osv/`
- Bench/test logs and caches:
  - `.benchmarks/`, `test-results/`, `.pytest_cache/`

## Candidates to keep but re-home in utils/

- CLI helper scripts that are optional locally but also copied into image during build:
  - `scripts/pfcp`, `scripts/pfcp-ssh`, `scripts/pfcp-rsync`, `scripts/pfcp-smart`, `scripts/pfs` (these are referenced by Containerfile; they will remain in-place for builds, but we can mirror curated copies in `utils/` for easier discovery)
- Misc helpers with value but not tied to the arithmetic demo:
  - `scripts/transfer/` (installer and dispatcher)
  - `scripts/quickstart-pfs.sh`

Note: For anything the container `Containerfile` COPY’s directly from `scripts/`, we will not move the source path. Instead we’ll add a curated copy/README in `utils/` pointing to the canonical script.

## Keep in place (actively used)

- `app/` (FastAPI backend, SPA in `app/static/transfer-v2.html`, TS lib in `app/web/pfs-arith`)
- `containers/backend/` (Containerfile and startup)
- `Justfile`, `WARP.md`, `requirements.txt`, `package.json` (project entrypoints)
- `vendor/packetfs` (vendored protocol subset)

## Next steps

- On approval, I’ll:
  1) Create `bak/` and move the archive/history/experiments listed above.
  2) Create `utils/` with a short README and curated pointers to the most useful scripts.
  3) Re-run a quick build (TS lib + container) to confirm no accidental breakage.

## Consolidation done (core/)

- Moved actively used routers into `app/core/routes/` and left import-compatible shims:
  - Transfers: `app/core/routes/transfers.py` is canonical; `app/routes/transfers.py` re-exports `router`.
  - Objects: `app/core/routes/objects.py` is canonical; `app/routes/objects.py` re-exports `router`.
  - Transfer WS: `app/core/routes/transfer_ws.py` is canonical; `app/routes/transfer_ws.py` re-exports `router`.
  - Browse WS: `app/core/routes/browse_ws.py` is canonical; `app/routes/browse_ws.py` re-exports registrar.
  - Cluster WS: `app/core/routes/cluster_ws.py` is canonical; `app/routes/cluster_ws.py` re-exports registrar and bg starter.
- Auth stack consolidated under `app/core/auth/` with `app/core/routes/auth.py`, and shims left in `app/auth/*` and `app/routes/auth.py`.
- App bootstrap updated to import from core routers directly.

- Restore instructions: Move the archived folder/file back to repo root, preserving relative paths, or adjust references in doc/scripts accordingly.

---
Generated on: 2025-09-23
