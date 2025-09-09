#!/usr/bin/env python3
"""Python rewrite of `msfrpc` client (simplified).

Supports connecting to the Metasploit JSON-RPC (preferred) or MSGRPC (legacy)
endpoint. The Ruby original provides an IRB shell with a bound `rpc` object;
here we offer a minimal interactive shell where you can type JSON-RPC method
names or raw group.command (legacy) forms.

Usage examples:
  JSON-RPC (default path /api/v1/json-rpc):
    ./msfrpc.py -a 127.0.0.1 -P password -U msf

  Legacy MSGRPC (expects msgpack over TCP): NOT implemented; we fallback to
  JSON-RPC only in this Python version unless --legacy is provided, in which
  case we abort with a message.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import readline  # noqa: F401 (line editing)
import ssl
import sys
import urllib.request


class RpcError(Exception):
    pass


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog='msfrpc.py', add_help=False,
                                description='Metasploit JSON-RPC interactive client (Python)')
    p.add_argument('-a', dest='host', required=True, help='Connect to this IP address')
    p.add_argument('-p', dest='port', type=int, default=55553, help='Connect to this port (default 55553)')
    p.add_argument('-U', dest='username', default='msf', help='Username (default msf)')
    p.add_argument('-P', dest='password', help='Password (will prompt if omitted)')
    p.add_argument('-S', dest='no_ssl', action='store_true', help='Disable SSL')
    p.add_argument('--path', dest='path', default='/api/v1/json-rpc', help='JSON-RPC path (default /api/v1/json-rpc)')
    p.add_argument('--legacy', action='store_true', help='(Placeholder) connect via legacy MSGRPC (unsupported)')
    p.add_argument('-h', '--help', action='help', help='Help banner')
    return p.parse_args(argv)


class JsonRpcClient:
    def __init__(self, base_url: str, token: str | None = None, insecure: bool = True):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.insecure = insecure
        if insecure:
            self._ctx = ssl._create_unverified_context()
        else:
            self._ctx = ssl.create_default_context()
        self._id = 0

    def call(self, method: str, **params):
        self._id += 1
        body = {
            'jsonrpc': '2.0',
            'method': method,
            'id': self._id,
            'params': params
        }
        if self.token:
            body['params']['token'] = self.token
        data = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(self.base_url, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=60) as resp:
                resp_body = resp.read().decode('utf-8', errors='ignore')
        except Exception as e:  # noqa: BLE001
            raise RpcError(f"Transport error: {e}") from e
        try:
            payload = json.loads(resp_body)
        except json.JSONDecodeError:
            raise RpcError(f'Non-JSON response: {resp_body[:200]}')
        if 'error' in payload:
            raise RpcError(payload['error'])
        return payload.get('result')


def login(client: JsonRpcClient, username: str, password: str) -> str:
    # Metasploit JSON-RPC login method `auth.login` typically returns {'result': 'success', 'token': '...'}
    res = client.call('auth.login', username=username, password=password)
    if not res or 'token' not in res:
        raise RpcError(f'Unexpected login response: {res}')
    return res['token']


def repl(client: JsonRpcClient):
    print("[*] Enter JSON-RPC method names (e.g., 'core.version'). Ctrl-D to exit.")
    while True:
        try:
            line = input('rpc> ').strip()
        except EOFError:
            print()
            break
        if not line:
            continue
        if line in {'exit', 'quit'}:
            break
        method, *param_tokens = line.split()
        params = {}
        for tok in param_tokens:
            if '=' in tok:
                k, v = tok.split('=', 1)
                # attempt json parse for value types
                try:
                    v = json.loads(v)
                except Exception:  # noqa: BLE001
                    pass
                params[k] = v
        try:
            result = client.call(method, **params)
            print(json.dumps(result, indent=2, sort_keys=True))
        except RpcError as e:
            print(f"[error] {e}")


def main():
    args = parse_args()
    if args.legacy:
        print('[!] Legacy MSGRPC protocol not implemented in this Python version.', file=sys.stderr)
        sys.exit(1)
    if not args.password:
        args.password = getpass.getpass('Password: ')
    scheme = 'http' if args.no_ssl else 'https'
    base_url = f"{scheme}://{args.host}:{args.port}{args.path}"
    client = JsonRpcClient(base_url)
    print(f"[*] Connecting to {base_url}")
    try:
        token = login(client, args.username, args.password)
    except RpcError as e:
        print(f"[-] Login failed: {e}", file=sys.stderr)
        sys.exit(2)
    client.token = token
    print('[*] Login OK; token stored (automatically added to subsequent calls)')
    repl(client)


if __name__ == '__main__':
    main()
