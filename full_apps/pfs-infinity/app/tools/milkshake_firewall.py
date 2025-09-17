#!/usr/bin/env python3
"""
IDrinkYourMILKSHAKE - Firewall compute harness (local nftables variant)
- Sets up a counter on UDP dst port
- Sends probes (or let external traffic drive it)
- Reads packet/byte counters as the "result"

This demonstrates the idea that even passive systems (firewalls) produce observable
state transitions that we can use as a compute signal.
"""

import subprocess
import time
from dataclasses import dataclass
from typing import Optional

SCRIPTS_DIR = 'scripts/milkshake'

@dataclass
class MilkshakeResult:
    port: int
    packets: int
    bytes: int
    elapsed_s: float


def sh(cmd: list[str]) -> str:
    out = subprocess.check_output(cmd, text=True)
    return out.strip()


def nft_setup(port: int) -> None:
    sh(['bash', f'{SCRIPTS_DIR}/nft_setup.sh', str(port)])


def nft_read(port: int) -> tuple[int, int]:
    out = sh(['bash', f'{SCRIPTS_DIR}/nft_read.sh', str(port)])
    if not out:
        return (0, 0)
    parts = out.split()
    return (int(parts[0]), int(parts[1]))


def nft_reset(port: int) -> None:
    sh(['bash', f'{SCRIPTS_DIR}/nft_reset.sh', str(port)])


def run_probe(host: str, port: int, pps: int, seconds: int, payload: str = '') -> int:
    out = sh(['python3', f'{SCRIPTS_DIR}/udp_probe.py', '--host', host, '--port', str(port), '--pps', str(pps), '--seconds', str(seconds), '--payload', payload])
    if out.startswith('sent='):
        return int(out.split('=')[1])
    return 0


def milkshake(port: int, seconds: int = 1, host: str = '127.0.0.1', pps: int = 5000, payload: str = '') -> MilkshakeResult:
    nft_setup(port)
    nft_reset(port)
    t0 = time.time()
    sent = run_probe(host, port, pps, seconds, payload)
    # small wait to ensure counters updated
    time.sleep(0.05)
    pk, by = nft_read(port)
    elapsed = time.time() - t0
    return MilkshakeResult(port=port, packets=pk, bytes=by, elapsed_s=elapsed)

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--seconds', type=int, default=1)
    ap.add_argument('--pps', type=int, default=5000)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--payload', default='')
    args = ap.parse_args()

    r = milkshake(args.port, seconds=args.seconds, host=args.host, pps=args.pps, payload=args.payload)
    print(f"port={r.port} packets={r.packets} bytes={r.bytes} elapsed_s={r.elapsed_s:.3f}")