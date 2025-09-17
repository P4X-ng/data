#!/usr/bin/env python3
import argparse, json, time
import requests
from typing import List, Dict, Any

# This script posts a compute program to a provider endpoint.
# For kind=worker or edge_http, we expect a /compute endpoint that accepts {data_url, instructions}


def post_program(endpoint: str, data_url: str, instructions: List[Dict[str,Any]]):
    url = endpoint.rstrip('/') + '/compute'
    resp = requests.post(url, json={'data_url': data_url, 'instructions': instructions}, timeout=120)
    resp.raise_for_status()
    return resp.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', required=True, choices=['worker','edge_http'])
    ap.add_argument('--endpoint', required=True)
    ap.add_argument('--data-url', required=True)
    ap.add_argument('--instructions', required=True, help='JSON array of instructions [{op,imm?,offset?,length?}]')
    args = ap.parse_args()

    instr = json.loads(args.instructions)
    t0 = time.time()
    out = post_program(args.endpoint, args.data_url, instr)
    out['elapsed_sec'] = time.time() - t0
    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    main()