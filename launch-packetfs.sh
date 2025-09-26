#!/bin/bash
# PacketFS Container Launcher
# Spins up the full PacketFS ecosystem with FUSE, F3, and clustering

set -e

# ASCII Art (no colors/emojis)
echo "
================================================================
     ____            _        _   _____ ____  
    |  _ \ __ _  ___| | _____| |_|  ___/ ___| 
    | |_) / _\` |/ __| |/ / _ \ __| |_  \___ \ 
    |  __/ (_| | (__|   <  __/ |_|  _|  ___) |
    |_|   \__,_|\___|_|\_\___|\__|_|   |____/ 
                                               
    Lightning Fast Transfer with 95% Compression
================================================================
"

INFO="[*]"
SUCCESS="[+]"
ERROR="[!]"
ARROW="-->"

# Check for podman/docker
if command -v podman >/dev/null 2>&1; then
    RUNTIME="podman"
    COMPOSE="podman-compose"
    echo "$SUCCESS Using podman"
elif command -v docker >/dev/null 2>&1; then
    RUNTIME="docker"
    COMPOSE="docker-compose"
    echo "$INFO Using docker"
else
    echo "$ERROR Neither podman nor docker found!"
    exit 1
fi

# Check for compose
if ! command -v $COMPOSE >/dev/null 2>&1; then
    echo "$ERROR $COMPOSE not found!"
    echo "$INFO Install with: pip install podman-compose (or docker-compose)"
    exit 1
fi

# Function to show usage
usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  up       $ARROW Start PacketFS cluster"
    echo "  down     $ARROW Stop PacketFS cluster"
    echo "  build    $ARROW Build container image"
    echo "  logs     $ARROW Show logs"
    echo "  status   $ARROW Show cluster status"
    echo "  shell    $ARROW Enter master container"
    echo "  demo     $ARROW Run demo transfer"
    echo "  clean    $ARROW Clean all data"
    echo ""
    echo "Quick start: $0 up"
}

# Build the container
build_container() {
    echo "$INFO Building PacketFS container..."
    $RUNTIME build -f Containerfile -t packetfs:latest .
    echo "$SUCCESS Container built successfully"
}

# Start the cluster
start_cluster() {
    echo "$INFO Starting PacketFS cluster..."
    
    # Check if already running
    if $RUNTIME ps | grep -q pfs-master; then
        echo "$ERROR PacketFS already running!"
        echo "$INFO Use '$0 down' to stop first"
        exit 1
    fi
    
    # Build if image doesn't exist
    if ! $RUNTIME image exists packetfs:latest 2>/dev/null; then
        build_container
    fi
    
    # Start with compose
    $COMPOSE up -d
    
    echo "$INFO Waiting for services to start..."
    sleep 5
    
    # Check health
    if curl -s http://localhost:8811/health >/dev/null 2>&1; then
        echo "$SUCCESS PacketFS cluster started!"
        echo ""
        echo "================================================================"
        echo "PacketFS is running!"
        echo ""
        echo "Master Node:"
        echo "  Web UI:     http://localhost:8811/static/transfer-v2.html"
        echo "  API:        http://localhost:8811/api"
        echo "  Container:  pfs-master"
        echo ""
        echo "Worker Nodes:"
        echo "  Node 1:     http://localhost:8821"
        echo "  Node 2:     http://localhost:8831"
        echo ""
        echo "Quick Commands:"
        echo "  Enter shell:     $0 shell"
        echo "  View logs:       $0 logs"
        echo "  Run demo:        $0 demo"
        echo "  Stop cluster:    $0 down"
        echo "================================================================"
    else
        echo "$ERROR Failed to start PacketFS!"
        echo "$INFO Check logs with: $0 logs"
        exit 1
    fi
}

# Stop the cluster
stop_cluster() {
    echo "$INFO Stopping PacketFS cluster..."
    $COMPOSE down
    echo "$SUCCESS PacketFS cluster stopped"
}

# Show logs
show_logs() {
    $COMPOSE logs -f
}

# Show status
show_status() {
    echo "$INFO PacketFS Cluster Status"
    echo "========================"
    
    # Check containers
    echo ""
    echo "Containers:"
    $RUNTIME ps --filter "name=pfs-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    # Check health
    echo ""
    echo "Health Check:"
    for port in 8811 8821 8831; do
        if curl -s http://localhost:$port/health >/dev/null 2>&1; then
            echo "  $SUCCESS Port $port: HEALTHY"
        else
            echo "  $ERROR Port $port: DOWN"
        fi
    done
    
    # Check FUSE mounts
    echo ""
    echo "FUSE Mounts:"
    $RUNTIME exec pfs-master mount | grep packetfs || echo "  $INFO No FUSE mounts found"
}

# Enter shell
enter_shell() {
    echo "$INFO Entering PacketFS master container..."
    $RUNTIME exec -it pfs-master /bin/bash
}

# Run demo
run_demo() {
    echo "$INFO Running PacketFS demo..."
    echo ""
    
    # Create test file
    echo "Creating 10MB test file..."
    dd if=/dev/urandom of=/tmp/test_10mb.bin bs=1M count=10 2>/dev/null
    
    # Upload to master
    echo "Uploading to PacketFS..."
    curl -X POST -F "file=@/tmp/test_10mb.bin" http://localhost:8811/api/objects
    
    echo ""
    echo "$SUCCESS Demo complete!"
    echo "$INFO Check the web UI at http://localhost:8811"
    
    # Clean up
    rm /tmp/test_10mb.bin
}

# Clean everything
clean_all() {
    echo "$ERROR This will delete all PacketFS data!"
    echo "Press Ctrl+C to cancel, or wait 5 seconds..."
    sleep 5
    
    echo "$INFO Cleaning PacketFS..."
    $COMPOSE down -v
    $RUNTIME volume prune -f
    echo "$SUCCESS Clean complete"
}

# Main command handler
case "${1:-}" in
    up|start)
        start_cluster
        ;;
    down|stop)
        stop_cluster
        ;;
    build)
        build_container
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    shell)
        enter_shell
        ;;
    demo)
        run_demo
        ;;
    clean)
        clean_all
        ;;
    *)
        usage
        ;;
esac