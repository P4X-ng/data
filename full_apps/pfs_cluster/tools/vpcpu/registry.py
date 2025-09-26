#!/usr/bin/env python3
import os
import json
import sqlite3
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join('var', 'vpcpu', 'assets.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,   -- e.g., worker, edge_http, nft_local, aws_flowlogs
  endpoint TEXT NOT NULL,
  attrs TEXT NOT NULL,  -- JSON
  created_at REAL NOT NULL
);
"""

@dataclass
class Asset:
    name: str
    kind: str
    endpoint: str
    attrs: Dict[str, Any]


def _ensure_db(path: str = DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.executescript(SCHEMA)
    finally:
        conn.commit()
        conn.close()


def add_asset(asset: Asset, path: str = DB_PATH) -> int:
    _ensure_db(path)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO assets (name, kind, endpoint, attrs, created_at) VALUES (?,?,?,?,?)',
            (asset.name, asset.kind, asset.endpoint, json.dumps(asset.attrs), time.time())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_assets(path: str = DB_PATH) -> List[Asset]:
    _ensure_db(path)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        rows = cur.execute('SELECT name, kind, endpoint, attrs FROM assets ORDER BY id DESC').fetchall()
        assets = []
        for name, kind, endpoint, attrs in rows:
            assets.append(Asset(name=name, kind=kind, endpoint=endpoint, attrs=json.loads(attrs)))
        return assets
    finally:
        conn.close()