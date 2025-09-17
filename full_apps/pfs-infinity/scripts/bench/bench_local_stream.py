#!/usr/bin/env python3
"""
Local streaming benchmark: posts 1 MiB windowed compute to the local /compute server
against a file:// URL (fast tmpfs blob recommended), with configurable concurrency.

Example:
  /home/punk/.venv/bin/python scripts/bench/bench_local_stream.py \
    --endpoint http://localhost:5000 \
    --path /dev/shm/pfs_blob.bin \
    --window-mb 1 --concurrency 8 --max-windows 256 --op counteq --imm 0

Outputs overall throughput (MB/s) and CPUpwn (~GB/s).
"""
import argparse, asyncio, aiohttp, os, time

async def post_window(session, endpoint, data_url, op, imm, offset, length):
    payload = {
        'data_url': data_url,
        'instructions': [{'op': op, 'imm': imm, 'offset': offset, 'length': length}]
    }
    async with session.post(endpoint.rstrip('/') + '/compute', json=payload) as resp:
        j = await resp.json()
        # prefer timing[0].bytes_processed
        bp = 0
        if isinstance(j.get('timing'), list) and j['timing']:
            bp = int(j['timing'][0].get('bytes_processed', 0))
        elif 'data_size' in j:
            bp = int(j['data_size'])
        return bp, j

async def run_bench(args):
    size = os.path.getsize(args.path)
    win = args.window_mb * 1024 * 1024
    windows = []
    off = 0
    count = 0
    maxw = args.max_windows if args.max_windows > 0 else 1_000_000_000
    while off < size and count < maxw:
        ln = min(win, size - off)
        windows.append((off, ln))
        off += ln
        count += 1

    data_url = 'file://' + args.path
    endpoint = args.endpoint

    started = time.time()
    bytes_done = 0

    sem = asyncio.Semaphore(args.concurrency)
    async with aiohttp.ClientSession() as session:
        async def worker(offset, length):
            nonlocal bytes_done
            async with sem:
                bp, _ = await post_window(session, endpoint, data_url, args.op, args.imm, offset, length)
                bytes_done += bp
        tasks = [asyncio.create_task(worker(o,l)) for (o,l) in windows]
        await asyncio.gather(*tasks)

    elapsed = time.time() - started
    mbps = (bytes_done / (1024*1024)) / elapsed if elapsed > 0 else 0.0
    gbps = mbps / 1024.0
    print(f"windows={len(windows)} bytes={bytes_done} elapsed_s={elapsed:.3f} throughput={mbps:.1f} MB/s cpupwn≈{gbps:.2f} GB/s")

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', default='http://localhost:5000')
    ap.add_argument('--path', required=True)
    ap.add_argument('--window-mb', type=int, default=1)
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--max-windows', type=int, default=256, help='0 = all windows')
    ap.add_argument('--op', default='counteq', choices=['counteq','crc32c','fnv64','xor','add'])
    ap.add_argument('--imm', type=int, default=0)
    args = ap.parse_args()
    asyncio.run(run_bench(args))