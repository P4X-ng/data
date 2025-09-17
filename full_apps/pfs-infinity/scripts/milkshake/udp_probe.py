#!/usr/bin/env python3
import socket
import time
import argparse

parser = argparse.ArgumentParser(description='UDP probe to drive nft counter')
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', type=int, required=True)
parser.add_argument('--pps', type=int, default=1000)
parser.add_argument('--seconds', type=int, default=2)
parser.add_argument('--payload', default='')
args = parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

payload = args.payload.encode()
interval = 1.0 / max(1, args.pps)
end = time.time() + args.seconds
sent = 0

while time.time() < end:
    sock.sendto(payload, (args.host, args.port))
    sent += 1
    if interval > 0:
        time.sleep(interval)

print(f"sent={sent}")