#!/usr/bin/env python3
"""
Naive scheduler for Virtual pCPU assets.
Selects an asset by kind with the lowest expected latency and available concurrency.
"""
import random
from typing import List, Dict, Any
from dataclasses import asdict
from .registry import list_assets

# Simple scoring: prefer lower latency_ms (attrs.latency_ms), higher concurrency, matching region if provided

def pick_asset(kind: str, region: str | None = None) -> Dict[str, Any] | None:
    candidates = [asdict(a) if hasattr(a, '__dict__') else a for a in list_assets()]
    best = None
    best_score = None
    for a in candidates:
        if a['kind'] != kind:
            continue
        attrs = a['attrs']
        lat = float(attrs.get('latency_ms', 50.0))
        conc = int(attrs.get('concurrency', 4))
        score = lat - 0.1 * conc
        if region and attrs.get('region') == region:
            score -= 5.0
        if best is None or score < best_score:
            best = a
            best_score = score
    return best