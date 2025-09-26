#!/usr/bin/env python3
"""
Virtual pCPU executor stub: simple wrapper to send instructions to a provider endpoint.
This will evolve into the vPCPU abstraction/scheduler integration.
"""
import requests, json, time
from typing import List, Dict, Any

class VPCPUExecutor:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint.rstrip('/')

    def compute(self, data_url: str, instructions: List[Dict[str, Any]]) -> Dict[str, Any]:
        t0 = time.time()
        resp = requests.post(self.endpoint + '/compute', json={
            'data_url': data_url,
            'instructions': instructions
        }, timeout=120)
        resp.raise_for_status()
        out = resp.json()
        out['elapsed_sec'] = time.time() - t0
        return out

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', default='http://localhost:5000')
    ap.add_argument('--path', required=True)
    ap.add_argument('--op', default='counteq')
    ap.add_argument('--imm', type=int, default=0)
    ap.add_argument('--offset', type=int, default=0)
    ap.add_argument('--length', type=int, default=1048576)
    args = ap.parse_args()

    exe = VPCPUExecutor(args.endpoint)
    data_url = 'file://' + args.path if not args.path.startswith('file://') else args.path
    out = exe.compute(data_url, [{'op': args.op, 'imm': args.imm, 'offset': args.offset, 'length': args.length}])
    print(json.dumps(out, indent=2))