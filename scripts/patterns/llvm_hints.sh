#!/usr/bin/env bash
set -euo pipefail
# llvm_hints.sh -- generate a lightweight hints JSON for a native binary
# Usage: scripts/patterns/llvm_hints.sh --target /usr/bin/bash --out logs/patterns/<ts>/bash.hints.json
# Requires: readelf (binutils) and optionally llvm-objdump (if present for future extensions)

ROOT_DIR="$(cd "$(dirname "$0")"/../.. && pwd)"
VENV_PY="/home/punk/.venv/bin/python"
TARGET=""
OUT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --target) shift; TARGET="$1";;
    --out) shift; OUT="$1";;
    *) echo "[warn] unknown arg: $1";;
  esac
  shift || true
done

if [ -z "$TARGET" ] || [ -z "$OUT" ]; then
  echo "Usage: $0 --target <path> --out <hints.json>" >&2
  exit 2
fi

# Collect section table via readelf -S (file offsets and sizes)
READelf_JSON=$(mktemp)
readelf -W -S "$TARGET" > "$READelf_JSON"

# Optionally collect disassembly (not yet parsed here, but left for future)
OBJDUMP_TXT=$(mktemp)
if command -v llvm-objdump >/dev/null 2>&1; then
  llvm-objdump -d "$TARGET" > "$OBJDUMP_TXT" || true
else
  : > "$OBJDUMP_TXT"
fi

# Parse and emit hints.json via python helper
"$VENV_PY" "$ROOT_DIR/scripts/patterns/llvm_hints.py" \
  --readelf "$READelf_JSON" --objdump "$OBJDUMP_TXT" --out "$OUT"

rm -f "$READelf_JSON" "$OBJDUMP_TXT"
echo "hints: $OUT"
