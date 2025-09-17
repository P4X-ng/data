from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from typing import List, Tuple

from .virtual_blob import VirtualBlob


@dataclass
class BlobConfig:
    name: str
    size_bytes: int
    seed: int
    meta_dir: str


class BlobFS:
    """
    Minimal append-only allocator over VirtualBlob, with a tiny SQLite metastore.
    Stores object→(offset,length) segments for reconstruction via BREF.
    """

    def __init__(self, cfg: BlobConfig):
        self.cfg = cfg
        os.makedirs(cfg.meta_dir, exist_ok=True)
        self.db_path = os.path.join(cfg.meta_dir, f"{cfg.name}.sqlite")
        self._init_db()
        self.vb = VirtualBlob(cfg.name, cfg.size_bytes, cfg.seed)
        self.vb.create_or_attach(create=True)
        # Do not auto-fill here; assume caller chose policy
        self._ensure_alloc_ptr()

    def close(self) -> None:
        try:
            self.vb.close()
        except Exception:
            pass

    # --- SQLite helpers ---
    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS objects (object_id TEXT PRIMARY KEY, size INTEGER, sha256 TEXT, windows INTEGER, window_size INTEGER, created_ts INTEGER)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS segments (object_id TEXT, seq INTEGER, off INTEGER, len INTEGER, PRIMARY KEY(object_id, seq))"
            )

    def _ensure_alloc_ptr(self) -> None:
        with self._conn() as c:
            cur = c.execute("SELECT value FROM meta WHERE key='alloc_off'")
            row = cur.fetchone()
            if not row:
                c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('alloc_off','4096')")

    def _alloc(self, length: int) -> List[Tuple[int, int]]:
        """Append allocate 'length' bytes; may wrap.
        Returns list of (offset,length) segments covering the allocation.
        """
        length = int(length)
        if length <= 0:
            return []
        with self._conn() as c:
            off = int(c.execute("SELECT value FROM meta WHERE key='alloc_off'").fetchone()[0])
            size = self.cfg.size_bytes
            end = off + length
            segs: List[Tuple[int, int]] = []
            if end <= size:
                segs.append((off, length))
                new_off = end
            else:
                first = size - off
                if first > 0:
                    segs.append((off, first))
                rem = length - first
                # wrap to 4096 to preserve header
                segs.append((4096, rem))
                new_off = 4096 + rem
            # constrain
            if new_off >= size:
                new_off = 4096 + (new_off - size)
            c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('alloc_off',?)", (str(new_off),))
            return segs

    def write_bytes(self, data: bytes) -> List[Tuple[int, int]]:
        segs = self._alloc(len(data))
        if not segs:
            return []
        mv = self.vb.buffer
        pos = 0
        for off, ln in segs:
            mv[off:off+ln] = data[pos:pos+ln]
            pos += ln
        return segs

    def record_object(self, object_id: str, size: int, sha256: str, window_size: int, segs: List[Tuple[int,int]]) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO objects(object_id,size,sha256,windows,window_size,created_ts) VALUES(?,?,?,?,?,?)",
                (object_id, int(size), sha256, len(segs), int(window_size), int(time.time())),
            )
            c.executemany(
                "INSERT OR REPLACE INTO segments(object_id,seq,off,len) VALUES(?,?,?,?)",
                [(object_id, i, int(off), int(ln)) for i,(off,ln) in enumerate(segs)],
            )

    def get_segments(self, object_id: str) -> List[Tuple[int,int]]:
        with self._conn() as c:
            cur = c.execute("SELECT off,len FROM segments WHERE object_id=? ORDER BY seq ASC", (object_id,))
            return [(int(a), int(b)) for (a,b) in cur.fetchall()]