#!/usr/bin/env bash
set -euo pipefail

# Quickstart: PacketFS-native container with translated binaries
# This brings up the full stack: container, Caddy proxy, and verification

echo "
╔══════════════════════════════════════════════════╗
║  PacketFS Native Container - Quickstart          ║
║  Packets ARE execution. Files ARE formulas.      ║
╚══════════════════════════════════════════════════╝
"

# Check prerequisites
check_deps() {
    local missing=()
    command -v podman >/dev/null || missing+=("podman")
    command -v caddy >/dev/null || missing+=("caddy")
    command -v just >/dev/null || missing+=("just")
    
    if [ ${#missing[@]} -gt 0 ]; then
        echo "Missing dependencies: ${missing[*]}"
        echo "Install with:"
        echo "  sudo apt install podman caddy"
        echo "  cargo install just"
        exit 1
    fi
}

# Create Caddyfile for local development
create_caddyfile() {
    cat > Caddyfile << 'EOF'
{
    servers {
        timeouts read_body 30s
    }
}

# Local HTTPS with internal CA
pfs.localhost {
    tls internal
    encode zstd gzip
    
    reverse_proxy 127.0.0.1:8811 {
        header_up X-Forwarded-Proto {scheme}
        header_up X-Real-IP {remote_host}
    }
    
    # Health endpoint passthrough
    handle /health {
        reverse_proxy 127.0.0.1:8811
    }
}

# Plain HTTP for quick dev
:8080 {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8811
}
EOF
    echo "[PFS] Created Caddyfile"
}

# Build container
build_container() {
    echo "[PFS] Building PacketFS-native container..."
    just pfs build || {
        echo "[PFS] Build failed. Trying from repo root..."
        cd ../.. && podman build -t packetfs/pfs-native:latest \
            -f full_apps/pfs-infinity/containers/pfs-native/Containerfile .
        cd - >/dev/null
    }
}

# Start services
start_services() {
    echo "[PFS] Starting services..."
    
    # Stop any existing containers
    podman stop pfs-native 2>/dev/null || true
    podman rm pfs-native 2>/dev/null || true
    
    # Start PacketFS-native container
    echo "[PFS] Starting container..."
    just pfs run || {
        podman run -d --name pfs-native \
            --privileged \
            --device /dev/fuse \
            -p 8811:8811 \
            packetfs/pfs-native:latest
    }
    
    # Start Caddy
    echo "[PFS] Starting Caddy..."
    if pgrep -x caddy >/dev/null; then
        echo "[PFS] Caddy already running, reloading config..."
        caddy reload --config Caddyfile
    else
        caddy start --config Caddyfile
    fi
    
    # Wait for services
    echo "[PFS] Waiting for services to be ready..."
    for i in {1..30}; do
        if curl -s http://127.0.0.1:8811/health >/dev/null 2>&1; then
            echo "[PFS] Services are up!"
            break
        fi
        sleep 1
    done
}

# Verify setup
verify_setup() {
    echo ""
    echo "[PFS] Verification:"
    
    # Check container
    if podman ps | grep -q pfs-native; then
        echo "  ✓ Container running"
    else
        echo "  ✗ Container not running"
    fi
    
    # Check health endpoint
    if curl -s http://127.0.0.1:8811/health | jq -e '.status == "healthy"' >/dev/null 2>&1; then
        echo "  ✓ Health endpoint responding"
    else
        echo "  ✗ Health endpoint not responding"
    fi
    
    # Check Caddy proxy
    if curl -s http://127.0.0.1:8080/health >/dev/null 2>&1; then
        echo "  ✓ Caddy proxy working (HTTP)"
    else
        echo "  ✗ Caddy proxy not working"
    fi
    
    # Show access URLs
    echo ""
    echo "[PFS] Access URLs:"
    echo "  Direct:  http://127.0.0.1:8811"
    echo "  Caddy:   http://127.0.0.1:8080"
    echo "  Secure:  https://pfs.localhost (trust Caddy's cert)"
    
    # Show container logs
    echo ""
    echo "[PFS] Container logs (last 10 lines):"
    podman logs --tail 10 pfs-native 2>&1 || true
}

# Test PacketFS mount inside container
test_pfs_mount() {
    echo ""
    echo "[PFS] Testing PacketFS mount inside container..."
    podman exec pfs-native bash -c '
        if mountpoint -q /pfs/mount; then
            echo "  ✓ PacketFS mounted at /pfs/mount"
            ls -la /pfs/mount/ 2>/dev/null | head -5 || true
        else
            echo "  ✗ PacketFS not mounted (FUSE may be disabled)"
        fi
        
        if [ -d /pfs/iprog ]; then
            echo "  ✓ IPROGs present:"
            ls -1 /pfs/iprog/*.iprog.json 2>/dev/null | head -3 || echo "    (none yet)"
        fi
    '
}

# Main flow
main() {
    cd "$(dirname "$0")/.."
    
    echo "[PFS] Starting from: $(pwd)"
    
    check_deps
    create_caddyfile
    build_container
    start_services
    verify_setup
    test_pfs_mount
    
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  PacketFS Native Container - Ready!              ║"
    echo "║                                                   ║"
    echo "║  Shell into container:                           ║"
    echo "║    just pfs shell                                 ║"
    echo "║                                                   ║"
    echo "║  Test compute:                                   ║"
    echo "║    curl http://127.0.0.1:8811/health            ║"
    echo "║                                                   ║"
    echo "║  Stop everything:                                ║"
    echo "║    just pfs stop                                 ║"
    echo "║    caddy stop                                    ║"
    echo "╚══════════════════════════════════════════════════╝"
}

# Run
main "$@"