#!/usr/bin/env python3
"""
async_core.py — Single-core async worker to supplement research tasks.

- Pins itself to a chosen CPU core (Linux) using sched_setaffinity.
- Runs a lightweight asyncio loop that watches a queue directory for tasks.
- Executes pattern_scan jobs (scan-file / scan-blob) sequentially (one at a time) to keep CPU usage predictable.
- Logs to logs/async_core.log and writes per-task stdout/stderr to logs/async_core_tasks/.

Queue format (JSON files dropped into logs/patterns/queue/):
{ "type": "scan-file", "path": "/path/to/file", "win": 4096, "k": 50, "mods": "64,128,256,512,4096" }
{ "type": "scan-blob", "name": "pfs_vblob_test", "size_mb": 100, "seed": 1337, "win": 4096, "k": 50, "mods": "64,128,256,512,4096", "keep_snapshot": false }

Usage:
  /home/punk/.venv/bin/python dev/working/tools/async_core.py --cpu 0

Stop:
  pkill -f "dev/working/tools/async_core.py"  # or kill the PID printed at startup
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

VENV_PY = "/home/punk/.venv/bin/python"
ROOT = Path(__file__).resolve().parents[3]
QUEUE_DIR = ROOT / "logs" / "patterns" / "queue"
TASK_LOG_DIR = ROOT / "logs" / "async_core_tasks"
MAIN_LOG = ROOT / "logs" / "async_core.log"


def pin_cpu(cpu: int | None) -> None:
    try:
        if cpu is None:
            return
        os.sched_setaffinity(0, {int(cpu)})
    except Exception as e:
        print(f"[warn] sched_setaffinity failed: {e}")


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    MAIN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with MAIN_LOG.open("a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(msg, flush=True)


async def run_cmd(label: str, *args: str) -> int:
    TASK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    base = f"{ts}_{label}"
    outp = (TASK_LOG_DIR / f"{base}.out").open("wb")
    errp = (TASK_LOG_DIR / f"{base}.err").open("wb")
    try:
        p = await asyncio.create_subprocess_exec(*args, stdout=outp, stderr=errp)
        rc = await p.wait()
        return rc
    finally:
        try:
            outp.close(); errp.close()
        except Exception:
            pass


async def handle_task(task_path: Path) -> None:
    try:
        data = json.loads(task_path.read_text())
    except Exception as e:
        log(f"[err] failed to parse {task_path.name}: {e}")
        task_path.unlink(missing_ok=True)
        return

    t = data.get("type")
    if t == "scan-file":
        path = str(data.get("path", ""))
        win = str(data.get("win", 4096))
        k = str(data.get("k", 50))
        mods = str(data.get("mods", "64,128,256,512,4096"))
        zlib = bool(data.get("zlib", False))
        lags = bool(data.get("lags", False))
        lags_set = str(data.get("lags_set", ""))
        delta = bool(data.get("delta", False))
        dupes = bool(data.get("dupes", False))
        magic = bool(data.get("magic", False))
        if not path:
            log(f"[skip] scan-file missing path in {task_path.name}")
        else:
            log(f"[task] scan-file path={path} win={win} k={k} mods={mods} zlib={zlib} lags={lags} delta={delta} dupes={dupes} magic={magic}")
            extra = []
            if zlib: extra.append("--zlib")
            if lags: extra.append("--lags")
            if lags_set:
                extra += ["--lags-set", lags_set]
            if delta: extra.append("--delta")
            if dupes: extra.append("--dupes")
            if magic: extra.append("--magic")
            rc = await run_cmd(
                "scan_file",
                VENV_PY,
                str(ROOT / "dev/working/tools/pattern_scan.py"),
                "scan-file",
                "--path", path,
                "--win", win,
                "--k", k,
                "--mods", mods,
                *extra,
            )
            log(f"[done] scan-file rc={rc}")

    elif t == "scan-blob":
        name = str(data.get("name", "pfs_vblob_test"))
        size_mb = str(data.get("size_mb", 100))
        seed = str(data.get("seed", 1337))
        win = str(data.get("win", 4096))
        k = str(data.get("k", 50))
        mods = str(data.get("mods", "64,128,256,512,4096"))
        keep = bool(data.get("keep_snapshot", False))
        zlib = bool(data.get("zlib", False))
        lags = bool(data.get("lags", False))
        lags_set = str(data.get("lags_set", ""))
        delta = bool(data.get("delta", False))
        dupes = bool(data.get("dupes", False))
        magic = bool(data.get("magic", False))
        log(f"[task] scan-blob name={name} size_mb={size_mb} seed={seed} win={win} zlib={zlib} lags={lags} delta={delta} dupes={dupes} magic={magic}")
        extra = []
        if keep: extra.append("--keep-snapshot")
        if zlib: extra.append("--zlib")
        if lags: extra.append("--lags")
        if lags_set:
            extra += ["--lags-set", lags_set]
        if delta: extra.append("--delta")
        if dupes: extra.append("--dupes")
        if magic: extra.append("--magic")
        rc = await run_cmd(
            "scan_blob",
            VENV_PY,
            str(ROOT / "dev/working/tools/pattern_scan.py"),
            "scan-blob",
            "--name", name,
            "--size-mb", size_mb,
            "--seed", str(seed),
            "--win", win,
            "--k", k,
            "--mods", mods,
            *extra,
        )
        log(f"[done] scan-blob rc={rc}")

    else:
        log(f"[skip] unknown task type in {task_path.name}: {t}")

    task_path.unlink(missing_ok=True)


async def watch_queue(poll_ms: int = 250) -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        tasks = sorted(QUEUE_DIR.glob("*.json"))
        if tasks:
            # FIFO by filename
            tp = tasks[0]
            await handle_task(tp)
        else:
            await asyncio.sleep(poll_ms / 1000.0)


async def heartbeat() -> None:
    while True:
        log("[hb] alive")
        await asyncio.sleep(10)


def main() -> int:
    ap = argparse.ArgumentParser(description="Single-core async worker for PacketFS research tasks")
    ap.add_argument("--cpu", type=int, default=0, help="CPU core to pin to (Linux)")
    args = ap.parse_args()

    pin_cpu(args.cpu)
    pid = os.getpid()
    log(f"[start] async_core pinned cpu={args.cpu} pid={pid}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.create_task(heartbeat())
        loop.run_until_complete(watch_queue())
    except KeyboardInterrupt:
        log("[stop] KeyboardInterrupt")
    finally:
        loop.stop(); loop.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
