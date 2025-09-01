#!/bin/bash
# PacketFS File Monitor - For Epic GIF Recording
# "Watch the impossible happen in real-time"

WATCH_FILE=${1:-demo.pfs}
INTERVAL=${2:-1}

echo "🎬 PacketFS File Monitor - Watching: $WATCH_FILE"
echo "📊 Update interval: ${INTERVAL}s"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Function to get file size in human readable format and also in bytes
get_file_info() {
    if [[ -f "$WATCH_FILE" ]]; then
        # Get file size in bytes and human readable
        SIZE_BYTES=$(stat -f%z "$WATCH_FILE" 2>/dev/null || stat -c%s "$WATCH_FILE" 2>/dev/null || echo "0")
        SIZE_HUMAN=$(ls -lh "$WATCH_FILE" 2>/dev/null | awk '{print $5}' || echo "0B")
        
        # Calculate hash (quick version for demo)
        HASH=$(echo "$SIZE_BYTES" | shasum -a 256 | cut -c1-8)
        
        # Get timestamp
        TIMESTAMP=$(date '+%H:%M:%S')
        
        printf "[$TIMESTAMP] %s | %s (%s bytes) | Hash: %s\n" "$WATCH_FILE" "$SIZE_HUMAN" "$SIZE_BYTES" "$HASH"
    else
        TIMESTAMP=$(date '+%H:%M:%S')
        printf "[$TIMESTAMP] %s | NOT FOUND | Hash: --------\n" "$WATCH_FILE"
    fi
}

# Initial display
get_file_info

# Monitor in real-time
while true; do
    sleep $INTERVAL
    get_file_info
done
