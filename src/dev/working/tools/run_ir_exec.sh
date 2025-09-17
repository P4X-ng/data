#!/usr/bin/env bash
set -euo pipefail

# Helper to run the production IR executor with clean argument handling.
# Usage: run_ir_exec.sh <ll|ll=...> <mode|mode=...> <windows|windows=...>
#   ll: path to .ll file
#   mode: analyze|execute|both
#   windows: 0|1 (include --windows when 1)

ll_in="${1:-dev/working/samples/llvm/compute/hello_world.ll}"
mode_in="${2:-both}"
windows_in="${3:-1}"

case "$ll_in" in ll=*) ll_in="${ll_in#ll=}" ;; esac
case "$mode_in" in mode=*) mode_in="${mode_in#mode=}" ;; esac
case "$windows_in" in windows=*) windows_in="${windows_in#windows=}" ;; esac

LL_ABS="$ll_in"
# Allow relative paths
if [ ! -e "$LL_ABS" ]; then
  echo "Error: IR file not found: $LL_ABS" >&2
  exit 2
fi

# Execute with proper environment (PYTHONPATH) set
if [ "$windows_in" = "1" ]; then
  PYTHONPATH=realsrc exec /home/punk/.venv/bin/python dev/working/tools/ir_exec.py "$LL_ABS" --mode "$mode_in" --windows
else
  PYTHONPATH=realsrc exec /home/punk/.venv/bin/python dev/working/tools/ir_exec.py "$LL_ABS" --mode "$mode_in"
fi

