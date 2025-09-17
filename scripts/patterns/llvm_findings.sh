#!/usr/bin/env bash
set -euo pipefail

# Wrapper: correlate entropy with ELF sections and instruction mnemonics
# Args: --scan-dir <dir> --bin <binary> [--win 4096]

VENV_PY="/home/punk/.venv/bin/python"
ROOT_DIR="$(cd "$(dirname "$0")"/../.. && pwd)"
LFIND="$ROOT_DIR/dev/working/tools/llvm_findings.py"

exec "$VENV_PY" "$LFIND" "$@"
