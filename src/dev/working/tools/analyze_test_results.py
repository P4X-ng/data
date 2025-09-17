#!/usr/bin/env python3
"""
PacketFS Test Results Analysis and Visualization
Analyzes performance test results and generates comprehensive reports with visualizations.
"""
import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# Set style for better plots
plt.style.use("seaborn-v0_8")
sns.set_palette("husl")


class PacketFSResultsAnalyzer:
    """Analyze and visualize PacketFS test results."""

    def __init__(self, results_files: List[str]):
        self.results_files = results_files
        self.all_results = []
        self.df = None
        self._load_results()

    def _load_results(self):
        """Load results from all specified files."""
        for file_path in self.results_files:
            if Path(file_path).exists():
                with open(file_path, "r") as f:
                    data = json.load(f)
                    self.all_results.extend(data)
                print(f"📄 Loaded {len(data)} results from {file_path}")
            else:
                print(f"⚠️  File not found: {file_path}")

        if self.all_results:
            self.df = pd.DataFrame(self.all_results)
            print(f"📊 Total results loaded: {len(self.all_results)}")
        else:
            print("❌ No results loaded!")
            sys.exit(1)

    def generate_performance_plots(self, output_dir: str = "analysis_plots"):
        """Generate comprehensive performance visualization plots."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        print(f"📈 Generating performance plots in {output_dir}/...")

        # Plot 1: Throughput vs Payload Size
        self._plot_throughput_vs_payload(output_path / "throughput_vs_payload.png")

        # Plot 2: Latency vs Payload Size
        self._plot_latency_vs_payload(output_path / "latency_vs_payload.png")

        # Plot 3: Frames per Second vs Payload Size
        self._plot_fps_vs_payload(output_path / "fps_vs_payload.png")

        # Plot 4: Window Size Impact
        self._plot_window_size_impact(output_path / "window_size_impact.png")

        # Plot 5: Bit Efficiency Analysis
        self._plot_bit_efficiency(output_path / "bit_efficiency.png")

        # Plot 6: Performance Heatmap
        self._plot_performance_heatmap(output_path / "performance_heatmap.png")

        # Plot 7: Latency Distribution
        self._plot_latency_distribution(output_path / "latency_distribution.png")

        # Plot 8: Scaling Analysis
        self._plot_scaling_analysis(output_path / "scaling_analysis.png")

        print(
            f"✅ Generated {len(list(output_path.glob('*.png')))} visualization plots"
        )

    def _plot_throughput_vs_payload(self, filename: str):
        """Plot throughput vs payload size."""
        plt.figure(figsize=(12, 8))

        # Main throughput plot
        plt.subplot(2, 2, 1)
        if "encode_mbps" in self.df.columns:
            throughput_col = "encode_mbps"
        else:
            throughput_col = "mbits_per_second"

        payload_groups = self.df.groupby("payload_size")[throughput_col].agg(
            ["mean", "std", "max"]
        )

        plt.errorbar(
            payload_groups.index,
            payload_groups["mean"],
            yerr=payload_groups["std"],
            marker="o",
            linewidth=2,
            markersize=8,
            capsize=5,
        )
        plt.scatter(
            payload_groups.index,
            payload_groups["max"],
            marker="^",
            s=100,
            alpha=0.7,
            label="Peak Performance",
        )

        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Throughput (Mbps)")
        plt.title("PacketFS Throughput vs Payload Size")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xscale("log", base=2)

        # Theoretical limit comparison
        plt.subplot(2, 2, 2)
        if "frames_per_second" in self.df.columns:
            fps_col = "frames_per_second"
        elif "encode_fps" in self.df.columns:
            fps_col = "encode_fps"

        theoretical_mbps = self.df["payload_size"] * self.df[fps_col] * 8 / 1e6
        actual_mbps = self.df[throughput_col]

        plt.scatter(theoretical_mbps, actual_mbps, alpha=0.6)
        max_val = max(theoretical_mbps.max(), actual_mbps.max())
        plt.plot(
            [0, max_val], [0, max_val], "r--", alpha=0.5, label="Perfect Efficiency"
        )
        plt.xlabel("Theoretical Throughput (Mbps)")
        plt.ylabel("Actual Throughput (Mbps)")
        plt.title("Throughput Efficiency")
        plt.grid(True, alpha=0.3)
        plt.legend()

        # Throughput by window size
        plt.subplot(2, 2, 3)
        if "window_size" in self.df.columns:
            window_throughput = self.df.groupby("window_size")[throughput_col].mean()
            plt.bar(range(len(window_throughput)), window_throughput.values)
            plt.xlabel("Window Size (bytes)")
            plt.ylabel("Avg Throughput (Mbps)")
            plt.title("Throughput by Window Size")
            plt.xticks(range(len(window_throughput)), window_throughput.index)
            plt.xticks(rotation=45)

        # Payload size distribution
        plt.subplot(2, 2, 4)
        payload_counts = self.df["payload_size"].value_counts().sort_index()
        plt.bar(payload_counts.index, payload_counts.values)
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Number of Tests")
        plt.title("Test Distribution by Payload Size")
        plt.xscale("log", base=2)

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  📊 Saved throughput analysis to {filename}")

    def _plot_latency_vs_payload(self, filename: str):
        """Plot latency vs payload size."""
        plt.figure(figsize=(14, 10))

        # Determine latency columns
        if "encode_latency_avg_us" in self.df.columns:
            latency_avg_col = "encode_latency_avg_us"
            latency_p95_col = (
                "encode_latency_p95_us"
                if "encode_latency_p95_us" in self.df.columns
                else None
            )
        else:
            latency_avg_col = "avg_latency_us"
            latency_p95_col = "latency_p95_ms"  # Convert to microseconds if needed

        # Main latency plot
        plt.subplot(2, 3, 1)
        payload_groups = self.df.groupby("payload_size")[latency_avg_col].agg(
            ["mean", "std", "min", "max"]
        )

        plt.errorbar(
            payload_groups.index,
            payload_groups["mean"],
            yerr=payload_groups["std"],
            marker="o",
            linewidth=2,
            markersize=8,
            capsize=5,
            label="Average ± Std",
        )
        plt.fill_between(
            payload_groups.index,
            payload_groups["min"],
            payload_groups["max"],
            alpha=0.2,
            label="Min-Max Range",
        )

        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Latency (μs)")
        plt.title("Average Encoding Latency vs Payload Size")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xscale("log", base=2)
        plt.yscale("log")

        # Latency per byte
        plt.subplot(2, 3, 2)
        latency_per_byte = self.df[latency_avg_col] / self.df["payload_size"]
        plt.scatter(self.df["payload_size"], latency_per_byte, alpha=0.6)
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Latency per Byte (μs/byte)")
        plt.title("Latency Efficiency vs Payload Size")
        plt.grid(True, alpha=0.3)
        plt.xscale("log", base=2)
        plt.yscale("log")

        # Latency distribution by payload size
        plt.subplot(2, 3, 3)
        payload_sizes = sorted(self.df["payload_size"].unique())
        latency_data = [
            self.df[self.df["payload_size"] == ps][latency_avg_col].values
            for ps in payload_sizes
        ]

        plt.boxplot(latency_data, labels=payload_sizes)
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Latency (μs)")
        plt.title("Latency Distribution by Payload Size")
        plt.xticks(rotation=45)
        plt.yscale("log")

        # Latency vs throughput trade-off
        plt.subplot(2, 3, 4)
        throughput_col = (
            "encode_mbps" if "encode_mbps" in self.df.columns else "mbits_per_second"
        )
        plt.scatter(
            self.df[latency_avg_col],
            self.df[throughput_col],
            c=self.df["payload_size"],
            cmap="viridis",
            alpha=0.7,
        )
        plt.colorbar(label="Payload Size (bytes)")
        plt.xlabel("Latency (μs)")
        plt.ylabel("Throughput (Mbps)")
        plt.title("Latency vs Throughput Trade-off")
        plt.grid(True, alpha=0.3)
        plt.xscale("log")

        # Latency scaling model
        plt.subplot(2, 3, 5)
        # Fit logarithmic model: latency = a * log(payload_size) + b
        log_payload = np.log(self.df["payload_size"])
        coeffs = np.polyfit(log_payload, self.df[latency_avg_col], 1)

        payload_range = np.logspace(
            np.log10(self.df["payload_size"].min()),
            np.log10(self.df["payload_size"].max()),
            100,
        )
        predicted_latency = coeffs[0] * np.log(payload_range) + coeffs[1]

        plt.scatter(
            self.df["payload_size"],
            self.df[latency_avg_col],
            alpha=0.6,
            label="Measured",
        )
        plt.plot(
            payload_range,
            predicted_latency,
            "r--",
            linewidth=2,
            label=f"Model: {coeffs[0]:.1f}*ln(size) + {coeffs[1]:.1f}",
        )
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Latency (μs)")
        plt.title("Latency Scaling Model")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xscale("log", base=2)
        plt.yscale("log")

        # Window size impact on latency
        plt.subplot(2, 3, 6)
        if "window_size" in self.df.columns:
            window_latency = self.df.groupby("window_size")[latency_avg_col].agg(
                ["mean", "std"]
            )
            plt.errorbar(
                window_latency.index,
                window_latency["mean"],
                yerr=window_latency["std"],
                marker="s",
                linewidth=2,
                markersize=8,
                capsize=5,
            )
            plt.xlabel("Window Size (bytes)")
            plt.ylabel("Average Latency (μs)")
            plt.title("Latency vs Window Size")
            plt.grid(True, alpha=0.3)
            plt.xscale("log", base=2)

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  📊 Saved latency analysis to {filename}")

    def _plot_fps_vs_payload(self, filename: str):
        """Plot frames per second vs payload size."""
        plt.figure(figsize=(12, 8))

        fps_col = (
            "encode_fps" if "encode_fps" in self.df.columns else "frames_per_second"
        )

        plt.subplot(2, 2, 1)
        payload_groups = self.df.groupby("payload_size")[fps_col].agg(
            ["mean", "std", "max"]
        )

        plt.errorbar(
            payload_groups.index,
            payload_groups["mean"],
            yerr=payload_groups["std"],
            marker="o",
            linewidth=2,
            markersize=8,
            capsize=5,
            label="Average ± Std",
        )
        plt.scatter(
            payload_groups.index,
            payload_groups["max"],
            marker="^",
            s=100,
            alpha=0.7,
            label="Peak FPS",
        )

        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Frames per Second")
        plt.title("Encoding Performance vs Payload Size")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xscale("log", base=2)
        plt.yscale("log")

        # FPS efficiency (FPS per computational complexity)
        plt.subplot(2, 2, 2)
        # Assume complexity scales with payload size
        fps_efficiency = self.df[fps_col] / self.df["payload_size"]
        plt.scatter(self.df["payload_size"], fps_efficiency, alpha=0.6)
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("FPS per Byte")
        plt.title("FPS Efficiency vs Payload Size")
        plt.grid(True, alpha=0.3)
        plt.xscale("log", base=2)
        plt.yscale("log")

        # Frame count vs performance
        plt.subplot(2, 2, 3)
        if "frame_count" in self.df.columns:
            frame_groups = self.df.groupby("frame_count")[fps_col].mean()
            plt.bar(frame_groups.index, frame_groups.values)
            plt.xlabel("Frame Count")
            plt.ylabel("Average FPS")
            plt.title("Performance vs Test Frame Count")
            plt.grid(True, alpha=0.3)

        # Performance by test scenario
        plt.subplot(2, 2, 4)
        if "test_name" in self.df.columns:
            # Group by payload size for cleaner visualization
            test_perf = self.df.groupby("payload_size")[fps_col].mean().sort_index()
            colors = plt.cm.viridis(np.linspace(0, 1, len(test_perf)))

            bars = plt.bar(range(len(test_perf)), test_perf.values, color=colors)
            plt.xlabel("Test Scenarios (by payload size)")
            plt.ylabel("Average FPS")
            plt.title("Performance Summary by Payload Size")
            plt.xticks(
                range(len(test_perf)),
                [f"{size}B" for size in test_perf.index],
                rotation=45,
            )

            # Add value labels on bars
            for bar, value in zip(bars, test_perf.values):
                plt.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + value * 0.01,
                    f"{value:.0f}",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                )

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  📊 Saved FPS analysis to {filename}")

    def _plot_window_size_impact(self, filename: str):
        """Plot window size impact on performance."""
        if "window_size" not in self.df.columns:
            print("  ⚠️  No window_size data available, skipping window analysis")
            return

        plt.figure(figsize=(15, 10))

        # Window size vs throughput
        plt.subplot(2, 3, 1)
        throughput_col = (
            "encode_mbps" if "encode_mbps" in self.df.columns else "mbits_per_second"
        )
        window_throughput = self.df.groupby("window_size")[throughput_col].agg(
            ["mean", "std"]
        )

        plt.errorbar(
            window_throughput.index,
            window_throughput["mean"],
            yerr=window_throughput["std"],
            marker="o",
            linewidth=2,
            markersize=8,
            capsize=5,
        )
        plt.xlabel("Window Size (bytes)")
        plt.ylabel("Throughput (Mbps)")
        plt.title("Throughput vs Window Size")
        plt.grid(True, alpha=0.3)
        plt.xscale("log", base=2)

        # Window size vs latency
        plt.subplot(2, 3, 2)
        latency_col = (
            "encode_latency_avg_us"
            if "encode_latency_avg_us" in self.df.columns
            else "avg_latency_us"
        )
        window_latency = self.df.groupby("window_size")[latency_col].agg(
            ["mean", "std"]
        )

        plt.errorbar(
            window_latency.index,
            window_latency["mean"],
            yerr=window_latency["std"],
            marker="s",
            linewidth=2,
            markersize=8,
            capsize=5,
        )
        plt.xlabel("Window Size (bytes)")
        plt.ylabel("Latency (μs)")
        plt.title("Latency vs Window Size")
        plt.grid(True, alpha=0.3)
        plt.xscale("log", base=2)

        # Window size vs sync frames
        plt.subplot(2, 3, 3)
        if "sync_frames" in self.df.columns:
            window_sync = self.df.groupby("window_size")["sync_frames"].mean()
            plt.bar(range(len(window_sync)), window_sync.values)
            plt.xlabel("Window Size (bytes)")
            plt.ylabel("Average Sync Frames")
            plt.title("Sync Frames vs Window Size")
            plt.xticks(range(len(window_sync)), window_sync.index)
            plt.xticks(rotation=45)

        # Heatmap: Window size vs Payload size performance
        plt.subplot(2, 3, 4)
        pivot_data = self.df.pivot_table(
            values=throughput_col,
            index="payload_size",
            columns="window_size",
            aggfunc="mean",
        )
        sns.heatmap(pivot_data, annot=True, fmt=".1f", cmap="YlOrRd")
        plt.title("Performance Heatmap\n(Throughput Mbps)")
        plt.ylabel("Payload Size (bytes)")
        plt.xlabel("Window Size (bytes)")

        # Window efficiency (throughput per window overhead)
        plt.subplot(2, 3, 5)
        if "bit_efficiency" in self.df.columns:
            window_efficiency = self.df.groupby("window_size")["bit_efficiency"].mean()
            plt.bar(range(len(window_efficiency)), window_efficiency.values)
            plt.xlabel("Window Size (bytes)")
            plt.ylabel("Bit Efficiency")
            plt.title("Bit Efficiency vs Window Size")
            plt.xticks(range(len(window_efficiency)), window_efficiency.index)
            plt.xticks(rotation=45)

        # Window size distribution
        plt.subplot(2, 3, 6)
        window_counts = self.df["window_size"].value_counts().sort_index()
        plt.pie(window_counts.values, labels=window_counts.index, autopct="%1.1f%%")
        plt.title("Test Distribution by Window Size")

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  📊 Saved window size analysis to {filename}")

    def _plot_bit_efficiency(self, filename: str):
        """Plot bit packing efficiency analysis."""
        if "bit_efficiency" not in self.df.columns:
            print("  ⚠️  No bit_efficiency data available, skipping efficiency analysis")
            return

        plt.figure(figsize=(12, 8))

        plt.subplot(2, 2, 1)
        plt.hist(self.df["bit_efficiency"], bins=20, alpha=0.7, edgecolor="black")
        plt.xlabel("Bit Efficiency")
        plt.ylabel("Frequency")
        plt.title("Bit Efficiency Distribution")
        plt.grid(True, alpha=0.3)

        plt.subplot(2, 2, 2)
        efficiency_by_payload = self.df.groupby("payload_size")["bit_efficiency"].mean()
        plt.plot(efficiency_by_payload.index, efficiency_by_payload.values, marker="o")
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Bit Efficiency")
        plt.title("Bit Efficiency vs Payload Size")
        plt.grid(True, alpha=0.3)
        plt.xscale("log", base=2)

        plt.subplot(2, 2, 3)
        if "total_bits" in self.df.columns and "frame_count" in self.df.columns:
            theoretical_bits = self.df["payload_size"] * self.df["frame_count"] * 8
            actual_bits = self.df["total_bits"]
            overhead_bits = actual_bits - theoretical_bits

            plt.scatter(theoretical_bits, overhead_bits, alpha=0.6)
            plt.xlabel("Theoretical Bits")
            plt.ylabel("Overhead Bits")
            plt.title("Protocol Overhead vs Data Size")
            plt.grid(True, alpha=0.3)

        plt.subplot(2, 2, 4)
        # Efficiency vs window size if available
        if "window_size" in self.df.columns:
            efficiency_by_window = self.df.groupby("window_size")["bit_efficiency"].agg(
                ["mean", "std"]
            )
            plt.errorbar(
                efficiency_by_window.index,
                efficiency_by_window["mean"],
                yerr=efficiency_by_window["std"],
                marker="o",
            )
            plt.xlabel("Window Size (bytes)")
            plt.ylabel("Bit Efficiency")
            plt.title("Bit Efficiency vs Window Size")
            plt.grid(True, alpha=0.3)
            plt.xscale("log", base=2)

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  📊 Saved bit efficiency analysis to {filename}")

    def _plot_performance_heatmap(self, filename: str):
        """Generate comprehensive performance heatmap."""
        plt.figure(figsize=(14, 10))

        throughput_col = (
            "encode_mbps" if "encode_mbps" in self.df.columns else "mbits_per_second"
        )
        latency_col = (
            "encode_latency_avg_us"
            if "encode_latency_avg_us" in self.df.columns
            else "avg_latency_us"
        )

        # Main performance heatmap
        plt.subplot(2, 2, 1)
        pivot_throughput = self.df.pivot_table(
            values=throughput_col,
            index="payload_size",
            columns=(
                "window_size" if "window_size" in self.df.columns else "frame_count"
            ),
            aggfunc="mean",
        )
        sns.heatmap(
            pivot_throughput,
            annot=True,
            fmt=".1f",
            cmap="YlOrRd",
            cbar_kws={"label": "Throughput (Mbps)"},
        )
        plt.title("Throughput Performance Heatmap")
        plt.ylabel("Payload Size (bytes)")

        # Latency heatmap
        plt.subplot(2, 2, 2)
        pivot_latency = self.df.pivot_table(
            values=latency_col,
            index="payload_size",
            columns=(
                "window_size" if "window_size" in self.df.columns else "frame_count"
            ),
            aggfunc="mean",
        )
        sns.heatmap(
            pivot_latency,
            annot=True,
            fmt=".0f",
            cmap="YlOrRd_r",
            cbar_kws={"label": "Latency (μs)"},
        )
        plt.title("Latency Heatmap")
        plt.ylabel("Payload Size (bytes)")

        # FPS heatmap
        plt.subplot(2, 2, 3)
        fps_col = (
            "encode_fps" if "encode_fps" in self.df.columns else "frames_per_second"
        )
        pivot_fps = self.df.pivot_table(
            values=fps_col,
            index="payload_size",
            columns=(
                "window_size" if "window_size" in self.df.columns else "frame_count"
            ),
            aggfunc="mean",
        )
        sns.heatmap(
            pivot_fps, annot=True, fmt=".0f", cmap="viridis", cbar_kws={"label": "FPS"}
        )
        plt.title("FPS Performance Heatmap")
        plt.ylabel("Payload Size (bytes)")

        # Performance score (combined metric)
        plt.subplot(2, 2, 4)
        # Normalize metrics and create composite score
        norm_throughput = (self.df[throughput_col] - self.df[throughput_col].min()) / (
            self.df[throughput_col].max() - self.df[throughput_col].min()
        )
        norm_latency = 1 - (self.df[latency_col] - self.df[latency_col].min()) / (
            self.df[latency_col].max() - self.df[latency_col].min()
        )

        self.df["performance_score"] = (norm_throughput + norm_latency) / 2

        pivot_score = self.df.pivot_table(
            values="performance_score",
            index="payload_size",
            columns=(
                "window_size" if "window_size" in self.df.columns else "frame_count"
            ),
            aggfunc="mean",
        )
        sns.heatmap(
            pivot_score,
            annot=True,
            fmt=".2f",
            cmap="RdYlGn",
            cbar_kws={"label": "Performance Score"},
        )
        plt.title("Combined Performance Score")
        plt.ylabel("Payload Size (bytes)")

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  📊 Saved performance heatmap to {filename}")

    def _plot_latency_distribution(self, filename: str):
        """Plot detailed latency distribution analysis."""
        plt.figure(figsize=(14, 10))

        latency_col = (
            "encode_latency_avg_us"
            if "encode_latency_avg_us" in self.df.columns
            else "avg_latency_us"
        )

        # Overall latency distribution
        plt.subplot(2, 3, 1)
        plt.hist(self.df[latency_col], bins=30, alpha=0.7, edgecolor="black")
        plt.xlabel("Latency (μs)")
        plt.ylabel("Frequency")
        plt.title("Overall Latency Distribution")
        plt.grid(True, alpha=0.3)

        # Latency by payload size
        plt.subplot(2, 3, 2)
        payload_sizes = sorted(self.df["payload_size"].unique())
        latency_by_payload = [
            self.df[self.df["payload_size"] == ps][latency_col].values
            for ps in payload_sizes
        ]

        plt.boxplot(latency_by_payload, labels=payload_sizes)
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Latency (μs)")
        plt.title("Latency Distribution by Payload Size")
        plt.xticks(rotation=45)
        plt.yscale("log")

        # Latency percentiles
        plt.subplot(2, 3, 3)
        percentiles = [50, 75, 90, 95, 99]
        latency_percentiles = [
            np.percentile(self.df[latency_col], p) for p in percentiles
        ]

        plt.bar(range(len(percentiles)), latency_percentiles)
        plt.xlabel("Percentile")
        plt.ylabel("Latency (μs)")
        plt.title("Latency Percentiles")
        plt.xticks(range(len(percentiles)), [f"P{p}" for p in percentiles])

        # Latency vs throughput scatter
        plt.subplot(2, 3, 4)
        throughput_col = (
            "encode_mbps" if "encode_mbps" in self.df.columns else "mbits_per_second"
        )
        plt.scatter(
            self.df[latency_col],
            self.df[throughput_col],
            c=self.df["payload_size"],
            cmap="viridis",
            alpha=0.7,
        )
        plt.colorbar(label="Payload Size (bytes)")
        plt.xlabel("Latency (μs)")
        plt.ylabel("Throughput (Mbps)")
        plt.title("Latency vs Throughput")
        plt.grid(True, alpha=0.3)
        plt.xscale("log")

        # Latency scaling with payload
        plt.subplot(2, 3, 5)
        payload_groups = self.df.groupby("payload_size")[latency_col].agg(
            ["mean", "std", "min", "max"]
        )

        plt.errorbar(
            payload_groups.index,
            payload_groups["mean"],
            yerr=payload_groups["std"],
            marker="o",
            linewidth=2,
            markersize=6,
            capsize=3,
            label="Mean ± Std",
        )
        plt.fill_between(
            payload_groups.index,
            payload_groups["min"],
            payload_groups["max"],
            alpha=0.2,
            label="Min-Max Range",
        )
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Latency (μs)")
        plt.title("Latency Scaling")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xscale("log", base=2)
        plt.yscale("log")

        # Latency efficiency (latency per byte)
        plt.subplot(2, 3, 6)
        latency_per_byte = self.df[latency_col] / self.df["payload_size"]
        plt.scatter(self.df["payload_size"], latency_per_byte, alpha=0.6)
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Latency per Byte (μs/byte)")
        plt.title("Latency Efficiency")
        plt.grid(True, alpha=0.3)
        plt.xscale("log", base=2)
        plt.yscale("log")

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  📊 Saved latency distribution analysis to {filename}")

    def _plot_scaling_analysis(self, filename: str):
        """Plot scaling and performance modeling analysis."""
        plt.figure(figsize=(16, 12))

        throughput_col = (
            "encode_mbps" if "encode_mbps" in self.df.columns else "mbits_per_second"
        )
        fps_col = (
            "encode_fps" if "encode_fps" in self.df.columns else "frames_per_second"
        )
        latency_col = (
            "encode_latency_avg_us"
            if "encode_latency_avg_us" in self.df.columns
            else "avg_latency_us"
        )

        # Throughput scaling model
        plt.subplot(3, 3, 1)
        # Fit power law: throughput = a * payload_size^b
        log_payload = np.log(self.df["payload_size"])
        log_throughput = np.log(self.df[throughput_col])
        coeffs = np.polyfit(log_payload, log_throughput, 1)

        payload_range = np.logspace(
            np.log10(self.df["payload_size"].min()),
            np.log10(self.df["payload_size"].max()),
            100,
        )
        predicted_throughput = np.exp(coeffs[1]) * (payload_range ** coeffs[0])

        plt.scatter(
            self.df["payload_size"],
            self.df[throughput_col],
            alpha=0.6,
            label="Measured",
        )
        plt.plot(
            payload_range,
            predicted_throughput,
            "r--",
            linewidth=2,
            label=f"Model: {np.exp(coeffs[1]):.1f} * size^{coeffs[0]:.2f}",
        )
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Throughput (Mbps)")
        plt.title("Throughput Scaling Model")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xscale("log", base=2)
        plt.yscale("log")

        # FPS scaling model
        plt.subplot(3, 3, 2)
        log_fps = np.log(self.df[fps_col])
        fps_coeffs = np.polyfit(log_payload, log_fps, 1)
        predicted_fps = np.exp(fps_coeffs[1]) * (payload_range ** fps_coeffs[0])

        plt.scatter(
            self.df["payload_size"], self.df[fps_col], alpha=0.6, label="Measured"
        )
        plt.plot(
            payload_range,
            predicted_fps,
            "r--",
            linewidth=2,
            label=f"Model: {np.exp(fps_coeffs[1]):.0f} * size^{fps_coeffs[0]:.2f}",
        )
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Frames per Second")
        plt.title("FPS Scaling Model")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xscale("log", base=2)
        plt.yscale("log")

        # Latency scaling model
        plt.subplot(3, 3, 3)
        latency_coeffs = np.polyfit(log_payload, self.df[latency_col], 1)
        predicted_latency = (
            latency_coeffs[0] * np.log(payload_range) + latency_coeffs[1]
        )

        plt.scatter(
            self.df["payload_size"], self.df[latency_col], alpha=0.6, label="Measured"
        )
        plt.plot(
            payload_range,
            predicted_latency,
            "r--",
            linewidth=2,
            label=f"Model: {latency_coeffs[0]:.1f}*ln(size) + {latency_coeffs[1]:.1f}",
        )
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Latency (μs)")
        plt.title("Latency Scaling Model")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xscale("log", base=2)
        plt.yscale("log")

        # Performance efficiency
        plt.subplot(3, 3, 4)
        efficiency = (
            self.df[throughput_col] / self.df[latency_col] * 1000
        )  # Mbps per ms
        plt.scatter(self.df["payload_size"], efficiency, alpha=0.6)
        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Efficiency (Mbps/ms)")
        plt.title("Performance Efficiency vs Size")
        plt.grid(True, alpha=0.3)
        plt.xscale("log", base=2)
        plt.yscale("log")

        # Resource utilization model
        plt.subplot(3, 3, 5)
        if "frame_count" in self.df.columns:
            total_work = self.df["payload_size"] * self.df["frame_count"]
            time_per_work = (
                (self.df["frame_count"] / self.df[fps_col]) / total_work * 1e6
            )  # μs per byte

            plt.scatter(total_work, time_per_work, alpha=0.6)
            plt.xlabel("Total Work (bytes)")
            plt.ylabel("Time per Byte (μs/byte)")
            plt.title("Resource Utilization Scaling")
            plt.grid(True, alpha=0.3)
            plt.xscale("log")
            plt.yscale("log")

        # Predictive model validation
        plt.subplot(3, 3, 6)
        predicted_throughput_validation = np.exp(coeffs[1]) * (
            self.df["payload_size"] ** coeffs[0]
        )
        residuals = self.df[throughput_col] - predicted_throughput_validation

        plt.scatter(predicted_throughput_validation, residuals, alpha=0.6)
        plt.axhline(y=0, color="r", linestyle="--")
        plt.xlabel("Predicted Throughput (Mbps)")
        plt.ylabel("Residuals (Mbps)")
        plt.title("Model Validation - Throughput")
        plt.grid(True, alpha=0.3)

        # Performance summary by configuration
        plt.subplot(3, 3, 7)
        if "window_size" in self.df.columns:
            config_perf = (
                self.df.groupby(["payload_size", "window_size"])[throughput_col]
                .mean()
                .unstack()
            )
            im = plt.imshow(config_perf.values, cmap="YlOrRd", aspect="auto")
            plt.colorbar(im, label="Throughput (Mbps)")
            plt.yticks(range(len(config_perf.index)), config_perf.index)
            plt.xticks(range(len(config_perf.columns)), config_perf.columns)
            plt.ylabel("Payload Size (bytes)")
            plt.xlabel("Window Size (bytes)")
            plt.title("Configuration Performance Matrix")

        # Optimization recommendations
        plt.subplot(3, 3, 8)
        # Find optimal configurations for different payload sizes
        if "window_size" in self.df.columns:
            optimal_configs = []
            payload_sizes = sorted(self.df["payload_size"].unique())

            for ps in payload_sizes:
                ps_data = self.df[self.df["payload_size"] == ps]
                best_config = ps_data.loc[ps_data[throughput_col].idxmax()]
                optimal_configs.append(best_config["window_size"])

            plt.plot(payload_sizes, optimal_configs, "o-", linewidth=2, markersize=8)
            plt.xlabel("Payload Size (bytes)")
            plt.ylabel("Optimal Window Size (bytes)")
            plt.title("Optimal Configuration by Payload Size")
            plt.grid(True, alpha=0.3)
            plt.xscale("log", base=2)
            plt.yscale("log", base=2)

        # Performance trends summary
        plt.subplot(3, 3, 9)
        payload_summary = self.df.groupby("payload_size").agg(
            {throughput_col: "mean", fps_col: "mean", latency_col: "mean"}
        )

        # Normalize for comparison
        norm_throughput = (
            payload_summary[throughput_col] / payload_summary[throughput_col].max()
        )
        norm_fps = payload_summary[fps_col] / payload_summary[fps_col].max()
        norm_latency = 1 - (
            payload_summary[latency_col] / payload_summary[latency_col].max()
        )

        x = range(len(payload_summary))
        width = 0.25

        plt.bar(
            [i - width for i in x],
            norm_throughput,
            width,
            label="Throughput",
            alpha=0.8,
        )
        plt.bar([i for i in x], norm_fps, width, label="FPS", alpha=0.8)
        plt.bar(
            [i + width for i in x],
            norm_latency,
            width,
            label="Latency (inv)",
            alpha=0.8,
        )

        plt.xlabel("Payload Size (bytes)")
        plt.ylabel("Normalized Performance")
        plt.title("Performance Trends Summary")
        plt.xticks(x, [f"{ps}B" for ps in payload_summary.index], rotation=45)
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  📊 Saved scaling analysis to {filename}")

    def generate_comprehensive_report(
        self, output_file: str = "comprehensive_analysis_report.txt"
    ):
        """Generate comprehensive text analysis report."""
        with open(output_file, "w") as f:
            f.write("=" * 100 + "\n")
            f.write("📊 PACKETFS COMPREHENSIVE PERFORMANCE ANALYSIS REPORT\n")
            f.write("=" * 100 + "\n")
            f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total test results analyzed: {len(self.df)}\n")
            f.write(f"Data sources: {', '.join(self.results_files)}\n\n")

            # Executive Summary
            throughput_col = (
                "encode_mbps"
                if "encode_mbps" in self.df.columns
                else "mbits_per_second"
            )
            fps_col = (
                "encode_fps" if "encode_fps" in self.df.columns else "frames_per_second"
            )
            latency_col = (
                "encode_latency_avg_us"
                if "encode_latency_avg_us" in self.df.columns
                else "avg_latency_us"
            )

            f.write("🎯 EXECUTIVE SUMMARY\n")
            f.write("-" * 50 + "\n")
            f.write(f"Peak Throughput: {self.df[throughput_col].max():.2f} Mbps\n")
            f.write(f"Peak FPS: {self.df[fps_col].max():,.0f} frames/second\n")
            f.write(f"Lowest Latency: {self.df[latency_col].min():.2f} μs\n")
            f.write(f"Average Throughput: {self.df[throughput_col].mean():.2f} Mbps\n")
            f.write(f"Average FPS: {self.df[fps_col].mean():,.0f} frames/second\n")
            f.write(f"Average Latency: {self.df[latency_col].mean():.2f} μs\n\n")

            # Payload size analysis
            f.write("📦 PAYLOAD SIZE PERFORMANCE ANALYSIS\n")
            f.write("-" * 60 + "\n")
            payload_analysis = self.df.groupby("payload_size").agg(
                {
                    throughput_col: ["mean", "std", "max"],
                    fps_col: ["mean", "max"],
                    latency_col: ["mean", "min"],
                }
            )

            f.write(
                f"{'Size (B)':<8} {'Avg Mbps':<10} {'Max Mbps':<10} {'Avg FPS':<12} {'Max FPS':<12} {'Avg Lat (μs)':<12}\n"
            )
            f.write("-" * 70 + "\n")

            for size in sorted(self.df["payload_size"].unique()):
                size_data = self.df[self.df["payload_size"] == size]
                f.write(
                    f"{size:<8} {size_data[throughput_col].mean():<10.2f} "
                    f"{size_data[throughput_col].max():<10.2f} "
                    f"{size_data[fps_col].mean():<12.0f} "
                    f"{size_data[fps_col].max():<12.0f} "
                    f"{size_data[latency_col].mean():<12.2f}\n"
                )

            f.write("\n")

            # Window size impact (if available)
            if "window_size" in self.df.columns:
                f.write("🪟 WINDOW SIZE IMPACT ANALYSIS\n")
                f.write("-" * 50 + "\n")
                window_analysis = self.df.groupby("window_size").agg(
                    {
                        throughput_col: "mean",
                        latency_col: "mean",
                        "sync_frames": (
                            "mean"
                            if "sync_frames" in self.df.columns
                            else throughput_col
                        ),
                    }
                )

                f.write(f"{'Window (B)':<10} {'Avg Mbps':<10} {'Avg Lat (μs)':<12}\n")
                f.write("-" * 35 + "\n")

                for window in sorted(self.df["window_size"].unique()):
                    window_data = self.df[self.df["window_size"] == window]
                    f.write(
                        f"{window:<10} {window_data[throughput_col].mean():<10.2f} "
                        f"{window_data[latency_col].mean():<12.2f}\n"
                    )

                f.write("\n")

            # Performance scaling analysis
            f.write("📈 PERFORMANCE SCALING ANALYSIS\n")
            f.write("-" * 50 + "\n")

            # Fit scaling models
            log_payload = np.log(self.df["payload_size"])
            log_throughput = np.log(self.df[throughput_col])
            throughput_coeffs = np.polyfit(log_payload, log_throughput, 1)

            log_fps = np.log(self.df[fps_col])
            fps_coeffs = np.polyfit(log_payload, log_fps, 1)

            latency_coeffs = np.polyfit(log_payload, self.df[latency_col], 1)

            f.write("Scaling Laws (power law: y = a * x^b, linear: y = a*ln(x) + b):\n")
            f.write(
                f"Throughput: {np.exp(throughput_coeffs[1]):.2f} * payload_size^{throughput_coeffs[0]:.3f}\n"
            )
            f.write(
                f"FPS: {np.exp(fps_coeffs[1]):.0f} * payload_size^{fps_coeffs[0]:.3f}\n"
            )
            f.write(
                f"Latency: {latency_coeffs[0]:.2f} * ln(payload_size) + {latency_coeffs[1]:.2f}\n\n"
            )

            # Efficiency analysis
            f.write("⚡ EFFICIENCY ANALYSIS\n")
            f.write("-" * 30 + "\n")

            # Calculate efficiency metrics
            throughput_per_latency = self.df[throughput_col] / (
                self.df[latency_col] / 1000
            )  # Mbps per ms
            fps_per_payload = self.df[fps_col] / self.df["payload_size"]

            f.write(
                f"Best Throughput/Latency Ratio: {throughput_per_latency.max():.2f} Mbps/ms\n"
            )
            f.write(f"Best FPS/Payload Ratio: {fps_per_payload.max():.2f} fps/byte\n")

            if "bit_efficiency" in self.df.columns:
                f.write(
                    f"Average Bit Efficiency: {self.df['bit_efficiency'].mean():.6f}\n"
                )
                f.write(f"Best Bit Efficiency: {self.df['bit_efficiency'].max():.6f}\n")

            f.write("\n")

            # Recommendations
            f.write("💡 OPTIMIZATION RECOMMENDATIONS\n")
            f.write("-" * 50 + "\n")

            # Find best configurations
            best_throughput = self.df.loc[self.df[throughput_col].idxmax()]
            best_fps = self.df.loc[self.df[fps_col].idxmax()]
            best_latency = self.df.loc[self.df[latency_col].idxmin()]

            f.write("Optimal Configurations:\n")
            f.write(
                f"For Maximum Throughput ({best_throughput[throughput_col]:.2f} Mbps):\n"
            )
            f.write(f"  - Payload Size: {best_throughput['payload_size']} bytes\n")
            if "window_size" in self.df.columns:
                f.write(f"  - Window Size: {best_throughput['window_size']} bytes\n")

            f.write(f"\nFor Maximum FPS ({best_fps[fps_col]:,.0f} fps):\n")
            f.write(f"  - Payload Size: {best_fps['payload_size']} bytes\n")
            if "window_size" in self.df.columns:
                f.write(f"  - Window Size: {best_fps['window_size']} bytes\n")

            f.write(f"\nFor Minimum Latency ({best_latency[latency_col]:.2f} μs):\n")
            f.write(f"  - Payload Size: {best_latency['payload_size']} bytes\n")
            if "window_size" in self.df.columns:
                f.write(f"  - Window Size: {best_latency['window_size']} bytes\n")

            # Performance insights
            f.write("\n📋 KEY PERFORMANCE INSIGHTS\n")
            f.write("-" * 40 + "\n")

            # Identify trends
            small_payload_perf = self.df[self.df["payload_size"] <= 128][
                throughput_col
            ].mean()
            large_payload_perf = self.df[self.df["payload_size"] >= 1024][
                throughput_col
            ].mean()

            f.write(
                f"1. Small payloads (≤128B) average: {small_payload_perf:.2f} Mbps\n"
            )
            f.write(
                f"2. Large payloads (≥1024B) average: {large_payload_perf:.2f} Mbps\n"
            )

            if large_payload_perf > small_payload_perf:
                f.write(
                    "3. Throughput increases with payload size (bulk transfer optimized)\n"
                )
            else:
                f.write(
                    "3. Higher throughput with smaller payloads (low-latency optimized)\n"
                )

            # Latency scaling insight
            latency_growth_rate = latency_coeffs[0]
            if latency_growth_rate > 0:
                f.write(
                    f"4. Latency grows logarithmically with payload size (rate: {latency_growth_rate:.2f} μs/ln(byte))\n"
                )
            else:
                f.write("4. Latency decreases or remains constant with payload size\n")

            # Window size insights (if available)
            if "window_size" in self.df.columns:
                window_impact = self.df.groupby("window_size")[throughput_col].mean()
                best_window = window_impact.idxmax()
                f.write(f"5. Optimal window size for throughput: {best_window} bytes\n")

        print(f"📄 Saved comprehensive analysis report to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="PacketFS Test Results Analysis and Visualization"
    )
    parser.add_argument(
        "--results",
        nargs="+",
        default=["simple_packetfs_results.json", "performance_benchmark_results.json"],
        help="JSON result files to analyze",
    )
    parser.add_argument(
        "--output-dir",
        default="analysis_output",
        help="Output directory for plots and reports",
    )

    args = parser.parse_args()

    print("📊 PacketFS Test Results Analysis")
    print("-" * 50)

    # Create analyzer
    analyzer = PacketFSResultsAnalyzer(args.results)

    # Create output directory
    Path(args.output_dir).mkdir(exist_ok=True)

    try:
        # Generate visualizations
        analyzer.generate_performance_plots(args.output_dir)

        # Generate comprehensive report
        analyzer.generate_comprehensive_report(
            f"{args.output_dir}/comprehensive_analysis_report.txt"
        )

        print(f"\n✅ Analysis complete! Results saved to {args.output_dir}/")
        print(f"📊 Generated {len(list(Path(args.output_dir).glob('*.png')))} plots")
        print(f"📄 Generated comprehensive report")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
