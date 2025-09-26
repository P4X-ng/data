#!/bin/bash
set -e

echo "[OS-Walk] Starting Distributed Operating System..."

# Start Redis for job queues
echo "[OS-Walk] Starting Redis..."
redis-server --daemonize yes --bind 0.0.0.0 --port 6379

# Wait for Redis
sleep 2

# Start packet bridge discovery
echo "[OS-Walk] Starting packet bridge..."
python packet_bridge.py &

# Start OSv executor workers
echo "[OS-Walk] Starting OSv workers..."
python osv_executor.py worker &

# Start network CPU workers  
echo "[OS-Walk] Starting network CPU..."
python -c "from distributed_cpu import DistributedCPU; cpu = DistributedCPU(); cpu.start_workers()" &

# Start F3 web interface
echo "[OS-Walk] Starting F3 web interface..."
cd /app/f3-app
hypercorn -b 0.0.0.0:8811 main:app &

# Wait a bit for services to start
sleep 5

echo "[OS-Walk] All services started!"
echo "[OS-Walk] Web interface: http://localhost:8811"
echo "[OS-Walk] Packet bridges will appear in /net/"
echo "[OS-Walk] Starting integrated shell..."

# Start the integrated shell
exec python integrated_shell.py