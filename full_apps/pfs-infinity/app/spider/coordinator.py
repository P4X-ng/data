from __future__ import annotations
import asyncio
import os
import time
import uuid
from collections import deque, defaultdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, HttpUrl, Field
import urllib.robotparser as robotparser

# Optional Redis backend
try:
    import redis.asyncio as aredis  # type: ignore
except Exception:
    aredis = None

router = APIRouter()

# Config
DEFAULT_UA = os.environ.get("SPIDER_UA", "pfs-spider")
LEASE_TTL_S = int(os.environ.get("SPIDER_LEASE_TTL_S", "120"))
IGNORE_ROBOTS = os.environ.get("SPIDER_IGNORE_ROBOTS", "0").lower() in ("1", "true", "yes")
REDIS_URL = os.environ.get("REDIS_URL")
SPIDER_SEED_MIN = int(os.environ.get("SPIDER_SEED_MIN", "0"))  # maintain at least this many items in queue if seeds file provided
SPIDER_SEEDS_FILE = os.environ.get("SPIDER_SEEDS_FILE", "")

# Redis keys
FRONTIER_KEY = os.environ.get("SPIDER_FRONTIER_KEY", "spider:frontier")
SCHEDULED_KEY = os.environ.get("SPIDER_SCHEDULED_KEY", "spider:scheduled")

_redis = None  # type: ignore

def _get_redis():
    global _redis
    if REDIS_URL and aredis is not None:
        if _redis is None:
            _redis = aredis.from_url(REDIS_URL)
        return _redis
    return None

# State
class PlanConfig(BaseModel):
    plan_id: str
    respect_robots: bool = True
    per_domain_concurrency: int = 4
    max_depth: int = 2
    allow: List[str] = []
    deny: List[str] = []

class QueueItem(BaseModel):
    url: str
    host: str
    depth: int
    plan_id: str

PLANS: Dict[str, PlanConfig] = {}
FRONTIER: deque[QueueItem] = deque()
VISITED: set[str] = set()
SCHEDULED: set[str] = set()
IN_FLIGHT_DOMAIN: Dict[str, int] = defaultdict(int)
LEASES: Dict[str, Dict] = {}
METRICS: Dict[str, int] = defaultdict(int)

ROBOTS_CACHE: Dict[str, Tuple[float, robotparser.RobotFileParser]] = {}
ROBOTS_TTL_S = 3600


class SpiderPlan(BaseModel):
    plan_version: str = Field("1.0.0", const=True)
    seeds: List[HttpUrl]
    allow: Optional[List[str]] = None
    deny: Optional[List[str]] = None
    respect_robots: bool = True
    per_domain_concurrency: int = 4
    max_depth: int = 2
    notes: Optional[List[str]] = None

class Lease(BaseModel):
    lease_id: str
    items: List[HttpUrl]
    ttl_s: int = LEASE_TTL_S

class ResultItem(BaseModel):
    url: HttpUrl
    status: int
    bytes: Optional[int] = None
    sha256: Optional[str] = None
    links: Optional[List[HttpUrl]] = None

class ResultSubmit(BaseModel):
    lease_id: str
    worker_id: str
    items: List[ResultItem]


def _norm_url(u: str) -> Optional[str]:
    try:
        p = urlparse(u)
        if p.scheme not in ("http", "https"):
            return None
        # normalize netloc (lowercase host)
        host = (p.hostname or "").lower()
        if not host:
            return None
        # Remove fragment; keep path/query
        p2 = p._replace(netloc=(host if p.port is None else f"{host}:{p.port}"), fragment="")
        return urlunparse(p2)
    except Exception:
        return None

async def _fetch_robots(host: str, scheme: str = "https") -> robotparser.RobotFileParser:
    now = time.time()
    key = host
    rp_cached = ROBOTS_CACHE.get(key)
    if rp_cached and now - rp_cached[0] < ROBOTS_TTL_S:
        return rp_cached[1]
    # Try https then http
    urls = [f"https://{host}/robots.txt", f"http://{host}/robots.txt"] if scheme == "https" else [f"http://{host}/robots.txt", f"https://{host}/robots.txt"]
    text = ""
    timeout = httpx.Timeout(3.0, connect=2.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for ru in urls:
            try:
                r = await client.get(ru)
                if r.status_code == 200 and len(r.text) < 1_000_000:
                    text = r.text
                    break
            except Exception:
                continue
    rp = robotparser.RobotFileParser()
    if text:
        rp.parse(text.splitlines())
    else:
        # If no robots, treat as allow-all
        rp.parse(["User-agent: *", "Allow: /"])
    ROBOTS_CACHE[key] = (now, rp)
    return rp


def _allowed_by_lists(host: str, allow: List[str], deny: List[str]) -> bool:
    ok = True
    if allow:
        ok = any(host.endswith(pat) for pat in allow)
    if deny and any(host.endswith(pat) for pat in deny):
        ok = False
    return ok


@router.post("/spider/plans")
async def create_plan(plan: SpiderPlan):
    plan_id = uuid.uuid4().hex[:12]
    cfg = PlanConfig(
        plan_id=plan_id,
        respect_robots=plan.respect_robots,
        per_domain_concurrency=max(1, int(plan.per_domain_concurrency)),
        max_depth=max(0, int(plan.max_depth)),
        allow=plan.allow or [],
        deny=plan.deny or [],
    )
    PLANS[plan_id] = cfg
    queued = 0
    r = _get_redis()
    to_push: List[bytes] = []
    for seed in plan.seeds:
        u = _norm_url(str(seed))
        if not u:
            continue
        host = urlparse(u).hostname or ""
        if not _allowed_by_lists(host, cfg.allow, cfg.deny):
            continue
        if u in VISITED or u in SCHEDULED:
            continue
        # Honor robots upfront (best-effort)
        if cfg.respect_robots and not IGNORE_ROBOTS:
            rp = await _fetch_robots(host, scheme=urlparse(u).scheme)
            if not rp.can_fetch(DEFAULT_UA, u):
                continue
        item = QueueItem(url=u, host=host, depth=0, plan_id=plan_id)
        FRONTIER.append(item)
        SCHEDULED.add(u)
        queued += 1
        if r is not None:
            try:
                import json as _json
                to_push.append(_json.dumps(item.dict()).encode("utf-8"))
            except Exception:
                pass
    if queued and r is not None and to_push:
        # push to Redis frontier (LPUSH preserves order reversed; OK for queue fill)
        try:
            await r.lpush(FRONTIER_KEY, *to_push)
            # also register in scheduled set for dedupe
            for seed in plan.seeds:
                u = _norm_url(str(seed))
                if u:
                    try:
                        await r.sadd(SCHEDULED_KEY, u)
                    except Exception:
                        pass
        except Exception:
            pass
    METRICS["plans_created"] += 1
    METRICS["urls_queued"] += queued
    return {"plan_id": plan_id, "queued": queued}


@router.get("/spider/lease", response_model=Lease)
async def get_lease(worker_id: str = Query(...), n: int = Query(10, ge=1, le=500), ua: str = Query(DEFAULT_UA)):
    if n <= 0:
        return {"lease_id": uuid.uuid4().hex[:8], "items": [], "ttl_s": LEASE_TTL_S}
    items: List[str] = []
    domains_count: Dict[str, int] = defaultdict(int)
    pulled: List[QueueItem] = []

    r = _get_redis()
    if r is not None:
        # Try to pop from Redis while preserving gating; requeue non-eligible
        import json as _json
        requeue_buf: List[bytes] = []
        tries = n * 6  # pop a bit more to satisfy gating
        while len(items) < n and tries > 0:
            tries -= 1
            val = await r.rpop(FRONTIER_KEY)
            if not val:
                break
            try:
                obj = _json.loads(val)
                qi = QueueItem(**obj)
            except Exception:
                # corrupted entry; skip
                continue
            cfg = PLANS.get(qi.plan_id)
            if not cfg:
                continue
            current = IN_FLIGHT_DOMAIN[qi.host]
            if domains_count[qi.host] + current >= cfg.per_domain_concurrency:
                requeue_buf.append(val)
                continue
            if cfg.respect_robots and not IGNORE_ROBOTS:
                rp = await _fetch_robots(qi.host, scheme=urlparse(qi.url).scheme)
                if not rp.can_fetch(ua, qi.url):
                    # drop silently
                    continue
            items.append(qi.url)
            pulled.append(qi)
            domains_count[qi.host] += 1
        if requeue_buf:
            # push back non-eligible items to preserve overall order fairness
            await r.lpush(FRONTIER_KEY, *requeue_buf)
    else:
        # In-memory frontier path
        tries = min(len(FRONTIER), n * 4)
        while len(items) < n and tries > 0 and FRONTIER:
            qi = FRONTIER.popleft()
            tries -= 1
            cfg = PLANS.get(qi.plan_id)
            if not cfg:
                continue
            current = IN_FLIGHT_DOMAIN[qi.host]
            if domains_count[qi.host] + current >= cfg.per_domain_concurrency:
                FRONTIER.append(qi)
                continue
            if cfg.respect_robots and not IGNORE_ROBOTS:
                rp = await _fetch_robots(qi.host, scheme=urlparse(qi.url).scheme)
                if not rp.can_fetch(ua, qi.url):
                    continue
            items.append(qi.url)
            pulled.append(qi)
            domains_count[qi.host] += 1

    # Register lease
    lease_id = uuid.uuid4().hex[:8]
    now = time.time()
    LEASES[lease_id] = {
        "worker_id": worker_id,
        "items": pulled,
        "expires": now + LEASE_TTL_S,
    }
    for qi in pulled:
        IN_FLIGHT_DOMAIN[qi.host] += 1
    METRICS["leases_issued"] += 1
    return {"lease_id": lease_id, "items": items, "ttl_s": LEASE_TTL_S}


@router.post("/spider/result")
async def submit_result(payload: ResultSubmit):
    lease = LEASES.get(payload.lease_id)
    if not lease:
        raise HTTPException(status_code=404, detail="unknown lease")
    # Decrement in-flight and process results
    pulled: List[QueueItem] = lease.get("items", [])
    by_url = {qi.url: qi for qi in pulled}
    r = _get_redis()
    to_push: List[bytes] = []
    for item in payload.items:
        u = _norm_url(str(item.url))
        if not u:
            continue
        qi = by_url.get(u)
        if qi:
            IN_FLIGHT_DOMAIN[qi.host] = max(0, IN_FLIGHT_DOMAIN[qi.host] - 1)
            VISITED.add(u)
        METRICS["urls_fetched"] += 1
        if item.status == 200 and item.links and qi:
            cfg = PLANS.get(qi.plan_id)
            if cfg and qi.depth < cfg.max_depth:
                new_depth = qi.depth + 1
                for L in item.links:
                    nu = _norm_url(str(L))
                    if not nu:
                        continue
                    host = urlparse(nu).hostname or ""
                    if not _allowed_by_lists(host, cfg.allow, cfg.deny):
                        continue
                    if nu in VISITED or nu in SCHEDULED:
                        continue
                    # Honor robots before enqueue
                    if cfg.respect_robots and not IGNORE_ROBOTS:
                        rp = await _fetch_robots(host, scheme=urlparse(nu).scheme)
                        if not rp.can_fetch(DEFAULT_UA, nu):
                            continue
                    qitem = QueueItem(url=nu, host=host, depth=new_depth, plan_id=qi.plan_id)
                    FRONTIER.append(qitem)
                    SCHEDULED.add(nu)
                    METRICS["urls_queued"] += 1
                    if r is not None:
                        try:
                            import json as _json
                            to_push.append(_json.dumps(qitem.dict()).encode("utf-8"))
                        except Exception:
                            pass
    if r is not None and to_push:
        try:
            await r.lpush(FRONTIER_KEY, *to_push)
            for item in payload.items:
                u = _norm_url(str(item.url))
                if u:
                    await r.sadd(SCHEDULED_KEY, u)
        except Exception:
            pass
    # Lease consumed
    LEASES.pop(payload.lease_id, None)
    METRICS["leases_completed"] += 1
    return {"status": "ok"}


@router.get("/spider/metrics")
async def spider_metrics():
    qlen = len(FRONTIER)
    r = _get_redis()
    if r is not None:
        try:
            qlen = int(await r.llen(FRONTIER_KEY))
        except Exception:
            pass
    return {
        "frontier": qlen,
        "visited": len(VISITED),
        "scheduled": len(SCHEDULED),
        "in_flight_domains": dict(IN_FLIGHT_DOMAIN),
        "leases": len(LEASES),
        "metrics": dict(METRICS),
    }

# Background seeder attachment
def attach_to_app(app):
    if SPIDER_SEED_MIN <= 0:
        return
    seeds_path = SPIDER_SEEDS_FILE
    if not seeds_path or not os.path.isfile(seeds_path):
        return
    r = _get_redis()
    if r is None:
        return

    async def _seeder():
        import json as _json
        # load seeds file once
        try:
            with open(seeds_path, "r", encoding="utf-8") as f:
                seeds = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except Exception:
            return
        idx = 0
        while True:
            try:
                qlen = int(await r.llen(FRONTIER_KEY))
                if qlen < SPIDER_SEED_MIN and seeds:
                    # push up to delta seeds
                    delta = SPIDER_SEED_MIN - qlen
                    batch: List[bytes] = []
                    for _ in range(min(delta, 1000)):
                        u = _norm_url(seeds[idx % len(seeds)])
                        idx += 1
                        if not u:
                            continue
                        host = urlparse(u).hostname or ""
                        item = QueueItem(url=u, host=host, depth=0, plan_id=PLANS[next(iter(PLANS))].plan_id if PLANS else "plan")
                        batch.append(_json.dumps(item.dict()).encode("utf-8"))
                    if batch:
                        await r.lpush(FRONTIER_KEY, *batch)
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2.0)

    task = asyncio.create_task(_seeder())
    if not hasattr(app.state, "_spider_tasks"):
        app.state._spider_tasks = []
    app.state._spider_tasks.append(task)

    @app.on_event("shutdown")
    async def _stop_seeder():
        try:
            for t in getattr(app.state, "_spider_tasks", []):
                t.cancel()
        except Exception:
            pass
