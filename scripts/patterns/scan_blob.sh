#!/usr/bin/env bash
set -euo pipefail

# Wrapper: scan a VirtualBlob snapshot with pattern_scan.py
# Env toggles:
#   ZLIB=1 LAGS=1 LAGS_SET="1,2,4,8" DELTA=1 DUPES=1 MAGIC=1 KEEP=1
# Optional args: --name NAME --size-mb N --seed N --win N --k N --mods CSV

VENV_PY="/home/punk/.venv/bin/python"
ROOT_DIR="$(cd "$(dirname "$0")"/../.. && pwd)"
PSCAN="$ROOT_DIR/dev/working/tools/pattern_scan.py"

FLAGS=("scan-blob")

[[ "${KEEP:-0}" != "0" ]] && FLAGS+=("--keep-snapshot")
[[ "${ZLIB:-0}" != "0" ]] && FLAGS+=("--zlib")
[[ "${LAGS:-0}" != "0" ]] && FLAGS+=("--lags")
[[ -n "${LAGS_SET:-}" ]] && FLAGS+=("--lags-set" "${LAGS_SET}")
[[ "${DELTA:-0}" != "0" ]] && FLAGS+=("--delta")
[[ "${DUPES:-0}" != "0" ]] && FLAGS+=("--dupes")
[[ "${MAGIC:-0}" != "0" ]] && FLAGS+=("--magic")

exec "$VENV_PY" "$PSCAN" "${FLAGS[@]}" "$@"
