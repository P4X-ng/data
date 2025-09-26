#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import sys
import time
from typing import List, Dict, Any, Tuple

import requests
import httpx


def windows_for_file(path: str, window_size: int) -> List[Tuple[int, int]]:
    st = os.stat(path)
    size = st.st_size
    out: List[Tuple[int, int]] = []
    off = 0
    while off < size:
        ln = min(window_size, size - off)
        out.append((off, ln))
        off += ln
    return out


def submit_job_session(client: httpx.Client, endpoint: str, data_url: str, program: List[Dict[str, Any]], off: int, ln: int, gpu_device: int | None, timeout: float = 300.0) -> Dict[str, Any]:
    url = endpoint.rstrip('/') + '/gpu/program'
    body: Dict[str, Any] = {
        'data_url': data_url,
        'program': program,
        'offset': off,
        'length': ln,
    }
    if gpu_device is not None:
        body['gpu_device'] = gpu_device
    r = client.post(url, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser(description='PacketFS swarm coordinator (GPU program dispatcher)')
    ap.add_argument('--endpoint', default='http://127.0.0.1:8811', help='Host Infinity endpoint')
    ap.add_argument('--path', required=True, help='Local file path to process')
    ap.add_argument('--winmb', type=int, default=1, help='Window size (MiB)')
    ap.add_argument('--max-windows', type=int, default=0, help='Limit number of windows (0=all)')
    ap.add_argument('--devices', default='0,1', help='Comma-separated GPU device ids to round-robin over (CuPy)')
    ap.add_argument('--concurrency', type=int, default=8, help='Concurrent jobs per device')
    ap.add_argument('--program', default='[{"op":"xor","imm":255},{"op":"counteq","imm":0},{"op":"crc32c"}]', help='JSON list of ops')
    args = ap.parse_args()

    window_size = args.winmb * 1024 * 1024
    if not os.path.exists(args.path):
        print(f'file not found: {args.path}', file=sys.stderr)
        return 2

    # Build windows
    wins = windows_for_file(args.path, window_size)
    if args.max_windows and args.max_windows > 0:
        wins = wins[: args.max_windows]

    devices = [int(x) for x in args.devices.split(',') if x.strip() != '']
    if not devices:
        devices = [None]  # type: ignore

    try:
        program = json.loads(args.program)
    except Exception as e:
        print(f'bad --program JSON: {e}', file=sys.stderr)
        return 2

    data_url = 'file://' + args.path

    total_bytes = 0
    t0 = time.time()

    # Thread pool per device
    per_dev = max(1, int(args.concurrency))
    pool_size = per_dev * len(devices)

    print(f'[coord] endpoint={args.endpoint} path={args.path} windows={len(wins)} win={args.winmb} MiB devices={devices} conc/dev={per_dev} pool={pool_size}')

    # Build persistent clients (HTTP/2 if https)
    is_https = args.endpoint.lower().startswith('https://')
    clients = {}
    for dev in devices if devices and devices[0] is not None else [None]:
        clients[dev] = httpx.Client(http2=True if is_https else False, verify=False, timeout=60.0)

    # Round-robin windows across devices
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as ex:
        for i, (off, ln) in enumerate(wins):
            dev = devices[i % len(devices)] if devices and devices[0] is not None else None
            client = clients[dev]
            futures.append(ex.submit(submit_job_session, client, args.endpoint, data_url, program, off, ln, dev))
        # Collect
        good = 0
        bad = 0
        agg_cpupwn = 0.0
        for f in concurrent.futures.as_completed(futures):
            try:
                out = f.result()
                m = out.get('metrics', {}) if isinstance(out, dict) else {}
                total_bytes += int((m.get('bytes_processed') or 0))
                agg_cpupwn += float((m.get('cpupwn_gbps') or 0.0))
                good += 1
            except Exception as e:
                print(f'[coord] job error: {e}', file=sys.stderr)
                bad += 1
        elapsed = time.time() - t0

    # Close clients
    for c in clients.values():
        try:
            c.close()
        except Exception:
            pass

    gb = total_bytes / (1024**3)
    gbps = gb / max(elapsed, 1e-9)

    print(json.dumps({
        'windows': len(wins),
        'good': good,
        'bad': bad,
        'elapsed_s': elapsed,
        'bytes_total': total_bytes,
        'throughput_gbps': gbps,
        'sum_cpupwn_gbps': agg_cpupwn
    }, indent=2))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())