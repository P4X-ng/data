#!/usr/bin/env bash
set -euo pipefail
# Env: NAME, SIZE_MB, SEED, PROFILE, SNAPSHOT
VENV_PY="/home/punk/.venv/bin/python"
ROOT_DIR="$(cd "$(dirname "$0")"/../.. && pwd)"
NAME="${NAME:-pfs_vblob_test}"
SIZE_MB="${SIZE_MB:-1024}"
SEED="${SEED:-1337}"
PROFILE="${PROFILE:-orchard}"
SNAPSHOT="${SNAPSHOT:-}"
ARGS=(--name "$NAME" --size-mb "$SIZE_MB" --seed "$SEED" --profile "$PROFILE")
[[ -n "$SNAPSHOT" ]] && ARGS+=(--snapshot "$SNAPSHOT")
exec "$VENV_PY" "$ROOT_DIR/scripts/patterns/blob_build.py" "${ARGS[@]}"
