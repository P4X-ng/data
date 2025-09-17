#!/usr/bin/env bash
set -euo pipefail

# Wrapper: scan a regular file with pattern_scan.py
# Env toggles:
#   ZLIB=1 LAGS=1 LAGS_SET="1,2,4,8" DELTA=1 DUPES=1 MAGIC=1
# Required args: --path <file>
# Optional args: --win N --k N --mods CSV

VENV_PY="/home/punk/.venv/bin/python"
ROOT_DIR="$(cd "$(dirname "$0")"/../.. && pwd)"
PSCAN="$ROOT_DIR/dev/working/tools/pattern_scan.py"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 --path <file> [--win 4096] [--k 50] [--mods 64,128,512,4096]" >&2
  exit 1
fi

FLAGS=("scan-file")

# Env → flags
[[ "${ZLIB:-0}" != "0" ]] && FLAGS+=("--zlib")
[[ "${LAGS:-0}" != "0" ]] && FLAGS+=("--lags")
[[ -n "${LAGS_SET:-}" ]] && FLAGS+=("--lags-set" "${LAGS_SET}")
[[ "${DELTA:-0}" != "0" ]] && FLAGS+=("--delta")
[[ "${DUPES:-0}" != "0" ]] && FLAGS+=("--dupes")
[[ "${MAGIC:-0}" != "0" ]] && FLAGS+=("--magic")

exec "$VENV_PY" "$PSCAN" "${FLAGS[@]}" "$@"
