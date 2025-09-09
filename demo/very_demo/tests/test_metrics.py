#!/usr/bin/env python3
"""
Enhanced performance metrics and benchmarking for PacketFS.
Includes Prometheus-style metrics, latency histograms, and regression detection.
"""
import pytest
import time
import json
import statistics
import threading
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path

# Optional Prometheus integration
try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

from packetfs.protocol import ProtocolEncoder, ProtocolDecoder, SyncConfig


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    test_name: str
    timestamp: float
    frame_count: int
    payload_size: int
    window_size: int
    
    # Timing metrics
    total_time_sec: float
    encode_time_sec: float
    decode_time_sec: float
    
    # Throughput metrics
    frames_per_second: float
    bits_per_second: float
    refs_per_second: float
    
    # Latency metrics
    avg_latency_us: float
    min_latency_us: float
    max_latency_us: float
    p50_latency_us: float
    p95_latency_us: float
    p99_latency_us: float
    latency_stdev_us: float
    
    # Resource metrics
    peak_memory_bytes: int
    peak_cpu_percent: float
    
    # Protocol metrics
    sync_frames: int
    sync_rate_percent: float
    crc_errors: int
    bit_packing_efficiency: float
    
    # Additional metrics
    custom_metrics: Dict[str, Any]


class PrometheusMetrics:
    """Prometheus metrics collector for PacketFS"""
    
    def __init__(self, registry=None):
        if not HAS_PROMETHEUS:
            return
        
        # Use custom registry to avoid conflicts during testing
        self.registry = registry or CollectorRegistry()
            
        # Define metrics
        self.latency_histogram = Histogram(
            'packetfs_latency_seconds',
            'PacketFS operation latency in seconds',
            ['operation', 'tier'],
            registry=self.registry
        )
        
        self.throughput_gauge = Gauge(
            'packetfs_throughput_pps',
            'PacketFS throughput in packets per second',
            ['direction'],
            registry=self.registry
        )
        
        self.crc_errors_counter = Counter(
            'packetfs_crc_errors_total',
            'Total CRC errors detected',
            registry=self.registry
        )
        
        self.sync_frames_counter = Counter(
            'packetfs_sync_frames_total',
            'Total sync frames processed',
            registry=self.registry
        )
        
        self.bits_packed_counter = Counter(
            'packetfs_bits_packed_total',
            'Total bits packed',
            ['tier'],
            registry=self.registry
        )
        
        self.frame_size_histogram = Histogram(
            'packetfs_frame_size_bytes',
            'PacketFS frame size distribution in bytes',
            registry=self.registry
        )
    
    def record_latency(self, operation: str, tier: str, latency_seconds: float):
        """Record operation latency"""
        if HAS_PROMETHEUS:
            self.latency_histogram.labels(operation=operation, tier=tier).observe(latency_seconds)
    
    def record_throughput(self, direction: str, pps: float):
        """Record throughput measurement"""
        if HAS_PROMETHEUS:
            self.throughput_gauge.labels(direction=direction).set(pps)
    
    def record_crc_error(self):
        """Record CRC error"""
        if HAS_PROMETHEUS:
            self.crc_errors_counter.inc()
    
    def record_sync_frame(self):
        """Record sync frame"""
        if HAS_PROMETHEUS:
            self.sync_frames_counter.inc()
    
    def record_bits_packed(self, tier: str, bits: int):
        """Record bits packed"""
        if HAS_PROMETHEUS:
            self.bits_packed_counter.labels(tier=tier).inc(bits)
    
    def record_frame_size(self, size_bytes: int):
        """Record frame size"""
        if HAS_PROMETHEUS:
            self.frame_size_histogram.observe(size_bytes)


class LatencyTracker:
    """High-precision latency tracking"""
    
    def __init__(self):
        self.measurements = []
        self.start_time = None
    
    def start(self):
        """Start timing measurement"""
        self.start_time = time.perf_counter()
    
    def stop(self) -> float:
        """Stop timing and record measurement"""
        if self.start_time is None:
            raise ValueError("Timer not started")
        
        latency = time.perf_counter() - self.start_time
        self.measurements.append(latency)
        self.start_time = None
        return latency
    
    def get_statistics(self) -> Dict[str, float]:
        """Calculate latency statistics"""
        if not self.measurements:
            return {}
        
        sorted_measurements = sorted(self.measurements)
        n = len(sorted_measurements)
        
        return {
            'count': n,
            'mean': statistics.mean(self.measurements),
            'median': statistics.median(self.measurements),
            'min': min(self.measurements),
            'max': max(self.measurements),
            'stdev': statistics.stdev(self.measurements) if n > 1 else 0.0,
            'p50': sorted_measurements[int(0.50 * n)],
            'p95': sorted_measurements[int(0.95 * n)],
            'p99': sorted_measurements[int(0.99 * n)],
        }
    
    def reset(self):
        """Reset all measurements"""
        self.measurements.clear()
        self.start_time = None


class BenchmarkSuite:
    """Comprehensive benchmarking suite"""
    
    def __init__(self, prometheus_port: Optional[int] = None):
        # Create custom registry to avoid conflicts
        registry = CollectorRegistry() if HAS_PROMETHEUS else None
        self.prometheus_metrics = PrometheusMetrics(registry)
        self.results = []
        
        # Start Prometheus server if requested
        if prometheus_port and HAS_PROMETHEUS:
            start_http_server(prometheus_port)
    
    def run_encoding_benchmark(
        self, 
        config: SyncConfig,
        frame_count: int = 1000,
        payload_sizes: List[int] = [64, 256, 1024],
        tier_mix: List[int] = [0, 1, 2]
    ) -> List[PerformanceMetrics]:
        """Run comprehensive encoding benchmark"""
        
        try:
            import packetfs._bitpack
        except ImportError:
            pytest.skip("C extension not available")
        
        results = []
        
        for payload_size in payload_sizes:
            for tier in tier_mix:
                metrics = self._run_single_encoding_test(
                    config, frame_count, payload_size, tier
                )
                results.append(metrics)
                self.results.append(metrics)
        
        return results
    
    def _run_single_encoding_test(
        self,
        config: SyncConfig,
        frame_count: int,
        payload_size: int,
        tier: int
    ) -> PerformanceMetrics:
        """Run single encoding performance test"""
        
        encoder = ProtocolEncoder(config)
        latency_tracker = LatencyTracker()
        out = bytearray(payload_size * 2)  # Generous buffer
        
        # Generate test data
        refs = bytes([i % 256 for i in range(payload_size)])
        
        # Warm-up
        for _ in range(10):
            encoder.pack_refs(out, tier, refs, 8)
        
        # Actual benchmark
        start_time = time.perf_counter()
        sync_frames = 0
        total_bits = 0
        
        for i in range(frame_count):
            latency_tracker.start()
            bits = encoder.pack_refs(out, tier, refs, 8)
            encode_latency = latency_tracker.stop()
            
            total_bits += bits
            sync_frame = encoder.maybe_sync()
            if sync_frame:
                sync_frames += 1
            
            # Record Prometheus metrics
            self.prometheus_metrics.record_latency('encode', str(tier), encode_latency)
            self.prometheus_metrics.record_bits_packed(str(tier), bits)
            if sync_frame:
                self.prometheus_metrics.record_sync_frame()
        
        total_time = time.perf_counter() - start_time
        
        # Calculate metrics
        latency_stats = latency_tracker.get_statistics()
        fps = frame_count / total_time if total_time > 0 else 0
        bps = total_bits / total_time if total_time > 0 else 0
        refs_per_sec = (frame_count * payload_size) / total_time if total_time > 0 else 0
        
        # Record throughput
        self.prometheus_metrics.record_throughput('encode', fps)
        
        return PerformanceMetrics(
            test_name=f"encode_t{tier}_f{frame_count}_p{payload_size}",
            timestamp=time.time(),
            frame_count=frame_count,
            payload_size=payload_size,
            window_size=1 << config.window_pow2,
            total_time_sec=total_time,
            encode_time_sec=total_time,
            decode_time_sec=0.0,
            frames_per_second=fps,
            bits_per_second=bps,
            refs_per_second=refs_per_sec,
            avg_latency_us=latency_stats.get('mean', 0) * 1e6,
            min_latency_us=latency_stats.get('min', 0) * 1e6,
            max_latency_us=latency_stats.get('max', 0) * 1e6,
            p50_latency_us=latency_stats.get('p50', 0) * 1e6,
            p95_latency_us=latency_stats.get('p95', 0) * 1e6,
            p99_latency_us=latency_stats.get('p99', 0) * 1e6,
            latency_stdev_us=latency_stats.get('stdev', 0) * 1e6,
            peak_memory_bytes=0,  # TODO: Implement memory tracking
            peak_cpu_percent=0,   # TODO: Implement CPU tracking
            sync_frames=sync_frames,
            sync_rate_percent=(sync_frames / frame_count) * 100 if frame_count > 0 else 0,
            crc_errors=0,
            bit_packing_efficiency=total_bits / (frame_count * payload_size * 8) if frame_count > 0 else 0,
            custom_metrics={
                'tier': tier,
                'window_pow2': config.window_pow2,
                'crc_enabled': config.window_crc16
            }
        )
    
    def run_stress_test(
        self,
        config: SyncConfig,
        duration_seconds: float = 10.0,
        target_fps: int = 10000
    ) -> PerformanceMetrics:
        """Run stress test at target frame rate"""
        
        try:
            import packetfs._bitpack
        except ImportError:
            pytest.skip("C extension not available")
        
        encoder = ProtocolEncoder(config)
        out = bytearray(1000)
        refs = bytes(range(64))  # 64-byte payload
        
        frame_count = 0
        sync_frames = 0
        start_time = time.perf_counter()
        target_interval = 1.0 / target_fps
        
        while (time.perf_counter() - start_time) < duration_seconds:
            frame_start = time.perf_counter()
            
            bits = encoder.pack_refs(out, 0, refs, 8)
            sync_frame = encoder.maybe_sync()
            
            frame_count += 1
            if sync_frame:
                sync_frames += 1
            
            # Maintain target frame rate
            elapsed = time.perf_counter() - frame_start
            if elapsed < target_interval:
                time.sleep(target_interval - elapsed)
        
        total_time = time.perf_counter() - start_time
        actual_fps = frame_count / total_time
        
        return PerformanceMetrics(
            test_name=f"stress_{target_fps}fps_{duration_seconds}s",
            timestamp=time.time(),
            frame_count=frame_count,
            payload_size=64,
            window_size=1 << config.window_pow2,
            total_time_sec=total_time,
            encode_time_sec=total_time,
            decode_time_sec=0.0,
            frames_per_second=actual_fps,
            bits_per_second=0,
            refs_per_second=0,
            avg_latency_us=0,
            min_latency_us=0,
            max_latency_us=0,
            p50_latency_us=0,
            p95_latency_us=0,
            p99_latency_us=0,
            latency_stdev_us=0,
            peak_memory_bytes=0,
            peak_cpu_percent=0,
            sync_frames=sync_frames,
            sync_rate_percent=(sync_frames / frame_count) * 100 if frame_count > 0 else 0,
            crc_errors=0,
            bit_packing_efficiency=0,
            custom_metrics={
                'target_fps': target_fps,
                'achieved_fps_ratio': actual_fps / target_fps if target_fps > 0 else 0
            }
        )
    
    def save_results(self, filename: str):
        """Save benchmark results to JSON file"""
        results_dict = [asdict(result) for result in self.results]
        
        with open(filename, 'w') as f:
            json.dump(results_dict, f, indent=2)
        
        print(f"Saved {len(self.results)} benchmark results to {filename}")
    
    def load_baseline(self, filename: str) -> List[PerformanceMetrics]:
        """Load baseline results from JSON file"""
        try:
            with open(filename, 'r') as f:
                results_data = json.load(f)
            
            return [PerformanceMetrics(**data) for data in results_data]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load baseline from {filename}: {e}")
            return []
    
    def compare_with_baseline(
        self,
        baseline_filename: str,
        threshold_percent: float = 5.0
    ) -> Dict[str, Any]:
        """Compare current results with baseline"""
        
        baseline_results = self.load_baseline(baseline_filename)
        if not baseline_results:
            return {'status': 'no_baseline', 'regressions': []}
        
        # Create baseline lookup by test name
        baseline_lookup = {result.test_name: result for result in baseline_results}
        
        regressions = []
        improvements = []
        
        for current in self.results:
            baseline = baseline_lookup.get(current.test_name)
            if not baseline:
                continue
            
            # Compare key metrics
            fps_change = ((current.frames_per_second - baseline.frames_per_second) / 
                         baseline.frames_per_second * 100)
            
            latency_change = ((current.avg_latency_us - baseline.avg_latency_us) / 
                             baseline.avg_latency_us * 100) if baseline.avg_latency_us > 0 else 0
            
            # Check for regressions
            if fps_change < -threshold_percent:
                regressions.append({
                    'test_name': current.test_name,
                    'metric': 'frames_per_second',
                    'baseline': baseline.frames_per_second,
                    'current': current.frames_per_second,
                    'change_percent': fps_change
                })
            
            if latency_change > threshold_percent:
                regressions.append({
                    'test_name': current.test_name,
                    'metric': 'avg_latency_us',
                    'baseline': baseline.avg_latency_us,
                    'current': current.avg_latency_us,
                    'change_percent': latency_change
                })
            
            # Track improvements
            if fps_change > threshold_percent:
                improvements.append({
                    'test_name': current.test_name,
                    'metric': 'frames_per_second',
                    'change_percent': fps_change
                })
        
        return {
            'status': 'regression' if regressions else 'pass',
            'regressions': regressions,
            'improvements': improvements,
            'threshold_percent': threshold_percent
        }


class TestMetricsAndBenchmarks:
    """Test metrics collection and benchmarking"""
    
    def test_latency_tracker(self):
        """Test latency tracking functionality"""
        tracker = LatencyTracker()
        
        # Record some measurements
        for i in range(100):
            tracker.start()
            time.sleep(0.001)  # 1ms
            tracker.stop()
        
        stats = tracker.get_statistics()
        
        assert stats['count'] == 100
        assert 0.0008 < stats['mean'] < 0.0012  # Around 1ms
        assert stats['min'] > 0
        assert stats['max'] > stats['min']
        assert stats['p99'] >= stats['p95']
        assert stats['p95'] >= stats['p50']
    
    def test_prometheus_metrics(self):
        """Test Prometheus metrics collection"""
        if not HAS_PROMETHEUS:
            pytest.skip("Prometheus client not available")
        
        metrics = PrometheusMetrics()
        
        # Record some metrics
        metrics.record_latency('encode', 'L1', 0.001)
        metrics.record_throughput('tx', 1000.0)
        metrics.record_crc_error()
        metrics.record_sync_frame()
        metrics.record_bits_packed('L1', 128)
        metrics.record_frame_size(64)
        
        # Should not raise exceptions
        assert True
    
    def test_benchmark_suite_basic(self):
        """Test basic benchmark suite functionality"""
        suite = BenchmarkSuite()
        
        config = SyncConfig(window_pow2=4, window_crc16=True)
        results = suite.run_encoding_benchmark(
            config, 
            frame_count=100, 
            payload_sizes=[32, 64],
            tier_mix=[0, 1]
        )
        
        assert len(results) == 4  # 2 payload sizes × 2 tiers
        
        for result in results:
            assert result.frame_count == 100
            assert result.frames_per_second > 0
            assert result.total_time_sec > 0
            assert result.payload_size in [32, 64]
    
    def test_stress_test(self):
        """Test stress testing functionality"""
        suite = BenchmarkSuite()
        config = SyncConfig(window_pow2=6, window_crc16=True)
        
        result = suite.run_stress_test(
            config,
            duration_seconds=1.0,
            target_fps=5000
        )
        
        assert result.frame_count > 0
        assert result.total_time_sec > 0
        assert result.frames_per_second > 0
        # Should achieve reasonable percentage of target
        assert result.custom_metrics['achieved_fps_ratio'] > 0.5
    
    def test_baseline_comparison(self):
        """Test baseline comparison functionality"""
        suite = BenchmarkSuite()
        
        # Create fake baseline
        baseline_results = [
            PerformanceMetrics(
                test_name="test_1",
                timestamp=time.time(),
                frame_count=100,
                payload_size=64,
                window_size=64,
                total_time_sec=1.0,
                encode_time_sec=1.0,
                decode_time_sec=0.0,
                frames_per_second=100.0,
                bits_per_second=1000.0,
                refs_per_second=6400.0,
                avg_latency_us=10.0,
                min_latency_us=5.0,
                max_latency_us=20.0,
                p50_latency_us=9.0,
                p95_latency_us=18.0,
                p99_latency_us=19.0,
                latency_stdev_us=3.0,
                peak_memory_bytes=1024,
                peak_cpu_percent=50.0,
                sync_frames=1,
                sync_rate_percent=1.0,
                crc_errors=0,
                bit_packing_efficiency=1.0,
                custom_metrics={}
            )
        ]
        
        # Save baseline
        baseline_file = "/tmp/test_baseline.json"
        with open(baseline_file, 'w') as f:
            json.dump([asdict(r) for r in baseline_results], f)
        
        # Add a regression result
        suite.results = [
            PerformanceMetrics(
                test_name="test_1",
                timestamp=time.time(),
                frame_count=100,
                payload_size=64,
                window_size=64,
                total_time_sec=1.0,
                encode_time_sec=1.0,
                decode_time_sec=0.0,
                frames_per_second=80.0,  # 20% slower
                bits_per_second=800.0,
                refs_per_second=5120.0,
                avg_latency_us=15.0,  # 50% higher latency
                min_latency_us=7.0,
                max_latency_us=30.0,
                p50_latency_us=14.0,
                p95_latency_us=28.0,
                p99_latency_us=29.0,
                latency_stdev_us=5.0,
                peak_memory_bytes=1024,
                peak_cpu_percent=50.0,
                sync_frames=1,
                sync_rate_percent=1.0,
                crc_errors=0,
                bit_packing_efficiency=1.0,
                custom_metrics={}
            )
        ]
        
        comparison = suite.compare_with_baseline(baseline_file, threshold_percent=5.0)
        
        assert comparison['status'] == 'regression'
        assert len(comparison['regressions']) == 2  # FPS and latency regressions
        
        # Cleanup
        Path(baseline_file).unlink(missing_ok=True)


if __name__ == '__main__':
    # Example usage
    suite = BenchmarkSuite()
    
    config = SyncConfig(window_pow2=6, window_crc16=True)
    
    print("Running encoding benchmarks...")
    results = suite.run_encoding_benchmark(config, frame_count=1000)
    
    print("Running stress test...")
    stress_result = suite.run_stress_test(config, duration_seconds=2.0, target_fps=5000)
    
    suite.save_results("benchmark_results.json")
    
    pytest.main([__file__, '-v'])
