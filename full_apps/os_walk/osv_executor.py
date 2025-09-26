#!/usr/bin/env python3
"""
OSv Container Executor - Lightweight execution via Redis queue
Integrates with packet bridge for seamless remote execution
"""
import redis
import json
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional
import uuid
import time

class OSvExecutor:
    def __init__(self, redis_host="localhost", redis_port=6379):
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.node_id = f"osv-{uuid.uuid4().hex[:8]}"
        
    def submit_job(self, command: str, cwd: str = "/", env: Dict[str, str] = None, 
                   target_node: Optional[str] = None) -> str:
        """Submit job to OSv execution queue"""
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        
        job = {
            "id": job_id,
            "command": command,
            "cwd": cwd,
            "env": env or {},
            "target_node": target_node,
            "submitted_by": self.node_id,
            "submitted_at": time.time(),
            "status": "queued"
        }
        
        # Queue for specific node or any available
        queue_name = f"osv:jobs:{target_node}" if target_node else "osv:jobs:any"
        self.redis.lpush(queue_name, json.dumps(job))
        self.redis.hset(f"osv:job:{job_id}", mapping=job)
        
        print(f"Submitted job {job_id} to {queue_name}")
        return job_id
    
    def execute_local(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute job locally in OSv container"""
        job_id = job_data["id"]
        command = job_data["command"]
        cwd = job_data.get("cwd", "/")
        env = job_data.get("env", {})
        
        # Update job status
        self.redis.hset(f"osv:job:{job_id}", "status", "running")
        self.redis.hset(f"osv:job:{job_id}", "worker_node", self.node_id)
        
        try:
            # Create OSv container for execution
            container_name = f"osv-exec-{job_id}"
            
            # Run in OSv container (lightweight unikernel)
            osv_cmd = [
                "podman", "run", "--rm", "--name", container_name,
                "-w", cwd,
                "osv:latest",  # OSv unikernel image
                "/bin/sh", "-c", command
            ]
            
            # Add environment variables
            for key, value in env.items():
                osv_cmd.insert(-3, "-e")
                osv_cmd.insert(-3, f"{key}={value}")
            
            result = subprocess.run(
                osv_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            job_result = {
                "status": "completed" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "completed_at": time.time()
            }
            
        except subprocess.TimeoutExpired:
            job_result = {
                "status": "timeout",
                "returncode": -1,
                "stdout": "",
                "stderr": "Job timed out after 5 minutes",
                "completed_at": time.time()
            }
        except Exception as e:
            job_result = {
                "status": "error",
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "completed_at": time.time()
            }
        
        # Update job with results
        self.redis.hset(f"osv:job:{job_id}", mapping=job_result)
        return job_result
    
    def worker_loop(self):
        """Main worker loop - processes jobs from Redis queue"""
        print(f"OSv worker {self.node_id} started")
        
        while True:
            try:
                # Check for jobs targeted at this node first
                job_data = self.redis.brpop([
                    f"osv:jobs:{self.node_id}",  # Node-specific jobs
                    "osv:jobs:any"              # Any available jobs
                ], timeout=5)
                
                if job_data:
                    queue_name, job_json = job_data
                    job = json.loads(job_json)
                    
                    print(f"Processing job {job['id']}: {job['command']}")
                    result = self.execute_local(job)
                    print(f"Job {job['id']} {result['status']}")
                
            except KeyboardInterrupt:
                print(f"Worker {self.node_id} stopping...")
                break
            except Exception as e:
                print(f"Worker error: {e}")
                time.sleep(1)
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status and results"""
        return self.redis.hgetall(f"osv:job:{job_id}")
    
    def wait_for_job(self, job_id: str, timeout: int = 60) -> Dict[str, Any]:
        """Wait for job completion"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_job_status(job_id)
            if status.get("status") in ["completed", "failed", "timeout", "error"]:
                return status
            time.sleep(0.5)
        
        return {"status": "timeout", "error": "Wait timeout exceeded"}

def main():
    import sys
    
    executor = OSvExecutor()
    
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        # Run as worker
        executor.worker_loop()
    else:
        # Submit a test job
        job_id = executor.submit_job("echo 'Hello from OSv container!'")
        result = executor.wait_for_job(job_id)
        print(f"Result: {result}")

if __name__ == "__main__":
    main()