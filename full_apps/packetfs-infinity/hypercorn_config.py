"""
Hypercorn configuration for PacketFS Infinity
Optimized for large file uploads and high performance
"""

bind = ["0.0.0.0:443"]
certfile = "./certs/server.crt"
keyfile = "./certs/server.key"

# Worker configuration
worker_class = "asyncio"
workers = 4
worker_connections = 1000

# Timeouts (in seconds)
keep_alive_timeout = 120
graceful_timeout = 60

# Large file support
h11_max_incomplete_size = 16 * 1024 * 1024  # 16MB for headers
h2_max_inbound_frame_size = 16 * 1024 * 1024  # 16MB frames
h2_max_concurrent_streams = 100

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Security
server_names = ["localhost", "packetfs.local"]

# No request limits for large files
max_requests = 0
max_requests_jitter = 0