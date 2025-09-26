from __future__ import annotations

import os
import mmap
import contextlib
from typing import Iterator, Optional

import httpx

# Shared-memory/VirtualBlob aware windowed reader with optional CPU pinning.
# Use this reader for consistent, cache-friendly IO and reproducible single-CPU runs.

ALIGN_DEFAULT = 1 << 20  # 1 MiB
CHUNK_DEFAULT = 4 << 20  # 4 MiB


def _crop_chunks(chunks: Iterator[bytes], window_start: int, window_len: Optional[int], fetch_start: int) -> Iterator[bytes]:
    """Crop upstream chunk iterator to [window_start, window_start+window_len)."""
    pos = fetch_start
    window_end = None if window_len is None else window_start + window_len
    for buf in chunks:
        if not buf:
            pos += 0
            continue
        if window_len is None:
            if pos < window_start:
                ls = window_start - pos
                if ls < len(buf):
                    yield buf[ls:]
            else:
                yield buf
        else:
            if pos >= window_end:  # type: ignore[operator]
                break
            left = max(pos, window_start)
            right = min(pos + len(buf), window_end)  # type: ignore[arg-type]
            if right > left:
                s = left - pos
                e = right - pos
                yield buf[s:e]
        pos += len(buf)


def _normalize_window(offset: Optional[int], length: Optional[int]) -> tuple[int, Optional[int]]:
    if offset is None and length is None:
        return 0, None
    if offset is not None and length is None:
        return int(offset), None
    if offset is None and length is not None:
        return 0, int(length)
    return int(offset), int(length)  # type: ignore[arg-type]


def stream_window(data_url: str, offset: Optional[int], length: Optional[int], *, align: int = ALIGN_DEFAULT, chunk: int = CHUNK_DEFAULT) -> Iterator[bytes]:
    """Yield exact window bytes from a source with aligned upstream fetch.

    Supports:
      - http(s):// URLs (uses Range)
      - file:// URLs
      - local filesystem paths

    Alignment improves CDN/cache friendliness; local paths ignore alignment for mmaps (we still respect window slicing).
    """
    window_start, window_len = _normalize_window(offset, length)

    # HTTP(S)
    if data_url.startswith("http://") or data_url.startswith("https://"):
        fetch_start = window_start
        fetch_len = window_len
        if align is not None and window_len is not None:
            fetch_start = (window_start // align) * align
            fetch_end_inclusive = (((window_start + window_len + align - 1) // align) * align) - 1
            fetch_len = fetch_end_inclusive - fetch_start + 1
        elif align is not None and window_len is None:
            fetch_start = (window_start // align) * align
        headers = {}
        if fetch_len is None:
            if fetch_start and fetch_start > 0:
                headers["Range"] = f"bytes={fetch_start}-"
        else:
            headers["Range"] = f"bytes={fetch_start}-{fetch_start + fetch_len - 1}"
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            r = client.get(data_url, headers=headers)
            r.raise_for_status()
            def http_chunks() -> Iterator[bytes]:
                for b in r.iter_bytes(chunk):
                    if not b:
                        break
                    yield b
            yield from _crop_chunks(http_chunks(), window_start, window_len, fetch_start)
        return

    # file:// and local paths via mmap
    path = data_url[7:] if data_url.startswith("file://") else data_url
    if not os.path.exists(path):
        raise FileNotFoundError(f"path not found: {path}")
    st = os.stat(path)
    fsize = st.st_size
    start = min(window_start, fsize)
    end = fsize if window_len is None else min(window_start + window_len, fsize)
    if end <= start:
        return
    with open(path, "rb") as f:
        f.seek(start)
        remaining = end - start
        while remaining > 0:
            to_read = chunk if remaining >= chunk else remaining
            buf = f.read(to_read)
            if not buf:
                break
            yield buf
            remaining -= len(buf)


@contextlib.contextmanager
def pin_cpu_if_requested():
    """Pin current process (or thread on some kernels) to one CPU if PFS_PIN_CPU is set.

    PFS_PIN_CPU="0" will pin to CPU 0. On Linux, this adjusts the calling task's affinity.
    """
    cpu_env = os.environ.get("PFS_PIN_CPU")
    if not cpu_env:
        yield
        return
    try:
        cpu = int(cpu_env)
    except Exception:
        # Ignore malformed values
        yield
        return
    try:
        cur = os.sched_getaffinity(0)
        os.sched_setaffinity(0, {cpu})
        try:
            yield
        finally:
            try:
                os.sched_setaffinity(0, cur)
            except Exception:
                pass
    except Exception:
        # Not supported or permission denied; continue without pinning
        yield