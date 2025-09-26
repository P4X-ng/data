#!/bin/bash
"""
OS Walk Demo - Show the distributed operating system in action
"""

set -e

echo "OS Walk Demo - Distributed Operating System"
echo "=============================================="

# Configuration
DEMO_DIR="/tmp/oswalk_demo"
CLUSTER_CONFIG="$DEMO_DIR/cluster.json"
MOUNT_POINT="$DEMO_DIR/unified_fs"
WATCH_DIR="$DEMO_DIR/files"
OUTPUT_DIR="$DEMO_DIR/translated"

# Clean up previous demo
echo "Cleaning up previous demo..."
sudo umount "$MOUNT_POINT" 2>/dev/null || true
rm -rf "$DEMO_DIR"

# Setup demo environment
echo "Setting up demo environment..."
mkdir -p "$DEMO_DIR"
mkdir -p "$WATCH_DIR"
mkdir -p "$OUTPUT_DIR"

# Initialize cluster
echo "Initializing cluster..."
cd "$(dirname "$0")/.."
./cli/oswalk --config "$CLUSTER_CONFIG" cluster init --name "demo-cluster" --nodes "localhost"

echo "Cluster initialized:"
cat "$CLUSTER_CONFIG" | jq .

# Create some demo files
echo "Creating demo files..."
echo "Hello from OS Walk!" > "$WATCH_DIR/hello.txt"
echo "#!/bin/bash\necho 'Distributed execution works!'" > "$WATCH_DIR/test_script.sh"
chmod +x "$WATCH_DIR/test_script.sh"

# Create a simple Python script
cat > "$WATCH_DIR/fibonacci.py" << 'EOF'
#!/usr/bin/env python3
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(f"Fibonacci({n}) = {fibonacci(n)}")
EOF

echo "Demo files created:"
ls -la "$WATCH_DIR"

# Start Redis (needed for distributed CPU)
echo "Starting Redis server..."
redis-server --daemonize yes --port 6379 || echo "Redis already running"

# Start file translator in background
echo "Starting file translator..."
./cli/oswalk translate \
    --watch-dirs "$WATCH_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --blob-name "demo_blob" &
TRANSLATOR_PID=$!

# Wait for translation
echo "Waiting for file translation..."
sleep 5

echo "Translated files:"
ls -la "$OUTPUT_DIR"

# Start CPU worker in background
echo "Starting CPU worker..."
./cli/oswalk worker --node-id "demo-node" &
WORKER_PID=$!

# Wait for worker to start
sleep 3

# Show cluster status
echo "Cluster status:"
./cli/oswalk status --verbose

# Submit some jobs
echo "Submitting distributed jobs..."

echo "Job 1: Simple command"
./cli/oswalk job echo "Hello from distributed CPU!" --wait

echo "Job 2: Python script"
./cli/oswalk job python3 "$WATCH_DIR/fibonacci.py" 15 --wait

echo "Job 3: Shell script"
./cli/oswalk job bash "$WATCH_DIR/test_script.sh" --wait

# Mount unified filesystem (in background)
echo "Mounting unified filesystem..."
./cli/oswalk mount "$MOUNT_POINT" &
MOUNT_PID=$!

# Wait for mount
sleep 3

echo "Unified filesystem contents:"
ls -la "$MOUNT_POINT" || echo "Mount not ready yet"

# Show final status
echo "Final cluster status:"
./cli/oswalk status --verbose

echo ""
echo "OS Walk Demo Complete!"
echo "================================"
echo "What we demonstrated:"
echo "  OK Cluster initialization"
echo "  OK Automatic file translation to PacketFS"
echo "  OK Distributed CPU execution via Redis queue"
echo "  OK Unified filesystem overlay (FUSE)"
echo "  OK Multiple machines acting as one"
echo ""
echo "Cleanup:"
echo "  kill $TRANSLATOR_PID $WORKER_PID $MOUNT_PID"
echo "  sudo umount $MOUNT_POINT"
echo "  rm -rf $DEMO_DIR"

# Keep processes running for user to explore
echo "Press Ctrl+C to cleanup and exit..."
trap 'echo "Cleaning up..."; kill $TRANSLATOR_PID $WORKER_PID $MOUNT_PID 2>/dev/null; sudo umount "$MOUNT_POINT" 2>/dev/null; exit 0' INT

wait