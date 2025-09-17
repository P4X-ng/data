# Smart Proxy Project

A high-performance proxy script that leverages advanced techniques like Cython optimization, GPU-accelerated compression, inline assembly simulations, and multithreaded task execution to optimize traffic forwarding and compression. The project is designed to be scalable and easily deployable on modern infrastructure.

---

## Features

1. **QUIC Proxy Server**:

   - Built with FastAPI and aioquic for high-speed HTTP/3 traffic handling.

2. **GPU-Accelerated Compression**:

   - Utilizes GPU and Zstandard (Zstd) for efficient compression of data streams.

3. **Caching**:

   - Redis-based caching to avoid redundant computations and speed up repetitive requests.

4. **Custom Packet Sending**:

   - Inline assembly simulation using Python's ctypes for raw packet crafting and sending.

5. **Multithreading**:

   - Efficient task execution using ThreadPoolExecutor.

---

## Installation

### Prerequisites

- Python 3.8+
- Ubuntu 20.04 or newer

### Dependencies

Install the required dependencies:

```bash
sudo apt update
sudo apt install -y python3-pip redis-server cython zstd
pip3 install aioquic fastapi uvicorn redis
```

### Project Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/your-repo/smart-proxy.git
   cd smart-proxy
   ```

2. Build the Cython module (optional):

   ```bash
   python3 setup.py build_ext --inplace
   ```

3. Run the script:

   ```bash
   python3 smart_proxy.py
   ```

---

## Usage

1. Start the proxy:

   ```bash
   python3 smart_proxy.py
   ```

2. Send a test request:

   ```bash
   curl -X POST http://127.0.0.1:8888/proxy -d "Test Data"
   ```

---

## Docker Deployment

### Build the Docker Image

Create a Dockerfile:

```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    redis-server zstd cython && apt-get clean

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Compile Cython module
RUN python setup.py build_ext --inplace

# Expose necessary ports
EXPOSE 8888

# Run the script
CMD ["python", "smart_proxy.py"]
```

Build and run the container:

```bash
docker build -t smart_proxy .
docker run -p 8888:8888 smart_proxy
```

---

## System Service Deployment

Create a systemd service file to run the proxy as a background service:

1. Create `/etc/systemd/system/smart_proxy.service`:

   ```plaintext
   [Unit]
   Description=Smart Proxy Service
   After=network.target

   [Service]
   ExecStart=/path/to/python3 /path/to/smart_proxy.py
   WorkingDirectory=/path/to/project
   Restart=always
   User=your-user
   Group=your-group

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable and start the service:

   ```bash
   sudo systemctl enable smart_proxy
   sudo systemctl start smart_proxy
   ```

---

## Testing

- **Performance Benchmarking**: Use tools like `wrk` or `locust` to measure performance.
- **Functionality Testing**: Use `curl` or custom scripts to validate the functionality.

---

## Contributing

Feel free to submit issues or pull requests to improve the project.

---

## License

This project is licensed under the MIT License.

