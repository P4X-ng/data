"""Minimal compression utilities.

Currently wraps gzip for deterministic, blocking compression of in-memory
byte sequences. No streaming / async yet. API intentionally small so a future
native or alternative codec layer can slot in without churn.
"""
from __future__ import annotations

from dataclasses import dataclass
import gzip
import time
from typing import Optional


@dataclass(frozen=True)
class CompressionResult:
    original_size: int
    compressed_size: int
    ratio: float  # original / compressed (>=1 when compression effective)
    algo: str
    time_ms: float
    error: Optional[str] = None


def compress_bytes(data: bytes, level: int = 6) -> tuple[bytes, CompressionResult]:
    start = time.perf_counter()
    try:
        out = gzip.compress(data, compresslevel=level)
        elapsed_ms = (time.perf_counter() - start) * 1000
        csz = len(out)
        ratio = (len(data) / csz) if csz > 0 else 1.0
        return out, CompressionResult(len(data), csz, ratio, f"gzip-{level}", elapsed_ms)
    except Exception as e:  # pragma: no cover (rare)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return b"", CompressionResult(len(data), 0, 1.0, f"gzip-{level}", elapsed_ms, error=str(e))


def decompress_bytes(data: bytes) -> bytes:
    return gzip.decompress(data)


__all__ = [
    'CompressionResult',
    'compress_bytes',
    'decompress_bytes',
]
