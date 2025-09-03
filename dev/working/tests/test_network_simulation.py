#!/usr/bin/env python3
"""
Network Simulation Testing Framework for PacketFS
Tests PacketFS performance under various network conditions and compares against TCP/UDP baselines.
"""
import pytest
import time
import subprocess
import socket
import threading
import queue
import json
import random
import statistics
import os
import tempfile
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Any
from contextlib import contextmanager
from pathlib import Path

from packetfs.rawio import send_frames, get_if_mac, make_eth_header, ETH_P_PFS
from packetfs.protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig
from packetfs.seed_pool import SeedPool


@dataclass
class NetworkCondition:
    """Network condition parameters for testing."""
    name: str
    delay_ms: float = 0.0           # RTT delay
    jitter_ms: float = 0.0          # Delay variation 
    loss_percent: float = 0.0       # Packet loss percentage
    bandwidth_mbps: float = 1000.0  # Bandwidth limit
    duplicate_percent: float = 0.0  # Packet duplication
    corrupt_percent: float = 0.0    # Packet corruption
    reorder_percent: float = 0.0    # Packet reordering


@dataclass
class TestScenario:
    """Complete test scenario definition."""
    name: str
    frame_counts: List[int]
    payload_sizes: List[int]  
    window_sizes: List[int]
    network_conditions: List[NetworkCondition]
    protocols: List[str]  # ['packetfs', 'tcp', 'udp']


@dataclass
class TestResult:
    """Test result metrics."""
    scenario_name: str
    protocol: str
    frame_count: int
    payload_size: int
    window_size: int
    network_condition: str
    
    # Performance metrics
    throughput_mbps: float
    latency_avg_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    packet_loss_percent: float
    jitter_ms: float
    
    # Protocol-specific metrics
    cpu_usage_percent: float
    memory_usage_mb: float
    
    # Test metadata
    timestamp: float
    duration_sec: float
    
    # Optional fields with defaults
    sync_frames: int = 0
    crc_errors: int = 0
    retransmissions: int = 0
    custom_metrics: Dict[str, Any] = None


class NetworkSimulator:
    """Network condition simulator using Linux traffic control (tc)."""
    
    def __init__(self, interface: str = "lo"):
        self.interface = interface
        self.active_rules = []
    
    @contextmanager
    def apply_conditions(self, condition: NetworkCondition):
        """Apply network conditions and automatically clean up."""
        try:
            self._apply_tc_rules(condition)
            print(f"🌐 Applied network condition: {condition.name}")
            yield
        finally:
            self._cleanup_tc_rules()
            print(f"🧹 Cleaned up network conditions")
    
    def _apply_tc_rules(self, condition: NetworkCondition):
        """Apply traffic control rules."""
        # Clear existing rules
        self._cleanup_tc_rules()
        
        # Build netem command
        netem_params = []
        
        if condition.delay_ms > 0:
            netem_params.append(f"delay {condition.delay_ms}ms")
            
        if condition.jitter_ms > 0:
            netem_params[-1] += f" {condition.jitter_ms}ms"
            
        if condition.loss_percent > 0:
            netem_params.append(f"loss {condition.loss_percent}%")
            
        if condition.duplicate_percent > 0:
            netem_params.append(f"duplicate {condition.duplicate_percent}%")
            
        if condition.corrupt_percent > 0:
            netem_params.append(f"corrupt {condition.corrupt_percent}%")
            
        if condition.reorder_percent > 0:
            netem_params.append(f"reorder {condition.reorder_percent}%")
        
        if netem_params:
            # Apply netem discipline
            cmd = [
                "sudo", "tc", "qdisc", "add", "dev", self.interface, 
                "root", "netem"
            ] + " ".join(netem_params).split()
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Warning: Failed to apply netem rules: {result.stderr}")
            else:
                self.active_rules.append("netem")
        
        # Apply bandwidth limits if specified
        if condition.bandwidth_mbps < 1000.0:
            # Add HTB for bandwidth limiting
            subprocess.run([
                "sudo", "tc", "qdisc", "add", "dev", self.interface, 
                "root", "handle", "1:", "htb", "default", "30"
            ], capture_output=True)
            
            subprocess.run([
                "sudo", "tc", "class", "add", "dev", self.interface,
                "parent", "1:", "classid", "1:1", "htb", 
                "rate", f"{condition.bandwidth_mbps}mbit"
            ], capture_output=True)
            
            self.active_rules.append("htb")
    
    def _cleanup_tc_rules(self):
        """Remove all traffic control rules."""
        subprocess.run([
            "sudo", "tc", "qdisc", "del", "dev", self.interface, "root"
        ], capture_output=True)
        self.active_rules.clear()


class PacketFSTestClient:
    """Test client for PacketFS protocol."""
    
    def __init__(self, interface: str, config: SyncConfig):
        self.interface = interface
        self.encoder = ProtocolEncoder(config)
        self.decoder = ProtocolDecoder(config)
        self.mac = get_if_mac(interface)
        
    def send_test_data(self, payload_size: int, frame_count: int) -> Tuple[float, List[float]]:
        """Send test data and measure performance."""
        latencies = []
        start_time = time.time()
        
        out = bytearray(payload_size * 2)
        
        for i in range(frame_count):
            # Generate test references
            refs = bytes([j % 256 for j in range(payload_size)])
            
            frame_start = time.time()
            
            # Encode
            bits = self.encoder.pack_refs(out, 0, refs, 8)
            sync_frame = self.encoder.maybe_sync()
            
            # Create payload
            payload_bytes = (bits + 7) // 8
            payload = bytes(out[:payload_bytes])
            if sync_frame:
                payload += sync_frame
            
            # Send frame
            send_frames(self.interface, [payload])
            
            frame_end = time.time()
            latencies.append((frame_end - frame_start) * 1000)  # Convert to ms
        
        total_time = time.time() - start_time
        return total_time, latencies
    
    def receive_test_data(self, expected_frames: int, timeout: float = 10.0) -> Tuple[int, List[float], int]:
        """Receive test data and measure performance."""
        latencies = []
        sync_count = 0
        frames_received = 0
        
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_PFS))
        sock.bind((self.interface, 0))
        sock.settimeout(0.1)
        
        start_time = time.time()
        
        while frames_received < expected_frames and (time.time() - start_time) < timeout:
            try:
                frame_start = time.time()
                frame = sock.recv(2048)
                frame_end = time.time()
                
                # Process frame
                if len(frame) > 14:  # Skip Ethernet header
                    payload = frame[14:]
                    sync_info = self.decoder.scan_for_sync(payload)
                    if sync_info:
                        sync_count += 1
                
                frames_received += 1
                latencies.append((frame_end - frame_start) * 1000)  # Convert to ms
                
            except socket.timeout:
                continue
            except Exception:
                pass
        
        sock.close()
        return frames_received, latencies, sync_count


class TCPTestClient:
    """Test client for TCP baseline comparison."""
    
    def __init__(self, port: int = 5001):
        self.port = port
    
    def run_server(self, duration: float) -> Dict[str, Any]:
        """Run TCP server and collect metrics."""
        cmd = [
            "iperf3", "-s", "-p", str(self.port), 
            "-t", str(int(duration)), "-J"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 5)
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return {
                    'throughput_mbps': data['end']['sum_received']['bits_per_second'] / 1e6,
                    'retransmissions': data['end']['sum_received'].get('retransmits', 0),
                    'cpu_usage': data['end']['cpu_utilization_percent']['host_total'],
                }
            except (json.JSONDecodeError, KeyError):
                pass
        
        return {'throughput_mbps': 0, 'retransmissions': 0, 'cpu_usage': 0}
    
    def run_client(self, target: str, duration: float, payload_size: int) -> Dict[str, Any]:
        """Run TCP client and collect metrics."""
        cmd = [
            "iperf3", "-c", target, "-p", str(self.port),
            "-t", str(int(duration)), "-l", str(payload_size), "-J"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 5)
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return {
                    'throughput_mbps': data['end']['sum_sent']['bits_per_second'] / 1e6,
                    'retransmissions': data['end']['sum_sent'].get('retransmits', 0),
                    'cpu_usage': data['end']['cpu_utilization_percent']['host_total'],
                    'mean_rtt': data['end'].get('streams', [{}])[0].get('sender', {}).get('mean_rtt', 0) / 1000,  # Convert to ms
                }
            except (json.JSONDecodeError, KeyError):
                pass
        
        return {'throughput_mbps': 0, 'retransmissions': 0, 'cpu_usage': 0, 'mean_rtt': 0}


class UDPTestClient:
    """Test client for UDP baseline comparison."""
    
    def __init__(self, port: int = 5002):
        self.port = port
    
    def run_test(self, target: str, duration: float, payload_size: int, bandwidth_mbps: float) -> Dict[str, Any]:
        """Run UDP test."""
        cmd = [
            "iperf3", "-c", target, "-u", "-p", str(self.port),
            "-t", str(int(duration)), "-l", str(payload_size),
            "-b", f"{bandwidth_mbps}M", "-J"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 5)
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return {
                    'throughput_mbps': data['end']['sum']['bits_per_second'] / 1e6,
                    'packet_loss': data['end']['sum']['lost_percent'],
                    'jitter_ms': data['end']['sum']['jitter_ms'],
                    'cpu_usage': data['end']['cpu_utilization_percent']['host_total'],
                }
            except (json.JSONDecodeError, KeyError):
                pass
        
        return {'throughput_mbps': 0, 'packet_loss': 100, 'jitter_ms': 0, 'cpu_usage': 0}


class ComprehensiveTestSuite:
    """Comprehensive testing suite for PacketFS."""
    
    def __init__(self, interface: str = "lo"):
        self.interface = interface
        self.simulator = NetworkSimulator(interface)
        self.results = []
    
    def run_packetfs_test(
        self, 
        condition: NetworkCondition,
        frame_count: int,
        payload_size: int, 
        window_size: int
    ) -> TestResult:
        """Run PacketFS performance test."""
        config = SyncConfig(
            window_pow2=window_size.bit_length() - 1,
            window_crc16=True
        )
        
        client = PacketFSTestClient(self.interface, config)
        
        with self.simulator.apply_conditions(condition):
            start_time = time.time()
            
            # Start receiver in separate thread
            result_queue = queue.Queue()
            
            def receiver():
                frames_rx, latencies_rx, sync_count = client.receive_test_data(frame_count)
                result_queue.put((frames_rx, latencies_rx, sync_count))
            
            rx_thread = threading.Thread(target=receiver)
            rx_thread.start()
            
            time.sleep(0.1)  # Let receiver start
            
            # Send data
            duration, latencies_tx = client.send_test_data(payload_size, frame_count)
            
            # Wait for receiver
            rx_thread.join(timeout=10)
            
            try:
                frames_rx, latencies_rx, sync_count = result_queue.get_nowait()
            except queue.Empty:
                frames_rx, latencies_rx, sync_count = 0, [], 0
            
            total_time = time.time() - start_time
            
            # Calculate metrics
            all_latencies = latencies_tx + latencies_rx
            throughput = (frames_rx * payload_size * 8) / (total_time * 1e6) if total_time > 0 else 0
            
            return TestResult(
                scenario_name="packetfs_test",
                protocol="packetfs",
                frame_count=frame_count,
                payload_size=payload_size,
                window_size=window_size,
                network_condition=condition.name,
                throughput_mbps=throughput,
                latency_avg_ms=statistics.mean(all_latencies) if all_latencies else 0,
                latency_p95_ms=statistics.quantiles(all_latencies, n=20)[18] if all_latencies else 0,
                latency_p99_ms=statistics.quantiles(all_latencies, n=100)[98] if all_latencies else 0,
                packet_loss_percent=((frame_count - frames_rx) / frame_count * 100) if frame_count > 0 else 0,
                jitter_ms=statistics.stdev(all_latencies) if len(all_latencies) > 1 else 0,
                cpu_usage_percent=0,  # TODO: Implement CPU monitoring
                memory_usage_mb=0,    # TODO: Implement memory monitoring  
                sync_frames=sync_count,
                timestamp=time.time(),
                duration_sec=total_time
            )
    
    def run_tcp_test(
        self, 
        condition: NetworkCondition,
        frame_count: int,
        payload_size: int
    ) -> TestResult:
        """Run TCP baseline test."""
        duration = max(5.0, frame_count * 0.001)  # Estimate duration
        
        tcp_client = TCPTestClient()
        
        with self.simulator.apply_conditions(condition):
            # Start server
            server_result = tcp_client.run_server(duration)
            
            # Run client  
            client_result = tcp_client.run_client("127.0.0.1", duration, payload_size)
            
            return TestResult(
                scenario_name="tcp_baseline",
                protocol="tcp",
                frame_count=frame_count,
                payload_size=payload_size,
                window_size=0,
                network_condition=condition.name,
                throughput_mbps=client_result.get('throughput_mbps', 0),
                latency_avg_ms=client_result.get('mean_rtt', 0),
                latency_p95_ms=0,  # iperf3 doesn't provide percentiles
                latency_p99_ms=0,
                packet_loss_percent=0,  # TCP handles this
                jitter_ms=0,
                cpu_usage_percent=client_result.get('cpu_usage', 0),
                memory_usage_mb=0,
                retransmissions=client_result.get('retransmissions', 0),
                timestamp=time.time(),
                duration_sec=duration
            )
    
    def run_udp_test(
        self,
        condition: NetworkCondition,
        frame_count: int,
        payload_size: int
    ) -> TestResult:
        """Run UDP baseline test."""
        duration = max(5.0, frame_count * 0.001)
        bandwidth_estimate = min(1000, condition.bandwidth_mbps)  # Conservative estimate
        
        udp_client = UDPTestClient()
        
        with self.simulator.apply_conditions(condition):
            result = udp_client.run_test("127.0.0.1", duration, payload_size, bandwidth_estimate)
            
            return TestResult(
                scenario_name="udp_baseline",
                protocol="udp", 
                frame_count=frame_count,
                payload_size=payload_size,
                window_size=0,
                network_condition=condition.name,
                throughput_mbps=result.get('throughput_mbps', 0),
                latency_avg_ms=0,  # UDP doesn't track latency in iperf3
                latency_p95_ms=0,
                latency_p99_ms=0,
                packet_loss_percent=result.get('packet_loss', 0),
                jitter_ms=result.get('jitter_ms', 0),
                cpu_usage_percent=result.get('cpu_usage', 0),
                memory_usage_mb=0,
                timestamp=time.time(),
                duration_sec=duration
            )
    
    def run_comprehensive_tests(self, scenarios: List[TestScenario]) -> List[TestResult]:
        """Run comprehensive test suite."""
        all_results = []
        
        for scenario in scenarios:
            print(f"\n🚀 Running scenario: {scenario.name}")
            
            for condition in scenario.network_conditions:
                print(f"  📡 Network condition: {condition.name}")
                
                for frame_count in scenario.frame_counts:
                    for payload_size in scenario.payload_sizes:
                        for window_size in scenario.window_sizes:
                            
                            if "packetfs" in scenario.protocols:
                                try:
                                    result = self.run_packetfs_test(condition, frame_count, payload_size, window_size)
                                    all_results.append(result)
                                    print(f"    ✅ PacketFS: {result.throughput_mbps:.2f} Mbps, {result.latency_avg_ms:.2f}ms avg latency")
                                except Exception as e:
                                    print(f"    ❌ PacketFS test failed: {e}")
                            
                            if "tcp" in scenario.protocols:
                                try:
                                    result = self.run_tcp_test(condition, frame_count, payload_size)
                                    all_results.append(result)
                                    print(f"    ✅ TCP: {result.throughput_mbps:.2f} Mbps, {result.retransmissions} retx")
                                except Exception as e:
                                    print(f"    ❌ TCP test failed: {e}")
                            
                            if "udp" in scenario.protocols:
                                try:
                                    result = self.run_udp_test(condition, frame_count, payload_size)
                                    all_results.append(result)
                                    print(f"    ✅ UDP: {result.throughput_mbps:.2f} Mbps, {result.packet_loss_percent:.2f}% loss")
                                except Exception as e:
                                    print(f"    ❌ UDP test failed: {e}")
                            
                            # Brief pause between tests
                            time.sleep(0.5)
        
        self.results.extend(all_results)
        return all_results
    
    def save_results(self, filename: str):
        """Save test results to JSON file."""
        results_dict = [asdict(result) for result in self.results]
        with open(filename, 'w') as f:
            json.dump(results_dict, f, indent=2)
        print(f"📊 Saved {len(self.results)} test results to {filename}")
    
    def generate_comparison_report(self, results: List[TestResult]) -> str:
        """Generate comparative performance report."""
        report = []
        report.append("=" * 80)
        report.append("📊 PACKETFS vs TCP/UDP PERFORMANCE COMPARISON")
        report.append("=" * 80)
        
        # Group results by network condition and test parameters
        grouped = {}
        for result in results:
            key = (result.network_condition, result.frame_count, result.payload_size)
            if key not in grouped:
                grouped[key] = {}
            grouped[key][result.protocol] = result
        
        report.append(f"{'Condition':<15} {'Frames':<8} {'Payload':<8} {'Protocol':<10} {'Throughput':<12} {'Latency':<10} {'Loss%':<8}")
        report.append("-" * 80)
        
        for key, protocols in grouped.items():
            condition, frames, payload = key
            
            for protocol, result in protocols.items():
                report.append(f"{condition:<15} {frames:<8} {payload:<8} {protocol:<10} "
                            f"{result.throughput_mbps:<12.2f} {result.latency_avg_ms:<10.2f} "
                            f"{result.packet_loss_percent:<8.2f}")
        
        return "\n".join(report)


# Test scenarios definitions
NETWORK_CONDITIONS = [
    NetworkCondition("perfect", 0, 0, 0, 1000),
    NetworkCondition("lan", 1, 0.1, 0, 1000),  
    NetworkCondition("wan", 50, 5, 0.1, 100),
    NetworkCondition("mobile", 100, 20, 1, 10),
    NetworkCondition("congested", 25, 10, 5, 50),
    NetworkCondition("lossy", 20, 5, 10, 100),
]

QUICK_SCENARIO = TestScenario(
    name="quick_test",
    frame_counts=[100, 500],
    payload_sizes=[64, 256],
    window_sizes=[64, 256], 
    network_conditions=[
        NetworkCondition("perfect", 0, 0, 0, 1000),
        NetworkCondition("lan", 1, 0.1, 0, 1000),
    ],
    protocols=["packetfs", "tcp", "udp"]
)

COMPREHENSIVE_SCENARIO = TestScenario(
    name="comprehensive_test", 
    frame_counts=[100, 500, 1000],
    payload_sizes=[64, 256, 512, 1024],
    window_sizes=[64, 256, 1024],
    network_conditions=NETWORK_CONDITIONS,
    protocols=["packetfs", "tcp", "udp"]
)


class TestNetworkSimulation:
    """Test network simulation framework."""
    
    @pytest.mark.skipif(
        os.geteuid() != 0,
        reason="Network simulation tests require root privileges"
    )
    def test_network_conditions(self):
        """Test network condition application."""
        simulator = NetworkSimulator("lo")
        
        condition = NetworkCondition(
            name="test_condition",
            delay_ms=10,
            jitter_ms=2,
            loss_percent=1
        )
        
        with simulator.apply_conditions(condition):
            # Test that conditions are applied
            result = subprocess.run(["tc", "qdisc", "show", "dev", "lo"], 
                                  capture_output=True, text=True)
            assert "netem" in result.stdout
    
    def test_packetfs_client(self):
        """Test PacketFS client functionality."""
        try:
            import packetfs._bitpack
        except ImportError:
            pytest.skip("C extension not available")
        
        config = SyncConfig(window_pow2=6, window_crc16=True)
        client = PacketFSTestClient("lo", config)
        
        # Test basic functionality
        duration, latencies = client.send_test_data(64, 10)
        assert duration > 0
        assert len(latencies) == 10
        assert all(lat >= 0 for lat in latencies)
    
    @pytest.mark.skipif(
        os.geteuid() != 0,
        reason="Integration tests require root privileges"  
    )
    def test_quick_scenario(self):
        """Run quick test scenario."""
        suite = ComprehensiveTestSuite("lo")
        results = suite.run_comprehensive_tests([QUICK_SCENARIO])
        
        assert len(results) > 0
        
        # Verify we have results for each protocol
        protocols = set(r.protocol for r in results)
        assert "packetfs" in protocols
        
        # Generate and print report
        report = suite.generate_comparison_report(results)
        print(report)
        
        # Save results
        suite.save_results("/tmp/quick_test_results.json")


if __name__ == "__main__":
    # Example usage
    print("🧪 PacketFS Network Simulation Testing")
    print("Note: This requires root privileges for network simulation")
    
    if os.geteuid() != 0:
        print("❌ Please run as root for network simulation tests")
        exit(1)
    
    # Run quick scenario
    suite = ComprehensiveTestSuite("lo")
    results = suite.run_comprehensive_tests([QUICK_SCENARIO])
    
    # Generate report
    report = suite.generate_comparison_report(results)
    print(report)
    
    # Save results
    suite.save_results("network_simulation_results.json")
    
    print(f"\n🏁 Testing complete! {len(results)} tests run.")
