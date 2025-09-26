#!/usr/bin/env python3
"""
Fetch a PacketFS super manifest from GitHub Pages (or any HTTP URL),
resolve provider manifests and window_map chunks (jsonl+gzip), and
emit a compact index JSON with window digests/proofs to var/vpcpu/index/.

Usage:
  /home/punk/.venv/bin/python scripts/publish/gh_fetch_index.py \
    --manifest-url https://USER.github.io/pfs-index/super_manifest.json \
    --out var/vpcpu/index/pages_index.json
"""
import argparse
import gzip
import io
import json
import os
import sys
import time
from urllib.parse import urljoin, urlparse

import os
import requests


def get_session() -> requests.Session:
    s = requests.Session()
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        s.headers.update({'Authorization': f'token {token}'})
    # Accept raw/json from Pages/Gist
    s.headers.update({'Accept': 'application/json, text/plain, */*'})
    return s


def load_json(sess: requests.Session, url: str) -> dict:
    r = sess.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_chunk_lines(sess: requests.Session, url: str):
    r = sess.get(url, timeout=30)
    r.raise_for_status()
    data = r.content
    try:
        bio = io.BytesIO(data)
        with gzip.open(bio, 'rt', encoding='utf-8') as gz:
            for line in gz:
                if line.strip():
                    yield json.loads(line)
    except OSError:
        # Not gzipped? Try plain jsonl
        for line in data.decode('utf-8', errors='ignore').splitlines():
            if line.strip():
                yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest-url', required=True)
    ap.add_argument('--out', default='var/vpcpu/index/pages_index.json')
    args = ap.parse_args()

    super_url = args.manifest_url
    base_super = super_url.rsplit('/', 1)[0] + '/'

    sess = get_session()

    super_manifest = load_json(sess, super_url)

    providers = super_manifest.get('providers', [])
    if not providers:
        print('[error] super manifest has no providers', file=sys.stderr)
        sys.exit(2)

    # Aggregate windows across providers (we keep unique offsets)
    windows = {}
    provider_summaries = []

    for p in providers:
        man_url = p.get('manifest_url')
        if not man_url:
            continue
        man_url_abs = man_url if man_url.startswith('http') else urljoin(base_super, man_url)
        prov = load_json(sess, man_url_abs)

        wm = prov.get('window_map', {})
        chunks = wm.get('chunks', [])
        chunk_count = 0
        win_count = 0
        for ch in chunks:
            cu = ch.get('url')
            if not cu:
                continue
            cu_abs = cu if cu.startswith('http') else urljoin(base_super, cu)
            for rec in fetch_chunk_lines(sess, cu_abs):
                off = int(rec['offset'])
                # Prefer first-seen entry per offset
                if off not in windows:
                    windows[off] = {
                        'length': int(rec['length']),
                        'sha256': rec.get('sha256'),
                        'crc32c': rec.get('crc32c'),
                        'transform': rec.get('transform'),
                        'proof': rec.get('proof'),
                        'provider_id': p.get('id') or prov.get('provider_id'),
                    }
                    win_count += 1
            chunk_count += 1
        provider_summaries.append({
            'provider_id': p.get('id') or prov.get('provider_id'),
            'manifest_url': man_url_abs,
            'chunks': chunk_count,
            'windows_indexed': win_count,
        })

    ordered = dict(sorted(windows.items(), key=lambda x: x[0]))

    out_obj = {
        'source': super_url,
        'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'object': super_manifest.get('object', {}),
        'providers_seen': provider_summaries,
        'windows': ordered,
    }

    out_path = args.out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out_obj, f)
    print('[ok] wrote index:', out_path)
    print('    windows:', len(ordered))
    for s in provider_summaries:
        print('   -', s)


if __name__ == '__main__':
    main()