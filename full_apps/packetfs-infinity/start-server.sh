#!/bin/bash
# Start PacketFS Infinity server container

set -e

echo "Starting PacketFS Infinity server..."

# Stop any existing container
podman stop pfs-infinity 2>/dev/null || true
podman rm pfs-infinity 2>/dev/null || true

# Generate self-signed certificate if it doesn't exist
CERT_DIR="${PWD}/certs"
if [ ! -f "$CERT_DIR/cert.pem" ]; then
    echo "Generating self-signed TLS certificate..."
    mkdir -p "$CERT_DIR"
    openssl req -x509 -newkey rsa:4096 -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" \
        -days 365 -nodes -subj "/C=US/ST=State/L=City/O=PacketFS/CN=localhost"
fi

# Run the container with proper volume mounts and environment
podman run -d \
    --name pfs-infinity \
    --security-opt label=disable \
    -p 8811:8811 \
    -v "${PWD}/app:/app:ro" \
    -v "${PWD}/certs:/certs:ro" \
    -v "${PWD}/packetfs:/app/packetfs:ro" \
    -v /tmp/pfs-data:/tmp/pfs-data:rw \
    -e PFS_AUTH_ENABLED=0 \
    -e PFS_WS_CHANNELS=10 \
    -e PFS_BLOB_NAME=pfs_test_blob \
    -e PFS_BLOB_SIZE=1073741824 \
    -e PFS_BLOB_SEED=42 \
    -e TLS_CERT=/certs/cert.pem \
    -e TLS_KEY=/certs/key.pem \
    localhost/packetfs/pfs-infinity:latest \
    bash -c "cd /app && /opt/venv/bin/hypercorn core.main:app --bind 0.0.0.0:8811 --certfile /certs/cert.pem --keyfile /certs/key.pem --access-logfile - --error-logfile -"

# Wait for server to start
echo "Waiting for server to start..."
for i in {1..30}; do
    if curl -k -s https://localhost:8811/health >/dev/null 2>&1; then
        echo "Server is running at https://localhost:8811"
        echo ""
        echo "Test with: /home/punk/.venv/bin/python test_pfs_simple.py /tmp/test_10mb.dat"
        exit 0
    fi
    sleep 1
done

echo "Server failed to start. Check logs with: podman logs pfs-infinity"
exit 1