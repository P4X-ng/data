FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    git \
    pkg-config \
    libpcap-dev \
    net-tools \
    iproute2 \
    tcpdump \
    iperf3 \
    ethtool \
    linux-perf \
    gdb \
    valgrind \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /packetfs

# Copy source files
COPY src/ src/
COPY tests/ tests/
COPY tools/ tools/
COPY setup.py .
COPY requirements.txt .
COPY pytest.ini .

# Create virtual environment and install dependencies
RUN python3 -m venv /packetfs/.venv && \
    /packetfs/.venv/bin/pip install --upgrade pip setuptools wheel && \
    /packetfs/.venv/bin/pip install pytest pytest-cov prometheus_client redis && \
    /packetfs/.venv/bin/pip install -e .

# Set up environment
ENV PATH="/packetfs/.venv/bin:$PATH"
ENV PYTHONPATH="/packetfs/src"

# Add test runner script
RUN echo '#!/bin/bash\n\
set -e\n\
echo "🧪 Running PacketFS test suite in container..."\n\
echo "📋 Environment: $(uname -a)"\n\
echo "🐍 Python: $(python --version)"\n\
echo "📦 PacketFS C extension: $(python -c \"import packetfs._bitpack; print('OK')\" 2>/dev/null && echo \"Available\" || echo \"Not available\")"\n\
echo ""\n\
echo "🏃 Running unit tests..."\n\
pytest tests/test_protocol.py -v\n\
echo ""\n\
echo "📊 Running performance benchmarks..."\n\
python -c "\n\
from tests.test_metrics import BenchmarkSuite\n\
from packetfs.protocol import SyncConfig\n\
suite = BenchmarkSuite()\n\
config = SyncConfig(window_pow2=6, window_crc16=True)\n\
results = suite.run_encoding_benchmark(config, frame_count=500, payload_sizes=[64, 256], tier_mix=[0, 1])\n\
print(f'🚀 Benchmark complete: {len(results)} tests')\n\
for r in results[:2]:\n\
    print(f'  {r.test_name}: {r.frames_per_second:.1f} fps')\n\
"\n\
echo "✅ All tests completed successfully!"' > /usr/local/bin/test-packetfs && \
    chmod +x /usr/local/bin/test-packetfs

# Default command
CMD ["test-packetfs"]

# Labels
LABEL org.opencontainers.image.title="PacketFS Test Environment"
LABEL org.opencontainers.image.description="Containerized testing environment for PacketFS protocol"
LABEL org.opencontainers.image.source="https://github.com/yourusername/packetfs"
