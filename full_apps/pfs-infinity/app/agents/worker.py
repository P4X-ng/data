from __future__ import annotations
import asyncio
import os
import socket
import sys
import time
import hashlib
from typing import List
from urllib.parse import urlparse, urljoin

import httpx
from html.parser import HTMLParser

COORD_URL = os.environ.get("COORD_URL", "http://127.0.0.1:8811")
WORKER_ID = os.environ.get("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")
LEASE_N = int(os.environ.get("SPIDER_LEASE_N", "25"))
UA = os.environ.get("SPIDER_UA", "pfs-spider")
IGNORE_ROBOTS = os.environ.get("SPIDER_IGNORE_ROBOTS", "0").lower() in ("1", "true", "yes")

class LinkParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links: List[str] = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            href = dict(attrs).get('href')
            if href:
                try:
                    self.links.append(urljoin(self.base_url, href))
                except Exception:
                    pass

async def fetch_one(client: httpx.AsyncClient, url: str) -> dict:
    try:
        r = await client.get(url, headers={"User-Agent": UA})
        content = r.content or b""
        sha = hashlib.sha256(content).hexdigest() if content else None
        links: List[str] = []
        ct = r.headers.get("content-type", "").lower()
        if r.status_code == 200 and "text/html" in ct and content:
            try:
                p = LinkParser(url)
                p.feed(content.decode(errors="ignore"))
                links = p.links[:200]
            except Exception:
                links = []
        return {"url": url, "status": r.status_code, "bytes": len(content), "sha256": sha, "links": links}
    except Exception:
        return {"url": url, "status": 0, "bytes": 0, "sha256": None, "links": []}

async def main():
    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        while True:
            try:
                # Lease
                params = {"worker_id": WORKER_ID, "n": str(LEASE_N), "ua": UA}
                r = await client.get(f"{COORD_URL}/spider/lease", params=params)
                if r.status_code != 200:
                    await asyncio.sleep(1.0)
                    continue
                lease = r.json()
                lease_id = lease.get("lease_id")
                urls = lease.get("items", [])
                if not urls:
                    await asyncio.sleep(0.5)
                    continue
                # Fetch
                results = await asyncio.gather(*[fetch_one(client, u) for u in urls])
                payload = {"lease_id": lease_id, "worker_id": WORKER_ID, "items": results}
                r2 = await client.post(f"{COORD_URL}/spider/result", json=payload)
                if r2.status_code != 200:
                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(0.05)
            except KeyboardInterrupt:
                break
            except Exception:
                await asyncio.sleep(1.0)

if __name__ == "__main__":
    asyncio.run(main())