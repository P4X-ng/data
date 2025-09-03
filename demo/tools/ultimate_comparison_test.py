#!/usr/bin/env python3
"""
ULTIMATE COMPARISON TEST: PacketFS vs TCP
Large file transfer performance, error rates, and efficiency analysis
"""

import os
import time
import socket
import hashlib
import threading
import json
import subprocess
import statistics
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from logging.handlers import RotatingFileHandler

# Import our PacketFS implementation
from packetfs_file_transfer import PacketFSFileTransfer

@dataclass
class TransferResult:
    """Comprehensive transfer results"""
    protocol: str
    file_size: int
    transfer_time: float
    throughput_mbps: float
    throughput_mbs: float  # MB/s
    errors: int
    retries: int
    cpu_usage_percent: float
    memory_usage_mb: float
    packets_sent: int
    packets_lost: int
    packet_loss_rate: float
    integrity_check: bool
    compression_ratio: float
    protocol_overhead_percent: float

class TCPFileTransfer:
    """Traditional TCP file transfer for comparison"""
    
    def __init__(self, port: int = 8338):
        self.port = port
        self.stats = {
            'bytes_sent': 0,
            'bytes_received': 0,
            'packets_sent': 0,
            'packets_lost': 0,
            'errors': 0,
            'retries': 0,
            'start_time': time.time()
        }
    
    def start_server(self, file_path: str):
        """Start TCP file server"""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(('0.0.0.0', self.port))
        server_sock.listen(1)
        
        print(f"📡 TCP Server listening on port {self.port}")
        
        client_sock, client_addr = server_sock.accept()
        print(f"🔗 TCP connection from {client_addr}")
        
        try:
            # Send file size first
            file_size = os.path.getsize(file_path)
            client_sock.send(str(file_size).encode().ljust(16))
            
            # Send file data
            with open(file_path, 'rb') as f:
                bytes_sent = 0
                while True:
                    chunk = f.read(8192)  # Same chunk size as PacketFS
                    if not chunk:
                        break
                    
                    client_sock.send(chunk)
                    bytes_sent += len(chunk)
                    self.stats['bytes_sent'] += len(chunk)
                    self.stats['packets_sent'] += 1
                    
                    if bytes_sent % (1024 * 1024) == 0:  # Every MB
                        print(f"📤 TCP sent {bytes_sent // (1024*1024)} MB")
            
            print(f"✅ TCP transfer completed: {bytes_sent} bytes")
            
        except Exception as e:
            print(f"❌ TCP server error: {e}")
            self.stats['errors'] += 1
        finally:
            client_sock.close()
            server_sock.close()
    
    def receive_file(self, server_host: str, output_path: str) -> bool:
        """Receive file via TCP"""
        try:
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.connect((server_host, self.port))
            
            # Receive file size
            size_data = client_sock.recv(16).decode().strip()
            file_size = int(size_data)
            print(f"📋 TCP receiving {file_size} bytes")
            
            # Receive file data
            with open(output_path, 'wb') as f:
                bytes_received = 0
                
                while bytes_received < file_size:
                    chunk = client_sock.recv(8192)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    bytes_received += len(chunk)
                    self.stats['bytes_received'] += len(chunk)
                    
                    if bytes_received % (1024 * 1024) == 0:  # Every MB
                        print(f"📥 TCP received {bytes_received // (1024*1024)} MB")
            
            print(f"✅ TCP received {bytes_received} bytes")
            client_sock.close()
            
            return bytes_received == file_size
            
        except Exception as e:
            print(f"❌ TCP client error: {e}")
            self.stats['errors'] += 1
            return False

class UltimateComparisonTest:
    """Ultimate performance comparison suite"""
    
    def __init__(self, remote_host: str = "10.69.69.235"):
        self.remote_host = remote_host
        self.results: List[TransferResult] = []
        self.setup_logging()
        
    def setup_logging(self):
        """Setup comprehensive logging"""
        # Create logs directory
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Setup logger
        self.logger = logging.getLogger('UltimateComparison')
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler with rotation
        log_file = log_dir / f'ultimate_comparison_{int(time.time())}.log'
        file_handler = RotatingFileHandler(
            log_file, maxBytes=50*1024*1024, backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Detailed formatter
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        # Simple formatter for console
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        file_handler.setFormatter(detailed_formatter)
        console_handler.setFormatter(simple_formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"Logging initialized - Remote host: {self.remote_host}")
        
    def create_large_test_file(self, size_mb: int, filename: str):
        """Create large test file with diverse data"""
        self.logger.info(f"Creating {size_mb}MB test file: {filename}")
        print(f"📁 Creating {size_mb}MB test file: {filename}")
        
        with open(filename, 'wb') as f:
            bytes_written = 0
            target_bytes = size_mb * 1024 * 1024
            
            # Create diverse data patterns for realistic testing
            patterns = [
                b'A' * 1024,           # Highly compressible
                os.urandom(512),       # Random data
                b'PacketFS' * 128,     # Repeated text
                bytes(range(256)) * 4, # Sequential data
                bytes(256),        # Zero padding
                json.dumps({           # JSON structure
                    'test_data': list(range(50)),
                    'timestamp': time.time(),
                    'pattern': 'mixed_content'
                }).encode()
            ]
            
            pattern_idx = 0
            while bytes_written < target_bytes:
                pattern = patterns[pattern_idx % len(patterns)]
                remaining = target_bytes - bytes_written
                
                if remaining < len(pattern):
                    pattern = pattern[:remaining]
                
                f.write(pattern)
                bytes_written += len(pattern)
                pattern_idx += 1
                
                if bytes_written % (10 * 1024 * 1024) == 0:  # Every 10MB
                    print(f"  📝 Written {bytes_written // (1024*1024)} MB")
        
        print(f"✅ Created {filename}: {bytes_written:,} bytes")
        return bytes_written
    
    def get_file_hash(self, file_path: str) -> str:
        """Calculate file hash for integrity verification"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def measure_system_resources(self) -> Tuple[float, float]:
        """Measure CPU and memory usage"""
        try:
            # Get CPU usage
            cpu_result = subprocess.run(['top', '-bn1'], 
                                      capture_output=True, text=True)
            cpu_line = [line for line in cpu_result.stdout.split('\n') 
                       if 'Cpu(s):' in line][0]
            cpu_idle = float(cpu_line.split('id')[0].split(',')[-1].strip())
            cpu_usage = 100.0 - cpu_idle
            
            # Get memory usage
            mem_result = subprocess.run(['free', '-m'], 
                                      capture_output=True, text=True)
            mem_line = mem_result.stdout.split('\n')[1]
            mem_used = int(mem_line.split()[2])
            
            return cpu_usage, mem_used
        except:
            return 0.0, 0.0
    
    def test_packetfs_transfer(self, file_path: str, size_mb: int) -> TransferResult:
        """Test PacketFS transfer performance"""
        print(f"\n🚀 Testing PacketFS transfer: {size_mb}MB file")
        
        # Start PacketFS server on remote machine
        server_cmd = (
            f"cd ~/packetfs-remote && "
            f"source .venv/bin/activate && "
            f"python tools/packetfs_file_transfer.py server --host 0.0.0.0 --port 8337"
        )
        
        # Copy test file to remote machine
        print("📤 Copying test file to remote machine...")
        rsync_result = subprocess.run([
            'rsync', '-avz', file_path, f'punk@{self.remote_host}:~/'
        ], capture_output=True)
        
        if rsync_result.returncode != 0:
            print(f"❌ Failed to copy file: {rsync_result.stderr.decode()}")
            return None
        
        # Start PacketFS server (background process)
        print("🎯 Starting PacketFS server on remote machine...")
        server_process = subprocess.Popen([
            'ssh', '-A', f'punk@{self.remote_host}', server_cmd
        ])
        
        time.sleep(2)  # Wait for server to start
        
        # Measure system resources before transfer
        cpu_before, mem_before = self.measure_system_resources()
        
        # Start PacketFS transfer
        pfs = PacketFSFileTransfer()
        start_time = time.time()
        
        remote_file_path = f"/home/punk/{Path(file_path).name}"
        local_output = f"received_packetfs_{size_mb}mb.bin"
        
        success = pfs.request_file(self.remote_host, remote_file_path, local_output)
        
        transfer_time = time.time() - start_time
        
        # Measure system resources after transfer
        cpu_after, mem_after = self.measure_system_resources()
        
        # Kill server
        try:
            server_process.terminate()
            server_process.wait(timeout=5)
        except:
            server_process.kill()
        
        if not success:
            print("❌ PacketFS transfer failed")
            return None
        
        # Calculate metrics
        file_size = os.path.getsize(file_path)
        throughput_mbs = file_size / (1024 * 1024) / transfer_time
        throughput_mbps = throughput_mbs * 8
        
        # Verify integrity
        original_hash = self.get_file_hash(file_path)
        received_hash = self.get_file_hash(local_output)
        integrity_ok = original_hash == received_hash
        
        # Calculate protocol overhead
        protocol_overhead = ((pfs.stats['bytes_received'] - file_size) / file_size) * 100
        
        result = TransferResult(
            protocol="PacketFS",
            file_size=file_size,
            transfer_time=transfer_time,
            throughput_mbps=throughput_mbps,
            throughput_mbs=throughput_mbs,
            errors=0 if success else 1,
            retries=0,
            cpu_usage_percent=(cpu_after - cpu_before),
            memory_usage_mb=(mem_after - mem_before),
            packets_sent=pfs.stats['chunks_sent'],
            packets_lost=0,  # PacketFS handles this internally
            packet_loss_rate=0.0,
            integrity_check=integrity_ok,
            compression_ratio=1.0,  # Not implemented yet
            protocol_overhead_percent=protocol_overhead
        )
        
        print(f"✅ PacketFS: {throughput_mbs:.2f} MB/s, {transfer_time:.2f}s, Integrity: {'✅' if integrity_ok else '❌'}")
        
        return result
    
    def test_tcp_transfer(self, file_path: str, size_mb: int) -> TransferResult:
        """Test TCP transfer performance"""
        print(f"\n📡 Testing TCP transfer: {size_mb}MB file")
        
        # Start TCP server on remote machine
        server_cmd = (
            f"cd ~/packetfs-remote && "
            f"source .venv/bin/activate && "
            f"python tools/ultimate_comparison_test.py tcp-server "
            f"--file /home/punk/{Path(file_path).name}"
        )
        
        # Start TCP server (background process)
        print("🎯 Starting TCP server on remote machine...")
        server_process = subprocess.Popen([
            'ssh', '-A', f'punk@{self.remote_host}', server_cmd
        ])
        
        time.sleep(2)  # Wait for server to start
        
        # Measure system resources before transfer
        cpu_before, mem_before = self.measure_system_resources()
        
        # Start TCP transfer
        tcp = TCPFileTransfer(port=8338)
        start_time = time.time()
        
        local_output = f"received_tcp_{size_mb}mb.bin"
        success = tcp.receive_file(self.remote_host, local_output)
        
        transfer_time = time.time() - start_time
        
        # Measure system resources after transfer
        cpu_after, mem_after = self.measure_system_resources()
        
        # Kill server
        try:
            server_process.terminate()
            server_process.wait(timeout=5)
        except:
            server_process.kill()
        
        if not success:
            print("❌ TCP transfer failed")
            return None
        
        # Calculate metrics
        file_size = os.path.getsize(file_path)
        throughput_mbs = file_size / (1024 * 1024) / transfer_time
        throughput_mbps = throughput_mbs * 8
        
        # Verify integrity
        original_hash = self.get_file_hash(file_path)
        received_hash = self.get_file_hash(local_output)
        integrity_ok = original_hash == received_hash
        
        # TCP overhead is minimal - just TCP/IP headers
        tcp_header_overhead = (tcp.stats['packets_sent'] * 66) / file_size * 100  # ~66 bytes per packet
        
        result = TransferResult(
            protocol="TCP",
            file_size=file_size,
            transfer_time=transfer_time,
            throughput_mbps=throughput_mbps,
            throughput_mbs=throughput_mbs,
            errors=tcp.stats['errors'],
            retries=tcp.stats['retries'],
            cpu_usage_percent=(cpu_after - cpu_before),
            memory_usage_mb=(mem_after - mem_before),
            packets_sent=tcp.stats['packets_sent'],
            packets_lost=tcp.stats['packets_lost'],
            packet_loss_rate=(tcp.stats['packets_lost'] / tcp.stats['packets_sent'] * 100) if tcp.stats['packets_sent'] > 0 else 0,
            integrity_check=integrity_ok,
            compression_ratio=1.0,
            protocol_overhead_percent=tcp_header_overhead
        )
        
        print(f"✅ TCP: {throughput_mbs:.2f} MB/s, {transfer_time:.2f}s, Integrity: {'✅' if integrity_ok else '❌'}")
        
        return result
    
    def run_ultimate_comparison(self, test_sizes_mb: List[int] = [10, 50, 100, 500]):
        """Run the ultimate comparison test"""
        print("🏆 ULTIMATE PACKETFS vs TCP COMPARISON TEST")
        print("=" * 60)
        
        for size_mb in test_sizes_mb:
            print(f"\n📊 Testing {size_mb}MB file transfers...")
            
            # Create test file
            test_file = f"test_file_{size_mb}mb.bin"
            self.create_large_test_file(size_mb, test_file)
            
            # Test PacketFS
            pfs_result = self.test_packetfs_transfer(test_file, size_mb)
            if pfs_result:
                self.results.append(pfs_result)
            
            # Wait between tests
            time.sleep(1)
            
            # Test TCP
            tcp_result = self.test_tcp_transfer(test_file, size_mb)
            if tcp_result:
                self.results.append(tcp_result)
            
            # Cleanup
            try:
                os.remove(test_file)
                os.remove(f"received_packetfs_{size_mb}mb.bin")
                os.remove(f"received_tcp_{size_mb}mb.bin")
            except:
                pass
        
        # Generate comprehensive report
        self.generate_comparison_report()
    
    def generate_comparison_report(self):
        """Generate comprehensive comparison report"""
        print("\n" + "=" * 80)
        print("🏆 ULTIMATE COMPARISON RESULTS")
        print("=" * 80)
        
        # Group results by protocol
        packetfs_results = [r for r in self.results if r.protocol == "PacketFS"]
        tcp_results = [r for r in self.results if r.protocol == "TCP"]
        
        if not packetfs_results or not tcp_results:
            print("❌ Insufficient test results for comparison")
            return
        
        print(f"\n📊 PERFORMANCE COMPARISON")
        print("-" * 80)
        print(f"{'Size (MB)':<10} {'Protocol':<10} {'Speed (MB/s)':<12} {'Time (s)':<10} {'Integrity':<10} {'Overhead %':<12}")
        print("-" * 80)
        
        # Sort results by file size for comparison
        all_results = sorted(self.results, key=lambda x: (x.file_size, x.protocol))
        
        for result in all_results:
            size_mb = result.file_size // (1024 * 1024)
            integrity_symbol = "✅" if result.integrity_check else "❌"
            
            print(f"{size_mb:<10} {result.protocol:<10} {result.throughput_mbs:<12.2f} "
                  f"{result.transfer_time:<10.2f} {integrity_symbol:<10} {result.protocol_overhead_percent:<12.2f}")
        
        # Calculate averages and comparisons
        print(f"\n📈 AVERAGE PERFORMANCE")
        print("-" * 80)
        
        pfs_avg_speed = statistics.mean([r.throughput_mbs for r in packetfs_results])
        tcp_avg_speed = statistics.mean([r.throughput_mbs for r in tcp_results])
        
        pfs_avg_overhead = statistics.mean([r.protocol_overhead_percent for r in packetfs_results])
        tcp_avg_overhead = statistics.mean([r.protocol_overhead_percent for r in tcp_results])
        
        speed_advantage = (pfs_avg_speed / tcp_avg_speed) if tcp_avg_speed > 0 else 0
        overhead_comparison = (pfs_avg_overhead / tcp_avg_overhead) if tcp_avg_overhead > 0 else 0
        
        print(f"PacketFS Average Speed: {pfs_avg_speed:.2f} MB/s")
        print(f"TCP Average Speed: {tcp_avg_speed:.2f} MB/s")
        print(f"PacketFS Speed Advantage: {speed_advantage:.2f}x")
        print(f"")
        print(f"PacketFS Average Overhead: {pfs_avg_overhead:.2f}%")
        print(f"TCP Average Overhead: {tcp_avg_overhead:.2f}%")
        print(f"PacketFS Overhead Ratio: {overhead_comparison:.2f}x")
        
        # Integrity check summary
        pfs_integrity_rate = sum([1 for r in packetfs_results if r.integrity_check]) / len(packetfs_results) * 100
        tcp_integrity_rate = sum([1 for r in tcp_results if r.integrity_check]) / len(tcp_results) * 100
        
        print(f"")
        print(f"PacketFS Integrity Rate: {pfs_integrity_rate:.1f}%")
        print(f"TCP Integrity Rate: {tcp_integrity_rate:.1f}%")
        
        # Save detailed results
        results_data = {
            'timestamp': time.time(),
            'test_summary': {
                'packetfs_avg_speed_mbs': pfs_avg_speed,
                'tcp_avg_speed_mbs': tcp_avg_speed,
                'speed_advantage': speed_advantage,
                'packetfs_avg_overhead': pfs_avg_overhead,
                'tcp_avg_overhead': tcp_avg_overhead,
                'overhead_comparison': overhead_comparison,
                'packetfs_integrity_rate': pfs_integrity_rate,
                'tcp_integrity_rate': tcp_integrity_rate
            },
            'detailed_results': [
                {
                    'protocol': r.protocol,
                    'file_size_mb': r.file_size // (1024 * 1024),
                    'transfer_time': r.transfer_time,
                    'throughput_mbs': r.throughput_mbs,
                    'throughput_mbps': r.throughput_mbps,
                    'errors': r.errors,
                    'integrity_check': r.integrity_check,
                    'protocol_overhead_percent': r.protocol_overhead_percent
                }
                for r in self.results
            ]
        }
        
        with open('ultimate_comparison_results.json', 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: ultimate_comparison_results.json")
        print("🏁 Ultimate comparison test completed!")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ultimate PacketFS vs TCP Comparison")
    parser.add_argument('mode', nargs='?', default='compare', 
                       choices=['compare', 'tcp-server'], 
                       help='Run mode')
    parser.add_argument('--file', help='File to serve (tcp-server mode)')
    parser.add_argument('--sizes', nargs='+', type=int, default=[10, 50, 100],
                       help='File sizes in MB to test')
    parser.add_argument('--remote', default='10.69.69.235', 
                       help='Remote host for testing')
    
    args = parser.parse_args()
    
    if args.mode == 'tcp-server':
        if not args.file:
            print("❌ TCP server mode requires --file argument")
            exit(1)
        
        tcp = TCPFileTransfer(port=8338)
        tcp.start_server(args.file)
    
    else:  # compare mode
        test = UltimateComparisonTest(args.remote)
        test.run_ultimate_comparison(args.sizes)
