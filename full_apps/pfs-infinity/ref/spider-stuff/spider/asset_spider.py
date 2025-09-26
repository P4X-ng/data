#!/usr/bin/env python3
"""
Asset Spider: discovers data URLs, records cache/Range capabilities, and optionally probes an edge compute endpoint.
- Allowed domains only (safety)
- HEAD to read ETag/Accept-Ranges/Content-Length
- Optional tiny Range GET (0-65535) to capture cache headers (CF-Cache-Status/X-Cache/Age)
- Optional compute probe via edge endpoint (worker/edge_http) on a 64 KiB window (counteq or crc32c)
- Stores discoveries in var/vpcpu/data_assets.db
"""
import argparse
import time
import re
import sys
from urllib.parse import urljoin, urlparse
import requests
from app.tools.vpcpu.data_catalog import upsert_asset, detect_vendor

DEFAULT_RANGE = (0, 65535)


def same_org(host: str, allowed: list[str]) -> bool:
    host = host.lower()
    return any(host == d or host.endswith('.' + d) for d in allowed)


def is_probably_html(ct: str | None) -> bool:
    return ct is not None and 'text/html' in ct.lower()


def extract_links(html: str, base_url: str) -> list[str]:
    # naive href extractor to avoid heavy deps
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    out = []
    for h in hrefs:
        try:
            out.append(urljoin(base_url, h))
        except Exception:
            continue
    return out


def head_url(url: str, timeout: int = 10):
    return requests.head(url, allow_redirects=True, timeout=timeout)


def tiny_range_probe(url: str, begin: int, end: int, timeout: int = 15):
    headers = {'Range': f'bytes={begin}-{end}'}
    return requests.get(url, headers=headers, stream=True, timeout=timeout)


def maybe_compute_probe(endpoint: str | None, kind: str | None, url: str, offset: int, length: int) -> float | None:
    if not endpoint or not kind:
        return None
    try:
        t0 = time.time()
        payload = {
            'data_url': url,
            'instructions': [{'op': 'counteq', 'imm': 0, 'offset': offset, 'length': length}],
        }
        ep = endpoint.rstrip('/') + '/compute'
        r = requests.post(ep, json=payload, timeout=30)
        if r.status_code != 200:
            return None
        j = r.json()
        elapsed = time.time() - t0
        bytes_proc = 0
        if 'timing' in j and isinstance(j['timing'], list) and j['timing']:
            bytes_proc = j['timing'][0].get('bytes_processed', 0)
        elif 'data_size' in j:
            bytes_proc = j.get('data_size', 0)
        if elapsed > 0 and bytes_proc:
            return bytes_proc / elapsed
        return None
    except Exception:
        return None


def crawl(seed_urls: list[str], allowed_domains: list[str], max_pages: int, do_range_probe: bool, compute_endpoint: str | None, compute_kind: str | None):
    seen = set()
    q = list(seed_urls)
    pages = 0

    while q and pages < max_pages:
        url = q.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            parsed = urlparse(url)
            if not parsed.scheme.startswith('http'):
                continue
            if not same_org(parsed.netloc, allowed_domains):
                continue

            # HEAD
            rh = head_url(url)
            headers = {k: v for k, v in rh.headers.items()}
            vendor = detect_vendor(headers) or ''
            meta = {
                'url': url,
                'content_length': int(headers.get('Content-Length')) if headers.get('Content-Length') else None,
                'etag': headers.get('ETag'),
                'accept_ranges': headers.get('Accept-Ranges'),
                'server': headers.get('Server'),
                'cdn_vendor': vendor,
                'cache_header': headers.get('CF-Cache-Status') or headers.get('X-Cache'),
                'age_header': headers.get('Age'),
                'last_modified': headers.get('Last-Modified'),
                'bps_estimate': None,
                'notes': None,
            }

            # Optional tiny Range probe to capture cache headers
            if do_range_probe and headers.get('Accept-Ranges', '').lower().startswith('bytes'):
                rr = tiny_range_probe(url, DEFAULT_RANGE[0], DEFAULT_RANGE[1])
                rh2 = {k: v for k, v in rr.headers.items()}
                meta['cache_header'] = rh2.get('CF-Cache-Status') or rh2.get('X-Cache') or meta['cache_header']
                meta['age_header'] = rh2.get('Age') or meta['age_header']
                if compute_endpoint:
                    # measure quick compute bps on the same small window
                    bps = maybe_compute_probe(compute_endpoint, compute_kind, url, DEFAULT_RANGE[0], DEFAULT_RANGE[1]-DEFAULT_RANGE[0]+1)
                    meta['bps_estimate'] = bps

            upsert_asset(meta)
            pages += 1

            # For HTML, fetch small body to discover more links (same org)
            ct = rh.headers.get('Content-Type')
            if is_probably_html(ct) and len(q) < max_pages:
                try:
                    rfull = requests.get(url, timeout=10)
                    if 'text/html' in rfull.headers.get('Content-Type','').lower():
                        links = extract_links(rfull.text, url)
                        for link in links:
                            p = urlparse(link)
                            if same_org(p.netloc, allowed_domains) and link not in seen:
                                q.append(link)
                except Exception:
                    pass

        except Exception:
            continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', required=True, help='Comma-separated list of seed URLs')
    ap.add_argument('--allow', required=True, help='Comma-separated allowed domains (suffix match)')
    ap.add_argument('--max-pages', type=int, default=50)
    ap.add_argument('--range-probe', action='store_true')
    ap.add_argument('--compute-endpoint', help='Edge compute endpoint (worker or edge_http) for optional probe')
    ap.add_argument('--compute-kind', choices=['worker','edge_http'])
    args = ap.parse_args()

    seeds = [s.strip() for s in args.seeds.split(',') if s.strip()]
    allowed = [d.strip().lower() for d in args.allow.split(',') if d.strip()]

    crawl(seeds, allowed, args.max_pages, args.range_probe, args.compute_endpoint, args.compute_kind)

if __name__ == '__main__':
    main()