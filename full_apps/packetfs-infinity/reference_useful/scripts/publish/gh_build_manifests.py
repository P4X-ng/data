#!/usr/bin/env python3
"""
GitHub Pages manifest publisher (PacketFS v1)
- Splits a local object into 1 MiB windows
- Computes sha256 and crc32c per window
- Emits:
  - docs/super_manifest.json
  - docs/providers/<provider_id>.json
  - docs/windows/chunk_000.jsonl.gz (jsonl+gzip of window records)

NOTE: This POC computes digests from a local file path. Set base_url to the public URL
(your CDN/origin) that will serve Range windows for this object.

Usage:
  /home/punk/.venv/bin/python scripts/publish/gh_build_manifests.py \
    --object-path /dev/shm/pfs_blob.bin \
    --base-url https://YOUR_CF/sha256/<digest>.bin \
    --provider-id pages \
    --window-mb 1 \
    --output-dir docs
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from typing import Iterator

# Bitwise CRC32C (Castagnoli) tableless implementation (slow but dependency-free)
def crc32c_bytes(data: bytes, init_crc: int = 0xFFFFFFFF) -> int:
    crc = init_crc
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x82F63B78
            else:
                crc >>= 1
    return crc ^ 0xFFFFFFFF


def read_windows(path: str, window_bytes: int) -> Iterator[tuple[int, bytes]]:
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        offset = 0
        while offset < size:
            to_read = min(window_bytes, size - offset)
            buf = f.read(to_read)
            if not buf:
                break
            yield offset, buf
            offset += len(buf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--object-path', required=True, help='Local file path to object')
    ap.add_argument('--base-url', required=True, help='Public base URL serving the object via Range (e.g., CloudFront)')
    ap.add_argument('--provider-id', default='pages')
    ap.add_argument('--window-mb', type=int, default=1)
    ap.add_argument('--output-dir', default='docs')
    args = ap.parse_args()

    obj_path = args.object_path
    if not os.path.exists(obj_path) or not os.path.isfile(obj_path):
        print(f"[error] object-path not found or not a file: {obj_path}", file=sys.stderr)
        sys.exit(2)

    out_dir = args.output_dir
    providers_dir = os.path.join(out_dir, 'providers')
    windows_dir = os.path.join(out_dir, 'windows')
    os.makedirs(providers_dir, exist_ok=True)
    os.makedirs(windows_dir, exist_ok=True)

    window_bytes = args.window_mb * 1024 * 1024
    size = os.path.getsize(obj_path)

    # Compute file-level sha256 (streaming)
    sha256_all = hashlib.sha256()
    with open(obj_path, 'rb') as f:
        while True:
            chunk = f.read(4 * 1024 * 1024)
            if not chunk:
                break
            sha256_all.update(chunk)
    file_sha256 = sha256_all.hexdigest()

    # Build one chunk (POC) of window_map (jsonl gz)
    chunk_path = os.path.join(windows_dir, 'chunk_000.jsonl.gz')
    records = 0
    with gzip.open(chunk_path, 'wt', encoding='utf-8') as gz:
        for offset, buf in read_windows(obj_path, window_bytes):
            sha = hashlib.sha256(buf).hexdigest()
            crc = crc32c_bytes(buf)
            rec = {
                'offset': offset,
                'length': len(buf),
                'sha256': sha,
                'crc32c': f"{crc}",
                'transform': None,
                'proof': None,
            }
            gz.write(json.dumps(rec) + '\n')
            records += 1

    chunk_bytes = os.path.getsize(chunk_path)

    # Provider manifest
    provider_manifest = {
        'version': 'pfs-provider-1',
        'provider_id': args.provider_id,
        'base_url': args.base_url,
        'accept_ranges': True,
        'etag': None,
        'last_modified': None,
        'segment_bytes': window_bytes,
        'budget': { 'max_rps': 5, 'max_bytes_day': 25 * 1024 * 1024 * 1024, 'concurrency': 8 },
        'window_map': {
            'format': 'jsonl+gzip',
            'chunks': [
                { 'idx': 0, 'url': 'windows/chunk_000.jsonl.gz', 'bytes': chunk_bytes }
            ]
        },
        'sign': { 'alg': 'none' }
    }
    provider_path = os.path.join(providers_dir, f'{args.provider_id}.json')
    with open(provider_path, 'w', encoding='utf-8') as f:
        json.dump(provider_manifest, f, indent=2)

    # Super manifest
    windows = (size + window_bytes - 1) // window_bytes
    super_manifest = {
        'version': 'pfs-1',
        'object': {
            'sha256': file_sha256,
            'size': size,
            'window_bytes': window_bytes,
            'windows': windows
        },
        'providers': [
            {
                'id': args.provider_id,
                'type': 'pages',
                'priority': 10,
                'manifest_url': f'providers/{args.provider_id}.json',
                'cost_weight': 1.0,
                'region_tags': ['us']
            }
        ],
        'sign': { 'alg': 'none' }
    }
    super_path = os.path.join(out_dir, 'super_manifest.json')
    with open(super_path, 'w', encoding='utf-8') as f:
        json.dump(super_manifest, f, indent=2)

    print('[ok] Wrote:')
    print(' ', super_path)
    print(' ', provider_path)
    print(' ', chunk_path, f'({chunk_bytes} bytes) with {records} windows')

if __name__ == '__main__':
    main()