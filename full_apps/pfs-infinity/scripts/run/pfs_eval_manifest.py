#!/usr/bin/env python3
"""
Evaluate a PacketFS super manifest by streaming 1 MiB windows from a provider's base_url
through your /compute endpoint, returning tiny results (counts/proofs) without payloads.

Usage:
  /home/punk/.venv/bin/python scripts/run/pfs_eval_manifest.py \
    --manifest-url https://USER.github.io/pfs-index/super_manifest.json \
    --endpoint http://localhost:5000 --op counteq --imm 0 \
    --provider-id pages --max-windows 64 --batch 16 --concurrency 4
"""
import argparse
import asyncio
import json
import os
import sys
from urllib.parse import urljoin

import aiohttp
import requests
import os


def get_session() -> requests.Session:
    s = requests.Session()
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        s.headers.update({'Authorization': f'token {token}'})
    s.headers.update({'Accept': 'application/json, text/plain, */*'})
    return s


def load_json(sess: requests.Session, url: str) -> dict:
    r = sess.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


async def post_batch(session, endpoint: str, data_url: str, instr_batch: list[dict]) -> dict:
    payload = { 'data_url': data_url, 'instructions': instr_batch }
    async with session.post(endpoint.rstrip('/') + '/compute', json=payload) as resp:
        return await resp.json()


async def main_async(args):
    sess = get_session()
    super_manifest = load_json(sess, args.manifest_url)
    base_super = args.manifest_url.rsplit('/', 1)[0] + '/'

    # Choose provider
    prov_entry = None
    for p in super_manifest.get('providers', []):
        if args.provider_id is None or p.get('id') == args.provider_id:
            prov_entry = p
            break
    if prov_entry is None:
        print('[error] provider not found in manifest', file=sys.stderr)
        sys.exit(2)

    prov_url = prov_entry['manifest_url']
    prov_url_abs = prov_url if prov_url.startswith('http') else urljoin(base_super, prov_url)
    prov = load_json(sess, prov_url_abs)

    data_url = prov['base_url']
    seg_bytes = int(prov.get('segment_bytes', 1048576))

    # Collect first N windows from chunk_000
    wm = prov.get('window_map', {})
    chunks = wm.get('chunks', [])
    if not chunks:
        print('[error] provider has no window_map chunks', file=sys.stderr)
        sys.exit(2)
    first_chunk = chunks[0]
    chunk_url = first_chunk['url']
    chunk_abs = chunk_url if chunk_url.startswith('http') else urljoin(base_super, chunk_url)

    # Fetch and parse windows (jsonl+gzip or plain jsonl)
    r = sess.get(chunk_abs, timeout=30)
    r.raise_for_status()
    content = r.content
    import gzip, io
    windows = []
    try:
        with gzip.open(io.BytesIO(content), 'rt', encoding='utf-8') as gz:
            for line in gz:
                if line.strip():
                    windows.append(json.loads(line))
    except OSError:
        for line in content.decode('utf-8', errors='ignore').splitlines():
            if line.strip():
                windows.append(json.loads(line))

    windows = windows[:args.max_windows]

    # Build instruction batches
    batches = []
    batch = []
    for w in windows:
        batch.append({ 'op': args.op, 'imm': args.imm, 'offset': int(w['offset']), 'length': int(w['length']) })
        if len(batch) >= args.batch:
            batches.append(batch)
            batch = []
    if batch:
        batches.append(batch)

    results = []
    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(args.concurrency)
        async def worker(b):
            async with sem:
                out = await post_batch(session, args.endpoint, data_url, b)
                results.append(out)
        tasks = [asyncio.create_task(worker(b)) for b in batches]
        await asyncio.gather(*tasks)

    # Summarize
    total_bytes = 0
    total_instr = 0
    for out in results:
        for t in out.get('timing', []) or []:
            total_bytes += int(t.get('bytes_processed', 0))
            total_instr += 1
    print(json.dumps({
        'endpoint': args.endpoint,
        'data_url': data_url,
        'windows_requested': len(windows),
        'instructions_sent': total_instr,
        'bytes_processed': total_bytes
    }, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest-url', required=True)
    ap.add_argument('--endpoint', default='http://localhost:5000')
    ap.add_argument('--provider-id')
    ap.add_argument('--op', default='counteq')
    ap.add_argument('--imm', type=int, default=0)
    ap.add_argument('--max-windows', type=int, default=64)
    ap.add_argument('--batch', type=int, default=16)
    ap.add_argument('--concurrency', type=int, default=4)
    args = ap.parse_args()
    asyncio.run(main_async(args))