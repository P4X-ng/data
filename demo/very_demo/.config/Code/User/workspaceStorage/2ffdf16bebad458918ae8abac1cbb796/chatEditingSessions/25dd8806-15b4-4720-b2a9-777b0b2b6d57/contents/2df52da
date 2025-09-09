#!/usr/bin/env python3
"""Python approximation of `msfrpcd` (JSON-RPC focus only).

This does NOT expose Metasploit internals directly; instead it can:
  * Proxy JSON-RPC requests to an existing Metasploit JSON-RPC service
    (useful for adding TLS or simple token auth) OR
  * Provide a placeholder in environments where the Ruby service cannot run.

Modes:
  --proxy http://host:port/path   Forward all JSON-RPC calls to that upstream

Auth:
  * If --auth-user/--auth-pass are set, requires an auth.login call first.
  * On successful login returns a dummy token; future calls must include
    params.token matching it.

This is intentionally minimal and meant as a scaffolding helper when a Python
ecosystem wrapper is preferable.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import ssl
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import urllib.request


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog='msfrpcd.py', add_help=False,
                                description='Lightweight JSON-RPC proxy / stub for Metasploit')
    p.add_argument('-a', dest='address', default='0.0.0.0', help='Bind address (default 0.0.0.0)')
    p.add_argument('-p', dest='port', type=int, default=55553, help='Bind port (default 55553)')
    p.add_argument('-S', dest='no_ssl', action='store_true', help='Disable SSL')
    p.add_argument('--proxy', help='Upstream JSON-RPC base URL to proxy to (e.g. https://127.0.0.1:55553/api/v1/json-rpc)')
    p.add_argument('--auth-user', help='Static auth username (optional)')
    p.add_argument('--auth-pass', help='Static auth password (optional)')
    p.add_argument('--token-timeout', type=int, default=300, help='Token timeout seconds (unused placeholder)')
    p.add_argument('-h', '--help', action='help', help='Help banner')
    return p.parse_args(argv)


class JsonRpcProxyHandler(BaseHTTPRequestHandler):
    server_version = 'msfrpcd.py/0.1'

    def _send(self, code=200, payload=None):
        body = json.dumps(payload or {}).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quieter
        sys.stderr.write("[rpcd] " + fmt % args + "\n")

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get('Content-Length', '0'))
        data = self.rfile.read(length)
        try:
            req = json.loads(data.decode('utf-8', errors='ignore'))
        except json.JSONDecodeError:
            self._send(HTTPStatus.BAD_REQUEST, {'error': 'invalid JSON'})
            return
        if req.get('jsonrpc') != '2.0':
            self._send(HTTPStatus.BAD_REQUEST, {'error': 'invalid jsonrpc version'})
            return
        method = req.get('method')
        params = req.get('params') or {}
        req_id = req.get('id')

        # Auth handling
        if method == 'auth.login':
            if self.server.auth_user is None:
                token = secrets.token_hex(16)
                self.server.sessions[token] = True
                self._send(200, {'jsonrpc': '2.0', 'id': req_id, 'result': {'result': 'success', 'token': token}})
                return
            if params.get('username') == self.server.auth_user and params.get('password') == self.server.auth_pass:
                token = secrets.token_hex(16)
                self.server.sessions[token] = True
                self._send(200, {'jsonrpc': '2.0', 'id': req_id, 'result': {'result': 'success', 'token': token}})
            else:
                self._send(200, {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32000, 'message': 'login failed'}})
            return

        # Token validation (if any auth configured)
        if self.server.auth_user is not None:
            token = params.get('token')
            if token not in self.server.sessions:
                self._send(200, {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32001, 'message': 'invalid token'}})
                return

        # Proxy mode
        if self.server.proxy_url:
            payload = json.dumps(req).encode('utf-8')
            upstream_req = urllib.request.Request(self.server.proxy_url, data=payload, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(upstream_req, context=self.server.ssl_ctx if self.server.ssl_ctx else None, timeout=120) as resp:
                    upstream_body = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() == 'content-length':
                        continue
                    self.send_header(k, v)
                self.send_header('Content-Length', str(len(upstream_body)))
                self.end_headers()
                self.wfile.write(upstream_body)
            except Exception as e:  # noqa: BLE001
                self._send(500, {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32099, 'message': f'upstream error: {e}'}})
            return

        # Stub fallback implementations
        if method == 'core.version':
            self._send(200, {'jsonrpc': '2.0', 'id': req_id, 'result': {'version': 'stub', 'ruby': False, 'api': 2}})
            return
        self._send(200, {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': -32601, 'message': f'Method {method} not implemented in stub'}})


class RpcServer(HTTPServer):
    def __init__(self, server_address, handler_cls, proxy_url=None, auth_user=None, auth_pass=None, ssl_ctx=None):
        super().__init__(server_address, handler_cls)
        self.proxy_url = proxy_url
        self.auth_user = auth_user
        self.auth_pass = auth_pass
        self.sessions = {}
        self.ssl_ctx = ssl_ctx


def main():
    args = parse_args()
    ssl_ctx = None
    if not args.no_ssl:
        import ssl as _ssl
        ssl_ctx = _ssl.create_default_context(_ssl.Purpose.CLIENT_AUTH)
        cert_path = os.getenv('MSF_SSL_CERT')
        key_path = os.getenv('MSF_SSL_KEY')
        if not (cert_path and key_path and os.path.isfile(cert_path) and os.path.isfile(key_path)):
            # generate ad-hoc
            try:
                from cryptography import x509
                from cryptography.x509.oid import NameOID
                from cryptography.hazmat.primitives import hashes, serialization
                from cryptography.hazmat.primitives.asymmetric import rsa
                import datetime, hashlib
                key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u'msfrpcd.py')])
                now = datetime.datetime.utcnow()
                cert_obj = (x509.CertificateBuilder()
                            .subject_name(subject)
                            .issuer_name(subject)
                            .public_key(key_obj.public_key())
                            .serial_number(int.from_bytes(hashlib.sha256(os.urandom(16)).digest()[:16], 'big'))
                            .not_valid_before(now)
                            .not_valid_after(now + datetime.timedelta(days=2))
                            .sign(key_obj, hashes.SHA256()))
                import tempfile
                tmp = tempfile.mkdtemp(prefix='msfrpcd-')
                cert_path = os.path.join(tmp, 'cert.pem')
                key_path = os.path.join(tmp, 'key.pem')
                with open(cert_path, 'wb') as f:
                    f.write(cert_obj.public_bytes(serialization.Encoding.PEM))
                with open(key_path, 'wb') as f:
                    f.write(key_obj.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
            except Exception as e:  # noqa: BLE001
                print(f"[-] Failed to generate self-signed cert: {e}", file=sys.stderr)
                sys.exit(2)
        ssl_ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)

    server = RpcServer((args.address, args.port), JsonRpcProxyHandler, proxy_url=args.proxy, auth_user=args.auth_user, auth_pass=args.auth_pass, ssl_ctx=ssl_ctx)
    print(f"[*] JSON-RPC stub/proxy listening on {args.address}:{args.port} SSL={'no' if args.no_ssl else 'yes'} proxy={'none' if not args.proxy else args.proxy}")
    try:
        if ssl_ctx:
            server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down")
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
