#!/usr/bin/env python3
import os
import sqlite3
import time
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join('var', 'vpcpu', 'data_assets.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS data_assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL UNIQUE,
  content_length INTEGER,
  etag TEXT,
  accept_ranges TEXT,
  server TEXT,
  cdn_vendor TEXT,
  cache_header TEXT,
  age_header TEXT,
  last_modified TEXT,
  last_seen REAL NOT NULL,
  bps_estimate REAL,
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_data_assets_last_seen ON data_assets(last_seen);
"""

VENDOR_CLUES = [
    ('CF-Cache-Status', 'Cloudflare'),
    ('X-Cache', 'CloudFront'),
    ('X-Served-By', 'Fastly'),
    ('Server', 'Akamai'),
    ('Via', 'Varnish'),
]


def _ensure_db(path: str = DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.commit()
        conn.close()


def detect_vendor(headers: Dict[str, str]) -> Optional[str]:
    h = {k.lower(): v for k, v in headers.items()}
    if 'cf-cache-status' in h:
        return 'Cloudflare'
    if 'x-cache' in h and 'cloudfront' in h.get('x-cache', '').lower():
        return 'CloudFront'
    if 'x-served-by' in h and 'fastly' in h.get('x-served-by', '').lower():
        return 'Fastly'
    if 'server' in h and 'akamai' in h.get('server', '').lower():
        return 'Akamai'
    if 'via' in h and 'varnish' in h.get('via', '').lower():
        return 'Varnish/Fastly?'
    return None


def upsert_asset(meta: Dict[str, Any], path: str = DB_PATH):
    _ensure_db(path)
    now = time.time()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            INSERT INTO data_assets (url, content_length, etag, accept_ranges, server, cdn_vendor, cache_header, age_header, last_modified, last_seen, bps_estimate, notes)
            VALUES (:url, :content_length, :etag, :accept_ranges, :server, :cdn_vendor, :cache_header, :age_header, :last_modified, :last_seen, :bps_estimate, :notes)
            ON CONFLICT(url) DO UPDATE SET
              content_length=excluded.content_length,
              etag=excluded.etag,
              accept_ranges=excluded.accept_ranges,
              server=excluded.server,
              cdn_vendor=excluded.cdn_vendor,
              cache_header=excluded.cache_header,
              age_header=excluded.age_header,
              last_modified=excluded.last_modified,
              last_seen=excluded.last_seen,
              bps_estimate=COALESCE(excluded.bps_estimate, data_assets.bps_estimate),
              notes=COALESCE(excluded.notes, data_assets.notes)
            """,
            {
                'url': meta.get('url'),
                'content_length': meta.get('content_length'),
                'etag': meta.get('etag'),
                'accept_ranges': meta.get('accept_ranges'),
                'server': meta.get('server'),
                'cdn_vendor': meta.get('cdn_vendor'),
                'cache_header': meta.get('cache_header'),
                'age_header': meta.get('age_header'),
                'last_modified': meta.get('last_modified'),
                'last_seen': now,
                'bps_estimate': meta.get('bps_estimate'),
                'notes': meta.get('notes'),
            }
        )
        conn.commit()
    finally:
        conn.close()


def list_assets(limit: int = 50, path: str = DB_PATH) -> List[Dict[str, Any]]:
    _ensure_db(path)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        rows = cur.execute("SELECT url, content_length, etag, accept_ranges, server, cdn_vendor, cache_header, age_header, last_modified, last_seen, bps_estimate FROM data_assets ORDER BY last_seen DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            out.append({
                'url': r[0], 'content_length': r[1], 'etag': r[2], 'accept_ranges': r[3], 'server': r[4], 'cdn_vendor': r[5], 'cache_header': r[6], 'age_header': r[7], 'last_modified': r[8], 'last_seen': r[9], 'bps_estimate': r[10]
            })
        return out
    finally:
        conn.close()