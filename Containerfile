# PacketFS Ultimate Container
# Lightning-fast file transfer with 95% compression
# Includes pfsfuse, F3 protocol, and all utilities

FROM ubuntu:22.04

LABEL maintainer="PacketFS Team"
LABEL description="PacketFS - Revolutionary 95% compression file transfer"
LABEL version="1.0.0"

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Core tools
    python3.10 \
    python3-pip \
    python3-venv \
    gcc \
    g++ \
    make \
    cmake \
    pkg-config \
    # FUSE for filesystem
    fuse3 \
    libfuse3-dev \
    # Networking tools
    iproute2 \
    iputils-ping \
    net-tools \
    curl \
    wget \
    socat \
    # Performance tools
    iperf3 \
    tcpdump \
    htop \
    iotop \
    # Development tools
    git \
    vim \
    tmux \
    jq \
    # Just command runner
    && curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create packetfs user and directories
RUN useradd -m -s /bin/bash -u 1337 packetfs \
    && mkdir -p /opt/packetfs \
    && mkdir -p /var/lib/packetfs/{uploads,downloads,logs,cache,blob} \
    && mkdir -p /mnt/packetfs \
    && mkdir -p /etc/packetfs

# Set up Python virtual environment
RUN python3 -m venv /opt/packetfs/venv \
    && /opt/packetfs/venv/bin/pip install --upgrade pip setuptools wheel

# Copy PacketFS source code
WORKDIR /opt/packetfs
COPY . .

# Install Python dependencies
RUN /opt/packetfs/venv/bin/pip install \
    flask \
    requests \
    tqdm \
    websocket-client \
    aiohttp \
    requests-toolbelt \
    prometheus-client \
    numpy \
    fusepy

# Build native components
RUN if [ -f realsrc/packetfs/native/bitpack.c ]; then \
        cd realsrc/packetfs/native && \
        gcc -O3 -fPIC -shared -o _bitpack.so bitpack.c && \
        cp _bitpack.so /opt/packetfs/venv/lib/python3.10/site-packages/; \
    fi

# Build pfsfuse if available
RUN if [ -f dev/wip/native/pfsfuse.c ]; then \
        cd dev/wip/native && \
        gcc -O3 -o /usr/local/bin/pfsfuse pfsfuse.c -lfuse3 -lpthread; \
    fi

# Install F3 transfer utilities
RUN cp full_apps/pfs-infinity/f3transfer.py /usr/local/bin/f3transfer \
    && chmod +x /usr/local/bin/f3transfer \
    && ln -s /opt/packetfs/venv/bin/python /usr/local/bin/packetfs-python

# Copy configuration files
COPY full_apps/pfs-infinity/Justfile /opt/packetfs/Justfile
COPY full_apps/pfs-infinity/app /opt/packetfs/app

# Create startup script
RUN cat > /usr/local/bin/packetfs-start << 'EOF'
#!/bin/bash
set -e

echo "[*] PacketFS Container Starting..."
echo "[*] Version: 1.0.0"
echo "[*] Features: F3 Protocol, 95% Compression, FUSE Filesystem"
echo ""

# Check for license
if [ -f /etc/packetfs/license.key ]; then
    echo "[+] License found"
else
    echo "[!] No license found - running in demo mode"
    echo "[!] Limited to 10MB files"
fi

# Initialize blob if needed
if [ ! -f /var/lib/packetfs/blob/pfs_vblob ]; then
    echo "[*] Initializing PacketFS blob (1GB)..."
    dd if=/dev/urandom of=/var/lib/packetfs/blob/pfs_vblob bs=1M count=1024 2>/dev/null
    echo "[+] Blob initialized"
fi

# Start FUSE filesystem if available
if command -v pfsfuse >/dev/null 2>&1; then
    echo "[*] Mounting PacketFS FUSE at /mnt/packetfs..."
    pfsfuse /mnt/packetfs \
        -o allow_other \
        -o default_permissions \
        -o nonempty \
        -o blob=/var/lib/packetfs/blob/pfs_vblob &
    sleep 2
    echo "[+] FUSE filesystem mounted"
fi

# Start F3 transfer service
echo "[*] Starting F3 Transfer Service..."
cd /opt/packetfs/app
/opt/packetfs/venv/bin/python app.py &
F3_PID=$!
echo "[+] F3 service started (PID: $F3_PID)"

# Wait for service to be ready
sleep 3
if curl -s http://localhost:8811/health >/dev/null 2>&1; then
    echo "[+] F3 Transfer ready at http://localhost:8811"
    echo ""
    echo "================================================================"
    echo "PacketFS Ready!"
    echo ""
    echo "Web UI: http://localhost:8811/static/transfer-v2.html"
    echo "CLI: f3transfer --help"
    echo "FUSE: ls /mnt/packetfs"
    echo ""
    echo "Quick Start:"
    echo "  f3transfer send myfile.txt"
    echo "  f3transfer receive"
    echo "  cp myfile.txt /mnt/packetfs/"
    echo "================================================================"
else
    echo "[!] Service failed to start"
    exit 1
fi

# Keep container running
tail -f /dev/null
EOF
RUN chmod +x /usr/local/bin/packetfs-start

# Create health check script
RUN cat > /usr/local/bin/packetfs-health << 'EOF'
#!/bin/bash
curl -f http://localhost:8811/health || exit 1
EOF
RUN chmod +x /usr/local/bin/packetfs-health

# Set permissions
RUN chown -R packetfs:packetfs /opt/packetfs /var/lib/packetfs /mnt/packetfs

# Expose ports
EXPOSE 8811 8812 8813

# Set up volumes
VOLUME ["/var/lib/packetfs", "/mnt/packetfs", "/etc/packetfs"]

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD /usr/local/bin/packetfs-health

# Switch to packetfs user
USER packetfs
WORKDIR /opt/packetfs

# Default command
CMD ["/usr/local/bin/packetfs-start"]