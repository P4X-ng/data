#!/usr/bin/env bash
# plan_with_hints.sh — Generate hints for a target and run the Orchard planner
#
# Usage:
#   scripts/patterns/plan_with_hints.sh [--target PATH] [--hints PATH] [--kind text|rodata|data] [--ts TIMESTAMP] [--outdir DIR]
#
# Defaults:
#   --target /usr/bin/bash
#   --kind text (only used when synthesizing fallback hints)
#   --ts $(date -u +%Y-%m-%dT%H-%M-%SZ)
#   --outdir logs/patterns/$ts
#   --hints logs/patterns/$ts/$(basename $target).hints.json (if not provided)
#
# Behavior:
# - If scripts/patterns/llvm_findings.sh exists and is executable, it is used to produce hints.
# - Otherwise a trivial single-section hint is synthesized covering the whole file with the given --kind.
# - Then scripts/patterns/run_orchard_plan.sh is invoked with the chosen hints and target.
# - A short summary is printed including any RESULT line and blueprint sizes if present.

set -euo pipefail
shopt -s lastpipe

usage() {
  cat <<'USAGE'
plan_with_hints.sh — Generate hints for a target and run the Orchard planner

Options:
  --target PATH          Target file to plan (default: /usr/bin/bash)
  --hints PATH           Existing hints JSON to use (default: auto-generate)
  --kind KIND            Section kind for fallback hints: text|rodata|data (default: text)
  --ts TIMESTAMP         Timestamp to use for logs dir (default: current UTC)
  --outdir DIR           Output directory for logs (default: logs/patterns/$ts)
  -h|--help              Show this help and exit

Examples:
  scripts/patterns/plan_with_hints.sh --target /usr/bin/bash
  scripts/patterns/plan_with_hints.sh --target /tmp/synth.json --kind rodata
USAGE
}

TARGET="/usr/bin/bash"
HOUT=""
KIND="text"
TS=""
OUTDIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      [[ $# -ge 2 ]] || { echo "--target requires a value" >&2; exit 2; }
      TARGET="$2"; shift 2 ;;
    --hints)
      [[ $# -ge 2 ]] || { echo "--hints requires a value" >&2; exit 2; }
      HOUT="$2"; shift 2 ;;
    --kind)
      [[ $# -ge 2 ]] || { echo "--kind requires a value" >&2; exit 2; }
      KIND="$2"; shift 2 ;;
    --ts)
      [[ $# -ge 2 ]] || { echo "--ts requires a value" >&2; exit 2; }
      TS="$2"; shift 2 ;;
    --outdir)
      [[ $# -ge 2 ]] || { echo "--outdir requires a value" >&2; exit 2; }
      OUTDIR="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    --)
      shift; break ;;
    *)
      echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$TS" ]]; then
  TS=$(date -u +%Y-%m-%dT%H-%M-%SZ)
fi
if [[ -z "$OUTDIR" ]]; then
  OUTDIR="logs/patterns/$TS"
fi
mkdir -p "$OUTDIR"

if [[ -z "$HOUT" ]]; then
  base=$(basename -- "$TARGET")
  HOUT="$OUTDIR/${base}.hints.json"
fi

if [[ ! -f "$TARGET" ]]; then
  echo "Target not found: $TARGET" >&2
  exit 1
fi

# Prefer LLVM wrapper if available; otherwise synthesize a trivial hint covering the file
if [[ -x scripts/patterns/llvm_findings.sh ]]; then
  echo "[plan-with-hints] Generating hints via llvm_findings.sh -> $HOUT"
  if ! scripts/patterns/llvm_findings.sh --bin "$TARGET" --out "$HOUT"; then
    echo "[plan-with-hints] llvm_findings.sh failed; falling back to trivial hints" >&2
  fi
fi

if [[ ! -s "$HOUT" ]]; then
  echo "[plan-with-hints] Synthesizing fallback hints ($KIND) -> $HOUT"
  size=$(stat -c %s "$TARGET")
  # Write minimal valid JSON with careful quoting
  printf '{"sections": [{"name": "%s", "start": 0, "end": %s, "kind": "%s"}]}' "$KIND" "$size" "$KIND" > "$HOUT"
fi

echo "[plan-with-hints] Hints: $HOUT"

# Ensure the orchard runner exists
if [[ ! -x scripts/patterns/run_orchard_plan.sh ]]; then
  echo "scripts/patterns/run_orchard_plan.sh not found or not executable." >&2
  echo "Please build the patterns tooling or invoke the appropriate Just targets (e.g., dev-blob-build, dev-blob-index, dev-plan-file)." >&2
  exit 1
fi

# Run the orchard plan
OUT="$OUTDIR/orchard_plan.out"
echo "[plan-with-hints] Running orchard planner for $TARGET (log: $OUT)"
set +e
scripts/patterns/run_orchard_plan.sh --target "$TARGET" --hints "$HOUT" | tee "$OUT"
rc=${PIPESTATUS[0]}
set -e

# Try to summarize results
if grep -F "[orchard-plan] RESULT" "$OUT" | tail -n1 | sed -n '1p' | read -r line; then
  echo "[plan-with-hints] $line"
fi

# Attempt to extract the final blueprint path (last non-empty line that ends with .json)
blueprint=""
while IFS= read -r ln; do
  blueprint="$ln"
done < <(grep -E "\.json$" "$OUT" | tail -n1)

if [[ -n "$blueprint" && -f "$blueprint" ]]; then
  echo "[plan-with-hints] blueprint=$blueprint"
  if [[ -f "${blueprint%.json}.pbb" ]]; then
    json_sz=$(stat -c %s "$blueprint")
    pbb_sz=$(stat -c %s "${blueprint%.json}.pbb")
    echo "[plan-with-hints] sizes: json_bytes=$json_sz pbb_bytes=$pbb_sz"
  fi
else
  echo "[plan-with-hints] blueprint path not detected from runner output (see $OUT)"
fi

# Ownership fix if run as root
if [[ $(id -u) -eq 0 ]]; then
  chown -R punk:punk "$OUTDIR" 2>/dev/null || true
fi

echo "[plan-with-hints] done (rc=$rc)"
exit "$rc"
