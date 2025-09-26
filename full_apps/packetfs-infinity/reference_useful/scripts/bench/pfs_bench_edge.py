#!/usr/bin/env python3
"""
Edge benchmark (duration-based): streams 1 MiB windows with concurrency to /compute
and appends JSONL results to var/vpcpu/baselines.jsonl.

Example:
  /home/punk/.venv/bin/python scripts/bench/pfs_bench_edge.py \
    --endpoint http://localhost:5000 --path /dev/shm/pfs_blob.bin \
    --op counteq --imm 0 --window-mb 1 --concurrency 8 --duration-s 60 --label local
"""
import argparse, asyncio, aiohttp, os, time, json, datetime, re
from typing import Tuple
import requests

async def post_window(session, endpoint, data_url, op, imm, offset, length):
    payload = {
        'data_url': data_url,
        'instructions': [{'op': op, 'imm': imm, 'offset': offset, 'length': length}]
    }
    async with session.post(endpoint.rstrip('/') + '/compute', json=payload) as resp:
        j = await resp.json()
        bp = 0
        if isinstance(j.get('timing'), list) and j['timing']:
            bp = int(j['timing'][0].get('bytes_processed', 0))
        elif 'data_size' in j:
            bp = int(j['data_size'])
        return bp, j

def _remote_size(url: str) -> int:
    try:
        h = requests.head(url, allow_redirects=True, timeout=15)
        cl = h.headers.get('Content-Length')
        if cl is not None:
            return int(cl)
        # Fallback to range probe
        g = requests.get(url, headers={'Range':'bytes=0-0'}, stream=True, timeout=20)
        cr = g.headers.get('Content-Range')  # e.g., 'bytes 0-0/12345'
        if cr:
            m = re.search(r"/(\d+)$", cr)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    raise RuntimeError(f"Could not determine remote size for {url}")

async def run_bench(args):
    # Allow http(s) URLs and file paths
    if args.path.startswith('http://') or args.path.startswith('https://') or args.path.startswith('file://'):
        data_url = args.path
    else:
        data_url = 'file://' + args.path
    # Determine size
    if data_url.startswith('file://'):
        size = os.path.getsize(data_url[7:])
    elif data_url.startswith('http://') or data_url.startswith('https://'):
        size = _remote_size(data_url)
    else:
        size = os.path.getsize(args.path)
    win = args.window_mb * 1024 * 1024
    endpoint = args.endpoint

    # Shared state
    next_offset = 0
    lock = asyncio.Lock()
    bytes_done = 0
    requests_made = 0

    end_time = time.time() + args.duration_s

    async def next_window() -> Tuple[int,int]:
        nonlocal next_offset
        async with lock:
            if next_offset >= size:
                next_offset = 0
            offset = next_offset
            length = min(win, size - offset)
            next_offset += length
            return offset, length

    async with aiohttp.ClientSession() as session:
        async def worker():
            nonlocal bytes_done, requests_made
            while time.time() < end_time:
                offset, length = await next_window()
                bp, _ = await post_window(session, endpoint, data_url, args.op, args.imm, offset, length)
                bytes_done += bp
                requests_made += 1
        tasks = [asyncio.create_task(worker()) for _ in range(args.concurrency)]
        await asyncio.gather(*tasks)

    elapsed = args.duration_s
    mbps = (bytes_done / (1024*1024)) / elapsed if elapsed > 0 else 0.0
    gbps = mbps / 1024.0

    result = {
        'ts': datetime.datetime.utcnow().isoformat() + 'Z',
        'endpoint': endpoint,
        'data_url': data_url,
        'op': args.op,
        'imm': args.imm,
        'window_mb': args.window_mb,
        'concurrency': args.concurrency,
        'duration_s': elapsed,
        'bytes_processed': bytes_done,
        'requests': requests_made,
        'throughput_mb_s': round(mbps, 3),
        'cpupwn_gb_s': round(gbps, 3),
        'label': args.label,
    }

    os.makedirs('var/vpcpu', exist_ok=True)
    with open('var/vpcpu/baselines.jsonl', 'a') as f:
        f.write(json.dumps(result) + '\n')

    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', default='http://localhost:5000')
    ap.add_argument('--path', required=True)
    ap.add_argument('--op', default='counteq', choices=['counteq','crc32c','fnv64','xor','add'])
    ap.add_argument('--imm', type=int, default=0)
    ap.add_argument('--window-mb', type=int, default=1)
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--duration-s', type=int, default=60)
    ap.add_argument('--label', default='local')
    args = ap.parse_args()
    asyncio.run(run_bench(args))