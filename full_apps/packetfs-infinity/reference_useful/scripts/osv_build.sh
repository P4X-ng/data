#!/usr/bin/env bash
set -euo pipefail

# Build an OSv image containing the Rust spider agent and a minimal startup
# Requirements:
# - OSV_ROOT env pointing at OSv source checkout
# - cargo available to build the agent
# - qemu-img for image handling (usually installed)

IMG="spider-osv.img"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --img) IMG="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "${OSV_ROOT:-}" ]; then
  echo "OSV_ROOT not set; please export OSV_ROOT to OSv source path" >&2
  exit 1
fi
if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo not found; install Rust: https://rustup.rs" >&2
  exit 1
fi

# Build Rust agent
( cd osv/agent && cargo build --release )
AGENT_BIN="$(pwd)/osv/agent/target/release/spider-agent"
[ -x "$AGENT_BIN" ] || { echo "agent binary missing: $AGENT_BIN" >&2; exit 1; }

# Prepare OSv appfs directory
APPDIR="$OSV_ROOT/apps/spider-agent"
mkdir -p "$APPDIR"
cp -f "$AGENT_BIN" "$APPDIR/spider-agent"
cat > "$APPDIR/manifest.json" <<'EOF'
{
  "name": "spider-agent",
  "version": "0.1",
  "binary": "/spider-agent",
  "args": [],
  "environment": {
    "COORD_URL": "http://127.0.0.1:8811",
    "SPIDER_LEASE_N": "25",
    "SPIDER_UA": "pfs-spider-osv"
  }
}
EOF

# Build OSv image with the app
( cd "$OSV_ROOT" && \
  ./scripts/build image=spider-agent -j )

# Copy out the produced image
# Depending on OSv config, the output image may be at build/last/usr.img or build/last/loader.img
OUT1="$OSV_ROOT/build/last/usr.img"
OUT2="$OSV_ROOT/build/last/loader.img"
if [ -f "$OUT1" ]; then
  cp -f "$OUT1" "$IMG"
elif [ -f "$OUT2" ]; then
  cp -f "$OUT2" "$IMG"
else
  echo "Could not find OSv output image in $OSV_ROOT/build/last" >&2
  exit 1
fi

echo "Built OSv image: $IMG"
