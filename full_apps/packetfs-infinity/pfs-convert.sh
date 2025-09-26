#!/bin/bash
# PacketFS File Converter & Sender
# Usage: ./pfs-convert.sh [file] [receiver_host] [receiver_port]

set -euo pipefail

# Configuration
SHARED_DIR="/tmp/pfs-share"
IPROG_DIR="/tmp/pfs-iprog"
META_DIR="/tmp/pfs-meta"
MOUNT_DIR="/tmp/pfs-mount"
BLOB_NAME="pfs_test_blob"
BLOB_SIZE="1073741824"  # 1GB
BLOB_SEED="42"

# Create directories
mkdir -p "$SHARED_DIR" "$IPROG_DIR" "$META_DIR" "$MOUNT_DIR"

# Clean up old mount if exists
fusermount -u "$MOUNT_DIR" 2>/dev/null || true

echo "🚀 Starting PacketFS FUSE mount..."
echo "   Shared folder: $SHARED_DIR"
echo "   IPROG output: $IPROG_DIR"
echo ""

# Start FUSE mount in background
PYTHONPATH=/home/punk/Projects/packetfs/src /home/punk/.venv/bin/python -m packetfs.filesystem.pfsfs_mount \
    --iprog-dir "$IPROG_DIR" \
    --mount "$MOUNT_DIR" \
    --blob-name "$BLOB_NAME" \
    --blob-size "$BLOB_SIZE" \
    --blob-seed "$BLOB_SEED" \
    --meta-dir "$META_DIR" \
    --window 65536 \
    --embed-pvrt &

FUSE_PID=$!

# Wait for mount
echo "Waiting for FUSE mount..."
for i in {1..30}; do
    if mountpoint -q "$MOUNT_DIR"; then
        echo "✅ PacketFS mounted at $MOUNT_DIR"
        break
    fi
    sleep 0.5
done

if ! mountpoint -q "$MOUNT_DIR"; then
    echo "❌ Failed to mount PacketFS"
    exit 1
fi

# Function to convert a file
convert_file() {
    local file="$1"
    local basename=$(basename "$file")
    
    echo "📦 Converting $basename to PacketFS format..."
    cp "$file" "$MOUNT_DIR/$basename"
    
    # Wait for IPROG to be created
    local iprog_file="$IPROG_DIR/${basename}.iprog.json"
    for i in {1..10}; do
        if [ -f "$iprog_file" ]; then
            echo "✅ Created IPROG: $iprog_file"
            
            # Show compression stats
            local original_size=$(stat -c%s "$file")
            local iprog_size=$(stat -c%s "$iprog_file")
            local ratio=$(echo "scale=2; $iprog_size * 100 / $original_size" | bc)
            echo "   Original: $(numfmt --to=iec $original_size)"
            echo "   IPROG: $(numfmt --to=iec $iprog_size) ($ratio% of original)"
            return 0
        fi
        sleep 0.5
    done
    
    echo "❌ Failed to create IPROG for $basename"
    return 1
}

# Function to send IPROG via WebSocket
send_iprog() {
    local iprog_file="$1"
    local host="${2:-localhost}"
    local port="${3:-8811}"
    
    echo "🌐 Sending $(basename "$iprog_file") to $host:$port..."
    
    PYTHONPATH=/home/punk/Projects/packetfs/src /home/punk/.venv/bin/python -m packetfs.tools.arith_send \
        --iprog "$iprog_file" \
        --host "$host" \
        --port "$port"
}

# Main logic
if [ $# -eq 0 ]; then
    echo "Usage modes:"
    echo "  1. Interactive: $0"
    echo "     Place files in $SHARED_DIR and they'll be auto-converted"
    echo ""
    echo "  2. Convert & send: $0 <file> [host] [port]"
    echo "     Converts file and sends to receiver"
    echo ""
    
    echo "📁 Watching $SHARED_DIR for files to convert..."
    echo "   Drop files here and they'll be converted to PacketFS format"
    echo "   IPROGs will be saved to: $IPROG_DIR"
    echo "   Press Ctrl-C to exit"
    echo ""
    
    # Watch for new files
    while true; do
        for file in "$SHARED_DIR"/*; do
            [ -f "$file" ] || continue
            basename=$(basename "$file")
            
            # Skip if already processed
            if [ -f "$IPROG_DIR/${basename}.iprog.json" ]; then
                continue
            fi
            
            convert_file "$file"
        done
        sleep 1
    done
    
elif [ $# -ge 1 ]; then
    # Convert and optionally send a specific file
    FILE="$1"
    HOST="${2:-localhost}"
    PORT="${3:-8811}"
    
    if [ ! -f "$FILE" ]; then
        echo "❌ File not found: $FILE"
        exit 1
    fi
    
    # Convert the file
    if convert_file "$FILE"; then
        # Send if host was provided
        if [ $# -ge 2 ]; then
            iprog_file="$IPROG_DIR/$(basename "$FILE").iprog.json"
            send_iprog "$iprog_file" "$HOST" "$PORT"
        else
            echo ""
            echo "To send this file, run:"
            echo "  $0 send $IPROG_DIR/$(basename "$FILE").iprog.json <host> [port]"
        fi
    fi
fi

# Cleanup on exit
trap "fusermount -u $MOUNT_DIR 2>/dev/null; kill $FUSE_PID 2>/dev/null" EXIT