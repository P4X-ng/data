"""Thread pool based scheduler multiplexing logical pCPUs.

Design goals:
 - Real metrics only (no fabricated ops/sec)
 - Bounded worker thread pool
 - FIFO task queue with optional backpressure
 - Batch dispatch for reduced lock contention
"""

from __future__ import annotations

from dataclasses import dataclass
from queue import Queue, Empty
from threading import Thread, Event
from typing import Callable, Any, List
import time

from .pcpu_config import PCPUConfig
from .pcpu_registry import PCPURegistry


@dataclass
class PCPUWorkItem:
    pcpu_id: int
    fn: Callable[..., Any]
    args: tuple
    kwargs: dict
    enq_ns: int


class PCPUScheduler:
    def __init__(self, cfg: PCPUConfig | None = None, registry: PCPURegistry | None = None):
        self.cfg = cfg or PCPUConfig()
        self.registry = registry or PCPURegistry(self.cfg)
        self._q: Queue[PCPUWorkItem] = Queue()
        self._stop = Event()
        self._workers: List[Thread] = []
        self._completed_tasks = 0
        self._total_queue_wait_ns = 0
        self._start_time_ns = time.time_ns()
        self._spawn_workers()

    def _spawn_workers(self):
        for i in range(self.cfg.MAX_WORKER_THREADS):
            t = Thread(target=self._worker_loop, name=f"pcpu-worker-{i}", daemon=True)
            t.start()
            self._workers.append(t)

    def submit(self, pcpu_id: int, fn: Callable[..., Any], *args, **kwargs):
        if self._q.qsize() >= self.cfg.QUEUE_HIGH_WATER:
            # Basic backpressure: reject new work (could evolve to drop/merge)
            raise RuntimeError("scheduler queue high-water mark reached")
        item = PCPUWorkItem(pcpu_id=pcpu_id, fn=fn, args=args, kwargs=kwargs, enq_ns=time.time_ns())
        self._q.put(item)

    def _worker_loop(self):
        batch_size = self.cfg.DISPATCH_BATCH_SIZE
        while not self._stop.is_set():
            batch: List[PCPUWorkItem] = []
            try:
                first = self._q.get(timeout=0.1)
            except Empty:
                continue
            batch.append(first)
            # Drain up to batch_size - 1 more without blocking
            for _ in range(batch_size - 1):
                try:
                    batch.append(self._q.get_nowait())
                except Empty:
                    break
            now_ns = time.time_ns()
            for item in batch:
                wait_ns = now_ns - item.enq_ns
                self._total_queue_wait_ns += wait_ns
                self.registry.mark_task(item.pcpu_id)
                try:
                    item.fn(*item.args, **item.kwargs)
                except Exception:
                    # For now: swallow; could add error channel
                    pass
                finally:
                    self._completed_tasks += 1
            for _ in batch:
                self._q.task_done()

    def stop(self, wait: bool = True):
        self._stop.set()
        if wait:
            for t in self._workers:
                t.join(timeout=0.5)

    def stats(self) -> dict:
        elapsed_ns = max(1, time.time_ns() - self._start_time_ns)
        throughput = self._completed_tasks / (elapsed_ns / 1e9)
        avg_wait_ns = (self._total_queue_wait_ns / self._completed_tasks) if self._completed_tasks else 0
        return {
            **self.registry.stats(),
            "completed_tasks": self._completed_tasks,
            "queue_depth": self._q.qsize(),
            "throughput_tasks_per_sec": throughput,
            "avg_queue_wait_us": avg_wait_ns / 1000,
            "worker_threads": self.cfg.MAX_WORKER_THREADS,
        }
