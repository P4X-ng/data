#!/usr/bin/env python3
"""
IDrinkYourMILKSHAKE (Cloud) — Multi-port "word" program via VPC Flow Logs

Encode a bit-vector by sending UDP packets to base_port..base_port+N-1 on a target.
Then query CloudWatch Logs (VPC Flow Logs) for dstport counts and decode the word.

Usage (example):
  /home/punk/.venv/bin/python scripts/cloud_milkshake/milkshake_aws_word.py \
    --target-ip 203.0.113.10 --bits 16 --base-port 52000 --pps 2000 --seconds 2 \
    --log-group /aws/vpc/flow-logs/my-vpc --interface-id eni-0123456789abcdef0 --region us-east-1 \
    --pattern 0b1011001110001111

Note: Flow Logs are near-real-time; allow 30-120s for logs to appear.
"""

import argparse, socket, time, json
import boto3
from datetime import datetime, timedelta, timezone


def send_pattern(target_ip: str, base_port: int, bits: int, pattern: int, pps: int, seconds: int, payload: bytes = b''):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    interval = 1.0 / max(1, pps)
    end = time.time() + seconds
    sent = 0
    ports = [base_port + i for i in range(bits) if ((pattern >> i) & 1) == 1]
    if not ports:
        return 0
    pi = 0
    while time.time() < end:
        port = ports[pi]
        sock.sendto(payload, (target_ip, port))
        sent += 1
        pi += 1
        if pi >= len(ports):
            pi = 0
        if interval > 0:
            time.sleep(interval)
    return sent


def query_flow_logs(log_group: str, eni: str, ports: list[int], minutes: int, region: str | None):
    logs = boto3.client('logs', region_name=region) if region else boto3.client('logs')
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)

    # Logs Insights query that parses the default flow log format
    fields = ','.join(['version','account_id','interface_id','srcaddr','dstaddr','srcport','dstport','protocol','packets','bytes','start','end','action','log_status'])
    filters = [f"| filter interface_id = '{eni}'", "| filter protocol = 17"]
    if ports:
        ports_list = ','.join(str(p) for p in ports)
        filters.append(f"| filter dstport in [{ports_list}]")

    query = f"""
fields @timestamp, @message
| parse @message "* * * * * * * * * * * * * * * *" as {fields}
{chr(10).join(filters)}
| stats sum(packets) as packets, sum(bytes) as bytes by dstport, action
| sort dstport asc
"""
    q = logs.start_query(
        logGroupName=log_group,
        startTime=int(start.timestamp()),
        endTime=int(end.timestamp()),
        queryString=query,
        limit=1000,
    )
    qid = q['queryId']
    # poll
    while True:
        resp = logs.get_query_results(queryId=qid)
        status = resp['status']
        if status in ('Complete','Failed','Cancelled','Timeout'):
            break
        time.sleep(1)

    counts: dict[int, dict[str,int]] = {}
    for row in resp.get('results', []):
        rec = {c['field']: c['value'] for c in row}
        try:
            dp = int(rec.get('dstport'))
            pk = int(rec.get('packets'))
            by = int(rec.get('bytes'))
            act = rec.get('action','')
        except Exception:
            continue
        counts.setdefault(dp, {}).setdefault(act, 0)
        counts[dp][act] += pk
    return counts, query


def decode_bits(base_port: int, bits: int, counts: dict[int, dict[str,int]], prefer_action: str | None = None, threshold: int = 1):
    value = 0
    for i in range(bits):
        port = base_port + i
        c = counts.get(port, {})
        pk = 0
        if prefer_action and prefer_action in c:
            pk = c[prefer_action]
        else:
            # sum all actions
            pk = sum(c.values())
        if pk >= threshold:
            value |= (1 << i)
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target-ip', required=True)
    ap.add_argument('--base-port', type=int, required=True)
    ap.add_argument('--bits', type=int, default=16)
    ap.add_argument('--pattern', help='integer (e.g., 0b1011 or decimal)', required=True)
    ap.add_argument('--pps', type=int, default=2000)
    ap.add_argument('--seconds', type=int, default=2)
    ap.add_argument('--payload', default='')
    ap.add_argument('--log-group', required=True)
    ap.add_argument('--interface-id', required=True)
    ap.add_argument('--minutes', type=int, default=5)
    ap.add_argument('--region')
    ap.add_argument('--prefer-action', choices=['ACCEPT','REJECT'])
    ap.add_argument('--threshold', type=int, default=1)
    args = ap.parse_args()

    pattern_int = int(args.pattern, 0) if isinstance(args.pattern, str) else int(args.pattern)

    sent = send_pattern(args.target_ip, args.base_port, args.bits, pattern_int, args.pps, args.seconds, args.payload.encode())
    # Allow some time for Flow Logs delivery
    time.sleep(20)

    ports = [args.base_port + i for i in range(args.bits)]
    counts, q = query_flow_logs(args.log_group, args.interface_id, ports, args.minutes, args.region)
    decoded = decode_bits(args.base_port, args.bits, counts, args.prefer_action, args.threshold)

    out = {
        'sent_datagrams': sent,
        'base_port': args.base_port,
        'bits': args.bits,
        'pattern': pattern_int,
        'decoded': decoded,
        'match': decoded == pattern_int,
        'counts': counts,
        'logs_query': q
    }
    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    main()