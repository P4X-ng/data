#!/usr/bin/env python3
# pCPU throughput bench using PacketFS PCPUScheduler + native ALU
# Real timings only; measures tasks/sec and queue wait

from __future__ import annotations
import argparse
import time
from typing import Callable

from packetfs.pcpu.pcpu_config import PCPUConfig
from packetfs.pcpu.pcpu_scheduler import PCPUScheduler
try:
    from packetfs.exec.native import PfsExecNative  # production native ALU
except Exception:
    PfsExecNative = None  # fallback to pure-Python workload


def make_work(native: PfsExecNative | None, reps: int) -> Callable[[int, int], None]:
    # Each task performs a small native add_loop when available; else pure-Python add
    if native is not None:
        def _fn(a: int, b: int) -> None:
            acc = 0
            for _ in range(reps):
                acc = native.add_loop(acc, 1, 256)
            if acc == 0xFFFFFFFF:
                raise RuntimeError("impossible")
        return _fn
    else:
        def _fn(a: int, b: int) -> None:
            acc = 0
            for _ in range(reps * 256):
                acc = (acc + 1) & 0xFFFFFFFF
            if acc == 0xFFFFFFFF:
                raise RuntimeError("impossible")
        return _fn


def main() -> int:
    ap = argparse.ArgumentParser(description="PacketFS pCPU throughput bench")
    ap.add_argument("--duration", type=float, default=5.0, help="Seconds to run")
    ap.add_argument("--threads", type=int, default=4, help="Worker threads (metal CPU threads for PCPUScheduler)")
    ap.add_argument("--worker-threads", type=int, default=None, help="Alias for --threads")
    ap.add_argument("--logical-pcpus", type=int, default=1_300_000, help="Logical pCPU count (addressing range)")
    ap.add_argument("--batch", type=int, default=4096, help="Tasks per submit batch")
    ap.add_argument("--reps", type=int, default=8, help="Native add_loop reps per task")
    args = ap.parse_args()

    worker_threads = args.worker_threads if args.worker_threads is not None else args.threads
    cfg = PCPUConfig(
        LOGICAL_PCPU_COUNT=max(1, args.logical_pcpus),
        MAX_WORKER_THREADS=max(1, worker_threads),
        QUEUE_HIGH_WATER=1_000_000,
        DISPATCH_BATCH_SIZE=256,
        METRIC_SAMPLE_SEC=1.0,
    )
    native = None
    try:
        if PfsExecNative is not None:
            native = PfsExecNative()
    except Exception:
        native = None
    sched = PCPUScheduler(cfg)
    work = make_work(native, args.reps)

    t0 = time.perf_counter()
    submitted = 0
    pcpu_cursor = 0
    try:
        while True:
            now = time.perf_counter()
            if now - t0 >= args.duration:
                break
            # Submit a batch
            for _ in range(args.batch):
                sched.submit(pcpu_cursor % cfg.LOGICAL_PCPU_COUNT, work, 1, 1)
                pcpu_cursor += 1
            submitted += args.batch
            # Short yield to avoid a single producer hogging CPU
            if (submitted // args.batch) % 8 == 0:
                time.sleep(0.001)
    finally:
        sched.stop(wait=True)

    stats = sched.stats()
    elapsed = time.perf_counter() - t0
    print("pCPU bench summary:")
    print(f"  duration_s:               {elapsed:.3f}")
    print(f"  submitted_tasks:          {submitted}")
    print(f"  completed_tasks:          {stats['completed_tasks']}")
    print(f"  throughput_tasks_per_sec: {stats['throughput_tasks_per_sec']:.0f}")
    print(f"  avg_queue_wait_us:        {stats['avg_queue_wait_us']:.1f}")
    print(f"  worker_threads:           {stats['worker_threads']}")
    print(f"  activated_pcpus:          {stats.get('activated_pcpus', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

