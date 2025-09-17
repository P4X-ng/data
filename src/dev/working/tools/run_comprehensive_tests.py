#!/usr/bin/env python3
"""
Comprehensive PacketFS Testing Automation Script
Runs multiple test scenarios, compares against baselines, and generates detailed reports.
"""
import argparse
import sys
import os
import time
import json
import subprocess
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from typing import List, Dict, Any

# Add src directory to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))

try:
    from test_network_simulation import (
        ComprehensiveTestSuite,
        NetworkCondition,
        TestScenario,
        TestResult,
        NETWORK_CONDITIONS,
        QUICK_SCENARIO,
        COMPREHENSIVE_SCENARIO,
    )
    from test_metrics import BenchmarkSuite, PerformanceMetrics
    from packetfs.protocol import SyncConfig
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}")
    print("Make sure you're running from the PacketFS project directory")
    sys.exit(1)


class TestReportGenerator:
    """Generate detailed testing reports with visualizations."""

    def __init__(self, results: List[TestResult]):
        self.results = results
        self.df = self._create_dataframe()

    def _create_dataframe(self) -> pd.DataFrame:
        """Convert test results to pandas DataFrame for analysis."""
        data = []
        for result in self.results:
            data.append(
                {
                    "protocol": result.protocol,
                    "network_condition": result.network_condition,
                    "frame_count": result.frame_count,
                    "payload_size": result.payload_size,
                    "window_size": result.window_size,
                    "throughput_mbps": result.throughput_mbps,
                    "latency_avg_ms": result.latency_avg_ms,
                    "latency_p95_ms": result.latency_p95_ms,
                    "latency_p99_ms": result.latency_p99_ms,
                    "packet_loss_percent": result.packet_loss_percent,
                    "jitter_ms": result.jitter_ms,
                    "cpu_usage_percent": result.cpu_usage_percent,
                    "sync_frames": result.sync_frames,
                    "retransmissions": result.retransmissions,
                    "duration_sec": result.duration_sec,
                }
            )
        return pd.DataFrame(data)

    def generate_throughput_comparison_plot(self, filename: str):
        """Generate throughput comparison plots."""
        plt.figure(figsize=(15, 10))

        # Plot 1: Throughput by protocol and network condition
        plt.subplot(2, 2, 1)
        throughput_pivot = self.df.pivot_table(
            values="throughput_mbps",
            index="network_condition",
            columns="protocol",
            aggfunc="mean",
        )
        throughput_pivot.plot(kind="bar", ax=plt.gca())
        plt.title("Average Throughput by Network Condition")
        plt.ylabel("Throughput (Mbps)")
        plt.xticks(rotation=45)
        plt.legend(title="Protocol")

        # Plot 2: Latency comparison
        plt.subplot(2, 2, 2)
        latency_pivot = self.df.pivot_table(
            values="latency_avg_ms",
            index="network_condition",
            columns="protocol",
            aggfunc="mean",
        )
        latency_pivot.plot(kind="bar", ax=plt.gca())
        plt.title("Average Latency by Network Condition")
        plt.ylabel("Latency (ms)")
        plt.xticks(rotation=45)
        plt.legend(title="Protocol")

        # Plot 3: Packet loss comparison
        plt.subplot(2, 2, 3)
        loss_pivot = self.df.pivot_table(
            values="packet_loss_percent",
            index="network_condition",
            columns="protocol",
            aggfunc="mean",
        )
        loss_pivot.plot(kind="bar", ax=plt.gca())
        plt.title("Packet Loss by Network Condition")
        plt.ylabel("Packet Loss (%)")
        plt.xticks(rotation=45)
        plt.legend(title="Protocol")

        # Plot 4: Throughput vs Payload Size (PacketFS focus)
        plt.subplot(2, 2, 4)
        packetfs_data = self.df[self.df["protocol"] == "packetfs"]
        if not packetfs_data.empty:
            throughput_payload = packetfs_data.groupby("payload_size")[
                "throughput_mbps"
            ].mean()
            throughput_payload.plot(kind="line", marker="o", ax=plt.gca())
            plt.title("PacketFS Throughput vs Payload Size")
            plt.xlabel("Payload Size (bytes)")
            plt.ylabel("Throughput (Mbps)")
            plt.grid(True)

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"📈 Saved throughput comparison plot to {filename}")

    def generate_latency_distribution_plot(self, filename: str):
        """Generate latency distribution plots."""
        plt.figure(figsize=(12, 8))

        # Box plot of latency distributions
        plt.subplot(2, 1, 1)
        sns.boxplot(
            data=self.df, x="network_condition", y="latency_avg_ms", hue="protocol"
        )
        plt.title("Latency Distribution by Network Condition and Protocol")
        plt.ylabel("Average Latency (ms)")
        plt.xticks(rotation=45)

        # Violin plot for more detailed distribution
        plt.subplot(2, 1, 2)
        sns.violinplot(
            data=self.df, x="protocol", y="latency_avg_ms", hue="network_condition"
        )
        plt.title("Latency Distribution by Protocol and Network Condition")
        plt.ylabel("Average Latency (ms)")

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"📈 Saved latency distribution plot to {filename}")

    def generate_performance_heatmap(self, filename: str):
        """Generate performance heatmap."""
        plt.figure(figsize=(12, 8))

        # Create heatmap of throughput across conditions and protocols
        heatmap_data = self.df.pivot_table(
            values="throughput_mbps",
            index="network_condition",
            columns="protocol",
            aggfunc="mean",
        )

        sns.heatmap(
            heatmap_data,
            annot=True,
            fmt=".2f",
            cmap="YlOrRd",
            cbar_kws={"label": "Throughput (Mbps)"},
        )
        plt.title("Performance Heatmap: Throughput by Protocol and Network Condition")
        plt.ylabel("Network Condition")
        plt.xlabel("Protocol")

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"📈 Saved performance heatmap to {filename}")

    def generate_summary_report(self, filename: str):
        """Generate comprehensive text summary report."""
        with open(filename, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("📊 PACKETFS COMPREHENSIVE TEST REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Tests: {len(self.results)}\n\n")

            # Overall statistics
            f.write("🔍 OVERALL STATISTICS\n")
            f.write("-" * 40 + "\n")

            for protocol in self.df["protocol"].unique():
                protocol_data = self.df[self.df["protocol"] == protocol]
                f.write(f"\n{protocol.upper()} Protocol:\n")
                f.write(
                    f"  Average Throughput: {protocol_data['throughput_mbps'].mean():.2f} Mbps\n"
                )
                f.write(
                    f"  Average Latency: {protocol_data['latency_avg_ms'].mean():.2f} ms\n"
                )
                f.write(
                    f"  Average Packet Loss: {protocol_data['packet_loss_percent'].mean():.2f}%\n"
                )
                f.write(f"  Tests Run: {len(protocol_data)}\n")

            # Performance by network condition
            f.write("\n\n🌐 PERFORMANCE BY NETWORK CONDITION\n")
            f.write("-" * 50 + "\n")

            for condition in self.df["network_condition"].unique():
                condition_data = self.df[self.df["network_condition"] == condition]
                f.write(f"\n{condition.upper()} Network:\n")

                condition_summary = condition_data.groupby("protocol").agg(
                    {
                        "throughput_mbps": "mean",
                        "latency_avg_ms": "mean",
                        "packet_loss_percent": "mean",
                    }
                )

                for protocol in condition_summary.index:
                    stats = condition_summary.loc[protocol]
                    f.write(
                        f"  {protocol}: {stats['throughput_mbps']:.2f} Mbps, "
                        f"{stats['latency_avg_ms']:.2f}ms latency, "
                        f"{stats['packet_loss_percent']:.2f}% loss\n"
                    )

            # PacketFS-specific analysis
            packetfs_data = self.df[self.df["protocol"] == "packetfs"]
            if not packetfs_data.empty:
                f.write("\n\n🚀 PACKETFS-SPECIFIC ANALYSIS\n")
                f.write("-" * 40 + "\n")
                f.write(f"Total Sync Frames: {packetfs_data['sync_frames'].sum()}\n")
                f.write(
                    f"Average Sync Rate: {packetfs_data['sync_frames'].mean():.1f} per test\n"
                )
                f.write(f"Window Size Performance:\n")

                window_performance = packetfs_data.groupby("window_size")[
                    "throughput_mbps"
                ].mean()
                for window_size, throughput in window_performance.items():
                    f.write(f"  {window_size} byte window: {throughput:.2f} Mbps\n")

            # Recommendations
            f.write("\n\n💡 PERFORMANCE RECOMMENDATIONS\n")
            f.write("-" * 40 + "\n")

            # Find best performing configurations
            best_packetfs = self.df[self.df["protocol"] == "packetfs"].nlargest(
                1, "throughput_mbps"
            )
            if not best_packetfs.empty:
                best = best_packetfs.iloc[0]
                f.write(f"Best PacketFS Configuration:\n")
                f.write(f"  Payload Size: {int(best['payload_size'])} bytes\n")
                f.write(f"  Window Size: {int(best['window_size'])} bytes\n")
                f.write(f"  Network Condition: {best['network_condition']}\n")
                f.write(f"  Throughput: {best['throughput_mbps']:.2f} Mbps\n")

            # Protocol comparison
            protocol_avg = self.df.groupby("protocol")["throughput_mbps"].mean()
            if "packetfs" in protocol_avg.index:
                packetfs_perf = protocol_avg["packetfs"]
                f.write(f"\nProtocol Comparison (Average Throughput):\n")
                for protocol, throughput in protocol_avg.items():
                    if protocol != "packetfs":
                        ratio = (
                            packetfs_perf / throughput
                            if throughput > 0
                            else float("inf")
                        )
                        f.write(f"  PacketFS vs {protocol.upper()}: {ratio:.2f}x\n")

        print(f"📄 Saved comprehensive report to {filename}")


def run_unit_tests():
    """Run unit tests to ensure system is working."""
    print("🧪 Running unit tests...")

    # Run pytest on our test modules
    test_files = [
        "tests/test_protocol.py",
        "tests/test_integration.py",
        "tests/test_metrics.py",
    ]

    for test_file in test_files:
        if Path(test_file).exists():
            print(f"  Running {test_file}...")
            result = subprocess.run(
                ["python", "-m", "pytest", test_file, "-v", "-x"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(f"    ❌ Tests failed: {result.stdout}")
                print(f"    Error: {result.stderr}")
                return False
            else:
                print(f"    ✅ Tests passed")

    return True


def run_performance_benchmarks():
    """Run performance benchmarks."""
    print("📊 Running performance benchmarks...")

    try:
        suite = BenchmarkSuite()
        config = SyncConfig(window_pow2=6, window_crc16=True)

        # Run encoding benchmarks
        results = suite.run_encoding_benchmark(
            config, frame_count=1000, payload_sizes=[64, 256, 1024], tier_mix=[0, 1, 2]
        )

        # Run stress test
        stress_result = suite.run_stress_test(
            config, duration_seconds=5.0, target_fps=5000
        )

        # Save results
        suite.save_results("performance_benchmark_results.json")

        print(f"✅ Completed {len(results)} performance benchmarks")
        return True

    except Exception as e:
        print(f"❌ Performance benchmarks failed: {e}")
        return False


def run_network_simulation_tests(scenario_name: str = "quick"):
    """Run network simulation tests."""
    print(f"🌐 Running network simulation tests ({scenario_name})...")

    # Check if running as root for network simulation
    if os.geteuid() != 0:
        print("⚠️  Network simulation tests require root privileges, skipping...")
        return []

    try:
        suite = ComprehensiveTestSuite("lo")

        if scenario_name == "quick":
            scenarios = [QUICK_SCENARIO]
        elif scenario_name == "comprehensive":
            scenarios = [COMPREHENSIVE_SCENARIO]
        else:
            # Create custom scenario
            scenarios = [
                TestScenario(
                    name=scenario_name,
                    frame_counts=[100, 500],
                    payload_sizes=[64, 256],
                    window_sizes=[64, 256],
                    network_conditions=[
                        NetworkCondition("perfect", 0, 0, 0, 1000),
                        NetworkCondition("lan", 1, 0.1, 0, 1000),
                        NetworkCondition("wan", 50, 5, 0.1, 100),
                    ],
                    protocols=["packetfs"],  # Focus on PacketFS for custom scenarios
                )
            ]

        results = suite.run_comprehensive_tests(scenarios)

        # Save raw results
        suite.save_results(f"network_simulation_{scenario_name}_results.json")

        print(f"✅ Completed {len(results)} network simulation tests")
        return results

    except Exception as e:
        print(f"❌ Network simulation tests failed: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="PacketFS Comprehensive Testing Suite")
    parser.add_argument("--unit-tests", action="store_true", help="Run unit tests")
    parser.add_argument(
        "--performance", action="store_true", help="Run performance benchmarks"
    )
    parser.add_argument(
        "--network",
        choices=["quick", "comprehensive", "custom"],
        help="Run network simulation tests",
    )
    parser.add_argument("--all", action="store_true", help="Run all test suites")
    parser.add_argument(
        "--generate-reports", action="store_true", help="Generate visual reports"
    )
    parser.add_argument(
        "--output-dir", default="test_results", help="Output directory for results"
    )

    args = parser.parse_args()

    if not any(
        [
            args.unit_tests,
            args.performance,
            args.network,
            args.all,
            args.generate_reports,
        ]
    ):
        parser.print_help()
        return 1

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    print("🚀 PacketFS Comprehensive Testing Suite")
    print(f"📁 Output directory: {output_dir}")
    print("-" * 50)

    start_time = time.time()
    all_results = []

    try:
        # Run unit tests
        if args.unit_tests or args.all:
            if not run_unit_tests():
                print("❌ Unit tests failed, aborting...")
                return 1

        # Run performance benchmarks
        if args.performance or args.all:
            if not run_performance_benchmarks():
                print("⚠️  Performance benchmarks failed, continuing...")

        # Run network simulation tests
        if args.network or args.all:
            scenario = args.network if args.network else "quick"
            results = run_network_simulation_tests(scenario)
            all_results.extend(results)

        # Generate reports and visualizations
        if (args.generate_reports or args.all) and all_results:
            print("📈 Generating reports and visualizations...")

            report_gen = TestReportGenerator(all_results)

            # Generate plots
            report_gen.generate_throughput_comparison_plot(
                str(output_dir / "throughput_comparison.png")
            )
            report_gen.generate_latency_distribution_plot(
                str(output_dir / "latency_distribution.png")
            )
            report_gen.generate_performance_heatmap(
                str(output_dir / "performance_heatmap.png")
            )

            # Generate summary report
            report_gen.generate_summary_report(
                str(output_dir / "comprehensive_test_report.txt")
            )

        total_time = time.time() - start_time
        print("-" * 50)
        print(f"🏁 Testing completed in {total_time:.1f} seconds")
        print(f"📊 Total test results: {len(all_results)}")
        print(f"📁 Results saved to: {output_dir}")

        return 0

    except KeyboardInterrupt:
        print("\n⚠️  Testing interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Testing failed with error: {e}")
        return 1


if __name__ == "__main__":
    # Install required packages if missing
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
    except ImportError:
        print("📦 Installing required visualization packages...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "matplotlib", "seaborn", "pandas"]
        )
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd

    sys.exit(main())
