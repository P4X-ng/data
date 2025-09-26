#!/usr/bin/env python3
"""
Distributed CPU - Redis queue-based distributed execution
All cluster CPUs available as one compute pool
"""

import os
import json
import time
import uuid
import subprocess
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import redis

@dataclass
class Job:
    job_id: str
    command: List[str]
    cwd: str
    env: Dict[str, str]
    priority: int = 1
    timeout: int = 300
    created_at: float = 0.0
    node_id: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None

@dataclass
class Node:
    node_id: str
    hostname: str
    cpu_count: int
    load_avg: float
    memory_mb: int
    last_heartbeat: float
    active_jobs: int = 0
    healthy: bool = True

class DistributedCPU:
    """Distributed CPU pool using Redis queues"""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, node_id: Optional[str] = None):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.node_id = node_id or f"node-{uuid.uuid4().hex[:8]}"
        self.hostname = os.uname().nodename
        self.running = False
        self.active_jobs: Dict[str, subprocess.Popen] = {}
        self.lock = threading.RLock()
        
        # Queue names
        self.job_queue = "oswalk:jobs:pending"
        self.result_queue = "oswalk:jobs:results"
        self.heartbeat_key = "oswalk:nodes:heartbeat"
        self.node_key = f"oswalk:nodes:{self.node_id}"
        
        print(f"[CPU] Distributed CPU initialized: {self.node_id} on {self.hostname}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get current system information"""
        try:
            # CPU count
            cpu_count = os.cpu_count() or 1
            
            # Load average
            load_avg = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.0
            
            # Memory info (Linux)
            memory_mb = 1024  # Default
            try:
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            memory_mb = int(line.split()[1]) // 1024
                            break
            except:
                pass
            
            return {
                'cpu_count': cpu_count,
                'load_avg': load_avg,
                'memory_mb': memory_mb,
                'active_jobs': len(self.active_jobs)
            }
        except Exception as e:
            print(f"Error getting system info: {e}")
            return {'cpu_count': 1, 'load_avg': 0.0, 'memory_mb': 1024, 'active_jobs': 0}
    
    def register_node(self):
        """Register this node in the cluster"""
        sys_info = self.get_system_info()
        node = Node(
            node_id=self.node_id,
            hostname=self.hostname,
            cpu_count=sys_info['cpu_count'],
            load_avg=sys_info['load_avg'],
            memory_mb=sys_info['memory_mb'],
            last_heartbeat=time.time(),
            active_jobs=sys_info['active_jobs']
        )
        
        # Store node info
        self.redis_client.hset(self.node_key, mapping=asdict(node))
        self.redis_client.expire(self.node_key, 120)  # Expire in 2 minutes
        
        # Add to heartbeat set
        self.redis_client.zadd(self.heartbeat_key, {self.node_id: time.time()})
    
    def submit_job(self, command: List[str], cwd: str = "/tmp", env: Optional[Dict[str, str]] = None, priority: int = 1, timeout: int = 300) -> str:
        """Submit a job to the distributed queue"""
        job_id = f"job-{uuid.uuid4().hex}"
        
        job = Job(
            job_id=job_id,
            command=command,
            cwd=cwd,
            env=env or {},
            priority=priority,
            timeout=timeout,
            created_at=time.time()
        )
        
        # Add to priority queue (higher priority = lower score)
        self.redis_client.zadd(self.job_queue, {json.dumps(asdict(job)): -priority})
        
        print(f"[JOB] Submitted job {job_id}: {' '.join(command)}")
        return job_id
    
    def get_job_result(self, job_id: str, timeout: int = 60) -> Optional[Dict[str, Any]]:
        """Get job result (blocking)"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result_key = f"oswalk:job:result:{job_id}"
            result_data = self.redis_client.get(result_key)
            
            if result_data:
                return json.loads(result_data)
            
            time.sleep(0.5)
        
        return None
    
    def execute_job(self, job: Job) -> Dict[str, Any]:
        """Execute a job locally"""
        print(f"[RUN] Executing job {job.job_id}: {' '.join(job.command)}")
        
        start_time = time.time()
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(job.env)
            
            # Execute command
            process = subprocess.Popen(
                job.command,
                cwd=job.cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Store active job
            with self.lock:
                self.active_jobs[job.job_id] = process
            
            # Wait for completion
            stdout, stderr = process.communicate(timeout=job.timeout)
            
            # Remove from active jobs
            with self.lock:
                self.active_jobs.pop(job.job_id, None)
            
            duration = time.time() - start_time
            
            result = {
                'job_id': job.job_id,
                'node_id': self.node_id,
                'status': 'completed' if process.returncode == 0 else 'failed',
                'return_code': process.returncode,
                'stdout': stdout,
                'stderr': stderr,
                'duration': duration,
                'completed_at': time.time()
            }
            
            print(f"[OK] Job {job.job_id} completed in {duration:.2f}s (exit {process.returncode})")
            return result
            
        except subprocess.TimeoutExpired:
            with self.lock:
                process = self.active_jobs.pop(job.job_id, None)
                if process:
                    process.kill()
            
            result = {
                'job_id': job.job_id,
                'node_id': self.node_id,
                'status': 'failed',
                'return_code': -1,
                'stdout': '',
                'stderr': f'Job timed out after {job.timeout} seconds',
                'duration': time.time() - start_time,
                'completed_at': time.time()
            }
            
            print(f"[TIMEOUT] Job {job.job_id} timed out")
            return result
            
        except Exception as e:
            with self.lock:
                self.active_jobs.pop(job.job_id, None)
            
            result = {
                'job_id': job.job_id,
                'node_id': self.node_id,
                'status': 'failed',
                'return_code': -1,
                'stdout': '',
                'stderr': str(e),
                'duration': time.time() - start_time,
                'completed_at': time.time()
            }
            
            print(f"[ERR] Job {job.job_id} failed: {e}")
            return result
    
    def worker_loop(self):
        """Main worker loop - processes jobs from queue"""
        print(f"[WORKER] Worker loop started on {self.node_id}")
        
        while self.running:
            try:
                # Get next job from priority queue
                job_data = self.redis_client.bzpopmin(self.job_queue, timeout=5)
                
                if not job_data:
                    continue
                
                queue_name, job_json, score = job_data
                job_dict = json.loads(job_json)
                job = Job(**job_dict)
                
                # Execute job
                result = self.execute_job(job)
                
                # Store result
                result_key = f"oswalk:job:result:{job.job_id}"
                self.redis_client.setex(result_key, 3600, json.dumps(result))  # Expire in 1 hour
                
                # Update node heartbeat
                self.register_node()
                
            except Exception as e:
                print(f"Worker error: {e}")
                time.sleep(1)
    
    def start_worker(self):
        """Start the worker in background thread"""
        if self.running:
            return
        
        self.running = True
        self.register_node()
        
        worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
        worker_thread.start()
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        
        print(f"[CPU] Worker started on {self.node_id}")
    
    def stop_worker(self):
        """Stop the worker"""
        self.running = False
        
        # Kill active jobs
        with self.lock:
            for job_id, process in self.active_jobs.items():
                try:
                    process.kill()
                    print(f"[KILL] Killed job {job_id}")
                except:
                    pass
            self.active_jobs.clear()
        
        print(f"[STOP] Worker stopped on {self.node_id}")
    
    def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self.running:
            try:
                self.register_node()
                time.sleep(30)  # Heartbeat every 30 seconds
            except Exception as e:
                print(f"Heartbeat error: {e}")
                time.sleep(5)
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get cluster status"""
        try:
            # Get all nodes
            node_keys = self.redis_client.keys("oswalk:nodes:node-*")
            nodes = []
            
            for key in node_keys:
                node_data = self.redis_client.hgetall(key)
                if node_data:
                    # Convert numeric fields
                    for field in ['cpu_count', 'memory_mb', 'active_jobs']:
                        if field in node_data:
                            node_data[field] = int(node_data[field])
                    for field in ['load_avg', 'last_heartbeat']:
                        if field in node_data:
                            node_data[field] = float(node_data[field])
                    
                    # Check if healthy (heartbeat within last 2 minutes)
                    node_data['healthy'] = (time.time() - node_data.get('last_heartbeat', 0)) < 120
                    nodes.append(node_data)
            
            # Get queue stats
            pending_jobs = self.redis_client.zcard(self.job_queue)
            
            # Calculate totals
            total_cpus = sum(node.get('cpu_count', 0) for node in nodes)
            total_memory = sum(node.get('memory_mb', 0) for node in nodes)
            total_active_jobs = sum(node.get('active_jobs', 0) for node in nodes)
            healthy_nodes = len([n for n in nodes if n.get('healthy', False)])
            
            return {
                'nodes': nodes,
                'total_nodes': len(nodes),
                'healthy_nodes': healthy_nodes,
                'total_cpus': total_cpus,
                'total_memory_mb': total_memory,
                'pending_jobs': pending_jobs,
                'active_jobs': total_active_jobs
            }
            
        except Exception as e:
            print(f"Error getting cluster status: {e}")
            return {'error': str(e)}

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Distributed CPU worker')
    parser.add_argument('--redis-host', default='localhost', help='Redis host')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis port')
    parser.add_argument('--node-id', help='Node ID (auto-generated if not provided)')
    parser.add_argument('--command', help='Command to execute (for testing)')
    
    args = parser.parse_args()
    
    cpu = DistributedCPU(args.redis_host, args.redis_port, args.node_id)
    
    if args.command:
        # Submit test job
        job_id = cpu.submit_job(args.command.split())
        print(f"Submitted job: {job_id}")
        
        # Wait for result
        result = cpu.get_job_result(job_id, timeout=60)
        if result:
            print(f"Result: {result}")
        else:
            print("Job timed out or failed")
    else:
        # Start worker
        cpu.start_worker()
        
        try:
            while True:
                status = cpu.get_cluster_status()
                print(f"Cluster: {status['healthy_nodes']}/{status['total_nodes']} nodes, {status['total_cpus']} CPUs, {status['pending_jobs']} pending jobs")
                time.sleep(30)
        except KeyboardInterrupt:
            cpu.stop_worker()

if __name__ == '__main__':
    main()