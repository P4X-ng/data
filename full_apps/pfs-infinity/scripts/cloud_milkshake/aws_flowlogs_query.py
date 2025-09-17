#!/usr/bin/env python3
"""
IDrinkYourMILKSHAKE (Cloud) — Query VPC Flow Logs via CloudWatch Logs Insights

Requires:
- VPC Flow Logs delivered to a CloudWatch Logs log group
- AWS credentials (env or default profile)

Example:
  python scripts/cloud_milkshake/aws_flowlogs_query.py \
    --log-group /aws/vpc/flow-logs/my-vpc \
    --interface-id eni-0123456789abcdef0 \
    --dstport 51999 --protocol 17 --minutes 5
"""

import argparse
import boto3
import json
import sys
import time
from datetime import datetime, timedelta, timezone

FIELDS = [
    'version','account_id','interface_id','srcaddr','dstaddr','srcport','dstport',
    'protocol','packets','bytes','start','end','action','log_status'
]

QUERY_TEMPLATE = """
fields @timestamp, @message
| parse @message "* * * * * * * * * * * * * * * *" as {fields}
{filters}
| stats sum(packets) as packets, sum(bytes) as bytes, count(*) as records by action
| sort action desc
"""


def build_filters(args) -> str:
    conds = []
    if args.interface_id:
        conds.append(f"| filter interface_id = '{args.interface_id}'")
    if args.srcaddr:
        conds.append(f"| filter srcaddr = '{args.srcaddr}'")
    if args.dstaddr:
        conds.append(f"| filter dstaddr = '{args.dstaddr}'")
    if args.dstport:
        conds.append(f"| filter dstport = {args.dstport}")
    if args.srcport:
        conds.append(f"| filter srcport = {args.srcport}")
    if args.protocol:
        conds.append(f"| filter protocol = {args.protocol}")
    if args.action:
        conds.append(f"| filter action = '{args.action}'")
    return "\n".join(conds)


def run_query(logs, log_group, query, start_ms, end_ms):
    q = logs.start_query(
        logGroupName=log_group,
        startTime=int(start_ms/1000),
        endTime=int(end_ms/1000),
        queryString=query,
        limit=1000,
    )
    qid = q['queryId']
    # Poll
    while True:
        resp = logs.get_query_results(queryId=qid)
        status = resp['status']
        if status in ('Complete','Failed','Cancelled','Timeout'):
            return resp
        time.sleep(1.0)


def results_to_json(resp):
    out = []
    for row in resp.get('results', []):
        item = {}
        for cell in row:
            item[cell['field']] = cell['value']
        out.append(item)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--log-group', required=True)
    ap.add_argument('--minutes', type=int, default=5)
    ap.add_argument('--interface-id')
    ap.add_argument('--srcaddr')
    ap.add_argument('--dstaddr')
    ap.add_argument('--srcport', type=int)
    ap.add_argument('--dstport', type=int)
    # protocol: 6 TCP, 17 UDP
    ap.add_argument('--protocol', type=int)
    ap.add_argument('--action', choices=['ACCEPT','REJECT'])
    ap.add_argument('--region')
    args = ap.parse_args()

    logs = boto3.client('logs', region_name=args.region) if args.region else boto3.client('logs')

    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=args.minutes)
    start_ms = int(start.timestamp()*1000)
    end_ms = int(end.timestamp()*1000)

    query = QUERY_TEMPLATE.format(
        fields=",".join(FIELDS),
        filters=build_filters(args)
    )

    resp = run_query(logs, args.log_group, query, start_ms, end_ms)
    data = {
        'status': resp.get('status'),
        'statistics': resp.get('statistics'),
        'results': results_to_json(resp),
        'window': {
            'start': start.isoformat(),
            'end': end.isoformat(),
            'minutes': args.minutes
        },
        'query': query
    }
    print(json.dumps(data, indent=2))

if __name__ == '__main__':
    main()