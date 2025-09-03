#!/usr/bin/env python3
"""
Simple PacketFS Performance Testing
Tests PacketFS protocol performance without requiring root privileges.
"""
import time
import json
import statistics
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
from pathlib import Path

# Import PacketFS modules
try:
    from packetfs.protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig
    from packetfs.seed_pool import SeedPool
except ImportError as e:
    print(f"❌ Failed to import PacketFS modules: {e}")
    print("Make sure PacketFS is installed: pip install -e .")
    exit(1)


@dataclass
class SimpleTestResult:
    """Simple test result metrics."""
    test_name: str
    payload_size: int
    frame_count: int
    window_size: int
    
    # Encoding performance
    encode_fps: float
    encode_mbps: float
    encode_latency_avg_us: float
    encode_latency_p95_us: float
    
    # Decoding performance  
    decode_fps: float
    decode_latency_avg_us: float
    
    # Protocol metrics
    sync_frames: int
    bit_efficiency: float
    total_bits: int
    
    # Test metadata
    timestamp: float
    duration_sec: float


class SimplePacketFSTester:
    """Simple PacketFS performance tester."""
    
    def __init__(self):
        self.results = []
    
    def run_encode_test(
        self, 
        payload_size: int, 
        frame_count: int, 
        window_size: int
    ) -> SimpleTestResult:
        """Run encoding performance test."""
        
        print(f"🚀 Testing encode: {frame_count} frames × {payload_size} bytes, window={window_size}")
        
        config = SyncConfig(
            window_pow2=window_size.bit_length() - 1,
            window_crc16=True
        )
        
        encoder = ProtocolEncoder(config)
        decoder = ProtocolDecoder(config)
        
        # Prepare test data
        out = bytearray(payload_size * 2)
        all_payloads = []
        encode_latencies = []
        sync_count = 0
        total_bits = 0
        
        # Encoding test
        start_time = time.time()
        
        for i in range(frame_count):
            # Generate test references
            refs = bytes([j % 256 for j in range(payload_size)])
            
            # Measure encoding latency
            encode_start = time.perf_counter()
            
            bits = encoder.pack_refs(out, 0, refs, 8)
            sync_frame = encoder.maybe_sync()
            
            encode_end = time.perf_counter()
            encode_latencies.append((encode_end - encode_start) * 1e6)  # Convert to microseconds
            
            # Create payload
            payload_bytes = (bits + 7) // 8
            payload = bytes(out[:payload_bytes])
            if sync_frame:
                payload += sync_frame
                sync_count += 1
            
            all_payloads.append(payload)
            total_bits += bits
        
        encode_total_time = time.time() - start_time
        
        # Decoding test
        decode_latencies = []
        frames_decoded = 0
        
        decode_start_time = time.time()
        
        for payload in all_payloads:
            decode_start = time.perf_counter()
            
            # Simulate packet processing
            sync_info = decoder.scan_for_sync(payload)
            if sync_info is not None:
                frames_decoded += 1
            
            decode_end = time.perf_counter()
            decode_latencies.append((decode_end - decode_start) * 1e6)  # Convert to microseconds
        
        decode_total_time = time.time() - decode_start_time
        
        # Calculate metrics
        encode_fps = frame_count / encode_total_time if encode_total_time > 0 else 0
        decode_fps = frames_decoded / decode_total_time if decode_total_time > 0 else 0
        
        encode_mbps = (total_bits / 1e6) / encode_total_time if encode_total_time > 0 else 0
        bit_efficiency = total_bits / (frame_count * payload_size * 8) if frame_count > 0 else 0
        
        result = SimpleTestResult(
            test_name=f"simple_p{payload_size}_f{frame_count}_w{window_size}",
            payload_size=payload_size,
            frame_count=frame_count,
            window_size=window_size,
            encode_fps=encode_fps,
            encode_mbps=encode_mbps,
            encode_latency_avg_us=statistics.mean(encode_latencies),
            encode_latency_p95_us=statistics.quantiles(encode_latencies, n=20)[18],
            decode_fps=decode_fps,
            decode_latency_avg_us=statistics.mean(decode_latencies),
            sync_frames=sync_count,
            bit_efficiency=bit_efficiency,
            total_bits=total_bits,
            timestamp=time.time(),
            duration_sec=encode_total_time + decode_total_time
        )
        
        print(f"  ✅ Encode: {encode_fps:.0f} fps, {encode_mbps:.2f} Mbps, {result.encode_latency_avg_us:.2f}μs avg")
        print(f"  ✅ Decode: {decode_fps:.0f} fps, {result.decode_latency_avg_us:.2f}μs avg")
        print(f"  📊 Sync frames: {sync_count}, Bit efficiency: {bit_efficiency:.4f}")
        
        return result
    
    def run_comprehensive_tests(self) -> List[SimpleTestResult]:
        """Run comprehensive test suite."""
        
        test_scenarios = [
            # Small payloads - high frequency
            (64, 1000, 64),
            (64, 1000, 256),
            (64, 1000, 1024),
            
            # Medium payloads
            (256, 1000, 64),
            (256, 1000, 256), 
            (256, 1000, 1024),
            
            # Large payloads
            (1024, 500, 64),
            (1024, 500, 256),
            (1024, 500, 1024),
            
            # Very large payloads
            (4096, 100, 256),
            (4096, 100, 1024),
            (4096, 100, 4096),
            
            # Stress test
            (128, 5000, 256),
            (512, 2000, 512),
        ]
        
        results = []
        
        print("🧪 Running comprehensive PacketFS performance tests...")
        print("-" * 60)
        
        for payload_size, frame_count, window_size in test_scenarios:
            try:
                result = self.run_encode_test(payload_size, frame_count, window_size)
                results.append(result)
                self.results.append(result)
            except Exception as e:
                print(f"  ❌ Test failed: {e}")
        
        return results
    
    def save_results(self, filename: str):
        """Save test results to JSON file."""
        results_dict = [asdict(result) for result in self.results]
        with open(filename, 'w') as f:
            json.dump(results_dict, f, indent=2)
        print(f"📊 Saved {len(self.results)} test results to {filename}")
    
    def generate_summary_report(self, results: List[SimpleTestResult]) -> str:
        """Generate performance summary report."""
        report = []
        report.append("=" * 80)
        report.append("📊 PACKETFS SIMPLE PERFORMANCE TEST RESULTS")
        report.append("=" * 80)
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Tests: {len(results)}")
        report.append("")
        
        # Performance summary table
        report.append(f"{'Test':<25} {'Payload':<8} {'Frames':<8} {'Encode FPS':<12} {'Encode Mbps':<12} {'Latency μs':<12}")
        report.append("-" * 80)
        
        for result in results:
            report.append(f"{result.test_name:<25} {result.payload_size:<8} {result.frame_count:<8} "
                         f"{result.encode_fps:<12.0f} {result.encode_mbps:<12.2f} {result.encode_latency_avg_us:<12.2f}")
        
        report.append("")
        
        # Statistics
        encode_fps_values = [r.encode_fps for r in results]
        encode_mbps_values = [r.encode_mbps for r in results]
        latency_values = [r.encode_latency_avg_us for r in results]
        
        report.append("📈 PERFORMANCE STATISTICS")
        report.append("-" * 40)
        report.append(f"Max Encode FPS: {max(encode_fps_values):,.0f}")
        report.append(f"Avg Encode FPS: {statistics.mean(encode_fps_values):,.0f}")
        report.append(f"Max Throughput: {max(encode_mbps_values):.2f} Mbps")
        report.append(f"Avg Throughput: {statistics.mean(encode_mbps_values):.2f} Mbps")
        report.append(f"Min Latency: {min(latency_values):.2f} μs")
        report.append(f"Avg Latency: {statistics.mean(latency_values):.2f} μs")
        
        # Payload size analysis
        report.append("")
        report.append("📊 PAYLOAD SIZE ANALYSIS")
        report.append("-" * 40)
        
        payload_groups = {}
        for result in results:
            size = result.payload_size
            if size not in payload_groups:
                payload_groups[size] = []
            payload_groups[size].append(result)
        
        for size in sorted(payload_groups.keys()):
            group_results = payload_groups[size]
            avg_fps = statistics.mean([r.encode_fps for r in group_results])
            avg_mbps = statistics.mean([r.encode_mbps for r in group_results])
            avg_latency = statistics.mean([r.encode_latency_avg_us for r in group_results])
            
            report.append(f"{size:4d} bytes: {avg_fps:8.0f} fps, {avg_mbps:8.2f} Mbps, {avg_latency:8.2f} μs")
        
        return "\n".join(report)


def main():
    """Run simple PacketFS performance tests."""
    print("🚀 PacketFS Simple Performance Testing Suite")
    print("No root privileges required!")
    print("")
    
    tester = SimplePacketFSTester()
    
    try:
        # Run comprehensive tests
        results = tester.run_comprehensive_tests()
        
        print("\n" + "=" * 60)
        print(f"🏁 Testing completed! {len(results)} tests run.")
        
        # Generate and display report
        report = tester.generate_summary_report(results)
        print("\n" + report)
        
        # Save results
        output_file = "simple_packetfs_results.json"
        tester.save_results(output_file)
        
        # Save report
        report_file = "simple_packetfs_report.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"📄 Saved performance report to {report_file}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Testing interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Testing failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
