#!/usr/bin/env python3
import argparse, json
from app.tools.vpcpu.registry import add_asset, Asset

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--kind', required=True, choices=['worker','edge_http','nft_local','aws_flowlogs'])
    ap.add_argument('--endpoint', required=True)
    ap.add_argument('--attrs', default='{}', help='JSON of attributes (latency_ms, region, concurrency, etc)')
    args = ap.parse_args()

    attrs = json.loads(args.attrs)
    asset = Asset(name=args.name, kind=args.kind, endpoint=args.endpoint, attrs=attrs)
    asset_id = add_asset(asset)
    print(f'added asset id={asset_id} name={args.name} kind={args.kind} endpoint={args.endpoint}')

if __name__ == '__main__':
    main()