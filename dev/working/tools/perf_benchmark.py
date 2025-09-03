#!/usr/bin/env python3
"""
PacketFS Performance Benchmark Suite
Comprehensive performance testing with CPU, memory, and throughput analysis.
"""
import time
import threading
import argparse
import sys
import queue
# import psutil  # Removed for system compatibility
import struct
import os
import mmap
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from statistics import mean, stdev
import socket

from packetfs.rawio import get_if_mac, make_eth_header
from packetfs.protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig
from packetfs import _bitpack

ETH_P_PFS = 0x1337

@dataclass
class BenchmarkConfig:
    """Benchmark configuration parameters."""
    frame_counts: List[int]  # Number of frames to send per test
    payload_sizes: List[int]  # Payload sizes to test (in refs)
    burst_sizes: List[int]    # Burst sizes for batched sends
    iterations: int          # Number of iterations per test
    warmup_frames: int       # Warmup frames before measurements
    cpu_monitoring: bool     # Enable CPU usage monitoring
    memory_profiling: bool   # Enable memory usage profiling
    
@dataclass
class PerformanceMetrics:
    """Performance measurement results."""
    test_name: str
    frame_count: int
    payload_size: int
    burst_size: int
    
    # Timing metrics
    total_time_sec: float
    encode_time_sec: float
    send_time_sec: float
    recv_time_sec: float
    
    # Throughput metrics
    frames_per_second: float
    mbits_per_second: float
    refs_per_second: float
    
    # Latency metrics (microseconds)
    avg_latency_us: float
    min_latency_us: float
    max_latency_us: float
    latency_stdev_us: float
    
    # Resource usage
    peak_cpu_percent: float
    peak_memory_mb: float
    
    # Protocol metrics
    sync_frames: int
    sync_rate_percent: float
    crc_errors: int

class HighPerformanceSender:
    """Optimized packet sender with minimal overhead."""
    
    def __init__(self, ifname: str):
        self.ifname = ifname
        self.mac = get_if_mac(ifname)
        self.eth_header = make_eth_header(self.mac)
        self.socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        self.socket.bind((ifname, 0))
        
        # Pre-allocate frame buffer for reuse
        self.frame_buffer = bytearray(1500 + 14)  # Max Ethernet frame
        self.frame_buffer[:14] = self.eth_header
        
    def create_optimized_payload(self, enc: ProtocolEncoder, ref_count: int) -> bytes:
        """Create payload with minimal allocations."""
        # Use class buffer to avoid repeated allocations
        out = bytearray(1500)
        refs = bytes((i % 256) for i in range(ref_count))
        
        bits = enc.pack_refs(out, 0, refs, 8)
        extra = enc.maybe_sync()
        
        nbytes = (bits + 7) // 8
        payload = out[:nbytes]
        
        if extra:
            payload += extra
            
        return payload
    
    def send_burst(self, payloads: List[bytes]) -> Tuple[float, List[float]]:
        """Send burst of frames with high-precision timing."""
        send_times = []
        
        start_time = time.time_ns()
        
        for payload in payloads:
            # Copy payload into pre-allocated buffer
            payload_len = len(payload)
            self.frame_buffer[14:14+payload_len] = payload
            
            # Ensure minimum frame size
            frame_len = max(60, 14 + payload_len)
            if frame_len > 14 + payload_len:
                # Zero-fill padding
                self.frame_buffer[14+payload_len:frame_len] = b'\x00' * (frame_len - 14 - payload_len)
            
            frame_start = time.time_ns()
            self.socket.send(self.frame_buffer[:frame_len])
            frame_end = time.time_ns()
            
            send_times.append((frame_end - frame_start) / 1000.0)  # Convert to microseconds
            
        total_time = (time.time_ns() - start_time) / 1_000_000_000.0  # Convert to seconds
        return total_time, send_times

class HighPerformanceReceiver:
    """Optimized packet receiver with minimal overhead."""
    
    def __init__(self, ifname: str):
        self.ifname = ifname
        self.socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_PFS))
        self.socket.bind((ifname, 0))
        self.socket.settimeout(0.1)  # 100ms timeout
        
        self.decoder = ProtocolDecoder(SyncConfig(window_pow2=16, window_crc16=True))
        
        # Pre-allocate receive buffer
        self.recv_buffer = bytearray(2048)
        
    def receive_burst(self, expected_count: int, max_wait_time: float = 10.0) -> Tuple[int, List[float], int, int]:
        """Receive burst of frames with timing measurements."""
        recv_times = []
        sync_count = 0
        crc_errors = 0
        frames_received = 0
        
        start_time = time.time()
        
        while frames_received < expected_count and (time.time() - start_time) < max_wait_time:
            try:
                frame_start = time.time_ns()
                frame_data = self.socket.recv(2048)
                frame_end = time.time_ns()
                
                frames_received += 1
                recv_times.append((frame_end - frame_start) / 1000.0)  # Convert to microseconds
                
                # Analyze frame
                if len(frame_data) > 14:
                    payload = frame_data[14:]
                    sync_info = self.decoder.scan_for_sync(payload)
                    if sync_info:
                        sync_count += 1
                        
            except socket.timeout:
                continue
            except Exception as e:
                crc_errors += 1
                
        return frames_received, recv_times, sync_count, crc_errors

class SystemMonitor:
    """System resource usage monitor (simplified version without psutil)."""
    
    def __init__(self):
        self.monitoring = False
        self.cpu_samples = []
        self.memory_samples = []
        self._monitor_thread = None
    
    def start_monitoring(self):
        """Start system resource monitoring (simplified version)."""
        self.monitoring = True
        self.cpu_samples.clear()
        self.memory_samples.clear()
        
        def monitor_loop():
            while self.monitoring:
                try:
                    # Simple /proc-based monitoring
                    with open('/proc/loadavg', 'r') as f:
                        load_avg = float(f.read().split()[0])
                        cpu_percent = min(100.0, load_avg * 25)  # Rough approximation
                    
                    with open('/proc/meminfo', 'r') as f:
                        meminfo = f.read()
                        total_match = [line for line in meminfo.split('\n') if line.startswith('MemTotal:')]
                        free_match = [line for line in meminfo.split('\n') if line.startswith('MemFree:')]
                        if total_match and free_match:
                            total_kb = int(total_match[0].split()[1])
                            free_kb = int(free_match[0].split()[1])
                            used_mb = (total_kb - free_kb) / 1024
                        else:
                            used_mb = 0.0
                    
                    self.cpu_samples.append(cpu_percent)
                    self.memory_samples.append(used_mb)
                    
                    time.sleep(0.1)  # 100ms sampling
                except Exception:
                    # Fallback values if monitoring fails
                    self.cpu_samples.append(0.0)
                    self.memory_samples.append(0.0)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self) -> Tuple[float, float]:
        """Stop monitoring and return peak usage."""
        self.monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
            
        peak_cpu = max(self.cpu_samples) if self.cpu_samples else 0.0
        peak_memory = max(self.memory_samples) if self.memory_samples else 0.0
        
        return peak_cpu, peak_memory

def run_performance_test(
    tx_iface: str,
    rx_iface: str, 
    config: BenchmarkConfig,
    test_name: str,
    frame_count: int,
    payload_size: int,
    burst_size: int
) -> PerformanceMetrics:
    """Run a single performance test with detailed measurements."""
    
    print(f"🏃 Running {test_name}: {frame_count} frames, {payload_size} refs, burst={burst_size}")
    
    # Initialize components
    sender = HighPerformanceSender(tx_iface)
    receiver = HighPerformanceReceiver(rx_iface)
    monitor = SystemMonitor()
    
    enc = ProtocolEncoder(SyncConfig(window_pow2=16, window_crc16=True))
    
    # Pre-generate payloads to remove encoding time from measurement
    print("  📦 Pre-generating payloads...")
    encode_start = time.time()
    
    payloads = []
    for i in range(frame_count):
        payload = sender.create_optimized_payload(enc, payload_size)
        payloads.append(payload)
    
    encode_time = time.time() - encode_start
    
    # Split into bursts
    payload_bursts = [payloads[i:i+burst_size] for i in range(0, len(payloads), burst_size)]
    
    # Start receiver
    print("  🎯 Starting receiver...")
    recv_start_time = time.time()
    
    def receiver_worker(result_queue: queue.Queue):
        frames_received, recv_times, sync_count, crc_errors = receiver.receive_burst(frame_count)
        recv_total_time = time.time() - recv_start_time
        
        result_queue.put({
            'frames_received': frames_received,
            'recv_times': recv_times, 
            'recv_total_time': recv_total_time,
            'sync_count': sync_count,
            'crc_errors': crc_errors
        })
    
    result_queue = queue.Queue()
    recv_thread = threading.Thread(target=receiver_worker, args=(result_queue,))
    recv_thread.daemon = True
    recv_thread.start()
    
    # Wait for receiver to initialize
    time.sleep(0.1)
    
    # Start system monitoring
    if config.cpu_monitoring:
        monitor.start_monitoring()
    
    # Execute sender bursts
    print(f"  🚀 Sending {len(payload_bursts)} bursts...")
    send_start_time = time.time()
    all_send_times = []
    
    for i, burst in enumerate(payload_bursts):
        burst_time, send_times = sender.send_burst(burst)
        all_send_times.extend(send_times)
        
        if (i + 1) % 10 == 0:
            print(f"    Sent burst {i+1}/{len(payload_bursts)}")
    
    send_total_time = time.time() - send_start_time
    
    # Wait for receiver to complete
    try:
        recv_result = result_queue.get(timeout=max(10.0, frame_count * 0.01))
    except queue.Empty:
        print("  ⚠️ Receiver timeout!")
        recv_result = {
            'frames_received': 0, 'recv_times': [], 'recv_total_time': 0,
            'sync_count': 0, 'crc_errors': 0
        }
    
    recv_thread.join(timeout=1.0)
    
    # Stop monitoring
    peak_cpu, peak_memory = monitor.stop_monitoring()
    
    # Calculate metrics
    total_time = max(send_total_time, recv_result['recv_total_time'])
    frames_received = recv_result['frames_received']
    
    # Throughput calculations
    frames_per_second = frames_received / total_time if total_time > 0 else 0
    total_bits = frames_received * payload_size * 8  # Assume 8 bits per ref for simplicity
    mbits_per_second = (total_bits / 1_000_000) / total_time if total_time > 0 else 0
    refs_per_second = (frames_received * payload_size) / total_time if total_time > 0 else 0
    
    # Latency calculations (round-trip approximation)
    combined_times = all_send_times + recv_result['recv_times']
    if combined_times:
        avg_latency = mean(combined_times)
        min_latency = min(combined_times)
        max_latency = max(combined_times)
        latency_std = stdev(combined_times) if len(combined_times) > 1 else 0
    else:
        avg_latency = min_latency = max_latency = latency_std = 0
    
    # Protocol metrics
    sync_rate = (recv_result['sync_count'] / frames_received * 100) if frames_received > 0 else 0
    
    print(f"  ✅ Complete: {frames_received}/{frame_count} frames, {frames_per_second:.1f} fps, {mbits_per_second:.2f} Mbps")
    
    return PerformanceMetrics(
        test_name=test_name,
        frame_count=frame_count,
        payload_size=payload_size,
        burst_size=burst_size,
        total_time_sec=total_time,
        encode_time_sec=encode_time,
        send_time_sec=send_total_time,
        recv_time_sec=recv_result['recv_total_time'],
        frames_per_second=frames_per_second,
        mbits_per_second=mbits_per_second,
        refs_per_second=refs_per_second,
        avg_latency_us=avg_latency,
        min_latency_us=min_latency,
        max_latency_us=max_latency,
        latency_stdev_us=latency_std,
        peak_cpu_percent=peak_cpu,
        peak_memory_mb=peak_memory,
        sync_frames=recv_result['sync_count'],
        sync_rate_percent=sync_rate,
        crc_errors=recv_result['crc_errors']
    )

def print_benchmark_results(results: List[PerformanceMetrics]):
    """Print formatted benchmark results."""
    print("\n" + "=" * 120)
    print("🏆 PACKETFS PERFORMANCE BENCHMARK RESULTS")
    print("=" * 120)
    
    print(f"{'Test Name':<20} {'Frames':<8} {'Payload':<8} {'Burst':<6} {'FPS':<10} {'Mbps':<10} {'Refs/s':<12} {'Lat(μs)':<10} {'CPU%':<8} {'Mem(MB)':<8}")
    print("-" * 120)
    
    for result in results:
        print(f"{result.test_name:<20} {result.frame_count:<8} {result.payload_size:<8} {result.burst_size:<6} "
              f"{result.frames_per_second:<10.1f} {result.mbits_per_second:<10.2f} {result.refs_per_second:<12.0f} "
              f"{result.avg_latency_us:<10.1f} {result.peak_cpu_percent:<8.1f} {result.peak_memory_mb:<8.1f}")

def main():
    parser = argparse.ArgumentParser(description="PacketFS Performance Benchmark Suite")
    parser.add_argument("--tx-iface", required=True, help="Transmit interface")
    parser.add_argument("--rx-iface", required=True, help="Receive interface")
    parser.add_argument("--quick", action="store_true", help="Run quick benchmark (fewer tests)")
    parser.add_argument("--intensive", action="store_true", help="Run intensive benchmark (more tests)")
    parser.add_argument("--output", help="Save results to JSON file")
    
    args = parser.parse_args()
    
    if args.quick:
        config = BenchmarkConfig(
            frame_counts=[100, 500],
            payload_sizes=[64, 256],
            burst_sizes=[1, 10],
            iterations=1,
            warmup_frames=10,
            cpu_monitoring=True,
            memory_profiling=True
        )
    elif args.intensive:
        config = BenchmarkConfig(
            frame_counts=[100, 500, 1000, 5000],
            payload_sizes=[32, 64, 128, 256, 512, 1024],
            burst_sizes=[1, 10, 50, 100],
            iterations=3,
            warmup_frames=50,
            cpu_monitoring=True,
            memory_profiling=True
        )
    else:
        config = BenchmarkConfig(
            frame_counts=[100, 1000],
            payload_sizes=[64, 256, 512],
            burst_sizes=[1, 10, 50],
            iterations=2,
            warmup_frames=20,
            cpu_monitoring=True,
            memory_profiling=True
        )
    
    print("🎯 PacketFS Performance Benchmark Suite")
    print(f"📡 TX: {args.tx_iface} -> RX: {args.rx_iface}")
    print(f"🔧 Config: {len(config.frame_counts)} frame counts, {len(config.payload_sizes)} payload sizes, {len(config.burst_sizes)} burst sizes")
    print(f"🔄 Iterations per test: {config.iterations}")
    
    results = []
    test_count = 0
    total_tests = len(config.frame_counts) * len(config.payload_sizes) * len(config.burst_sizes) * config.iterations
    
    try:
        for iteration in range(config.iterations):
            for frame_count in config.frame_counts:
                for payload_size in config.payload_sizes:
                    for burst_size in config.burst_sizes:
                        test_count += 1
                        test_name = f"iter{iteration+1}_f{frame_count}_p{payload_size}_b{burst_size}"
                        
                        print(f"\n[{test_count}/{total_tests}] Testing {test_name}")
                        
                        result = run_performance_test(
                            args.tx_iface, args.rx_iface, config,
                            test_name, frame_count, payload_size, burst_size
                        )
                        
                        results.append(result)
                        
                        # Brief pause between tests
                        time.sleep(0.5)
        
        print_benchmark_results(results)
        
        # Save results if requested
        if args.output:
            import json
            with open(args.output, 'w') as f:
                json.dump([result.__dict__ for result in results], f, indent=2)
            print(f"\n📊 Results saved to {args.output}")
            
        print(f"\n🏁 Benchmark completed! {len(results)} tests run.")
        
    except KeyboardInterrupt:
        print("\n⚠️ Benchmark interrupted by user")
        if results:
            print_benchmark_results(results)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
