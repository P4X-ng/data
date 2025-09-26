#!/bin/bash
set -e

echo "[PFS] Initializing PacketFS-native container..."

# Allow FUSE in container (requires --privileged or --device /dev/fuse)
if [ ! -c /dev/fuse ]; then
    echo "[PFS] Warning: /dev/fuse not available. Run with --privileged or --device /dev/fuse"
fi

# Mount PacketFS as overlay if FUSE is available
if [ -c /dev/fuse ]; then
    echo "[PFS] Mounting PacketFS at /pfs/mount..."
    python -m packetfs.filesystem.pfsfs_mount \
        --iprog-dir /pfs/iprog \
        --mount /pfs/mount \
        --blob-name pfs_core \
        --blob-size 268435456 \
        --blob-seed 1337 \
        --window 65536 \
        --meta-dir /pfs/meta \
        --foreground false &
    
    # Wait for mount
    for i in {1..30}; do
        if mountpoint -q /pfs/mount; then
            echo "[PFS] PacketFS mounted successfully"
            break
        fi
        sleep 0.5
    done
    
    # Optional: overlay PacketFS over system dirs (experimental)
    if [ "${PFS_OVERLAY}" = "1" ]; then
        echo "[PFS] Setting up overlay mounts (experimental)..."
        # This would use overlayfs to layer PacketFS under system dirs
        # Requires careful handling to not break the container
    fi
fi

# Start the pfs-infinity server
echo "[PFS] Starting pfs-infinity server on port 8811..."
exec hypercorn -b 0.0.0.0:8811 app.main:app
