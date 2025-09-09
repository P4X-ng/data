"""Minimal placeholder Flask web service used by msfdb.py.

Provides a token issuance endpoint and a simple status endpoint to mirror the
concept of the Metasploit web service while remaining intentionally tiny.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request

app = Flask(__name__)

TOKENS = {}


@app.post('/api/v1/json-rpc')
def json_rpc():  # Very small subset for compatibility with msfrpc.py login
    payload = request.get_json(force=True, silent=True) or {}
    method = payload.get('method')
    req_id = payload.get('id')
    params = payload.get('params') or {}
    if method == 'auth.login':
        user = params.get('username')
        pw = params.get('password')
        if user == os.getenv('MSFDB_WS_USER') and pw == os.getenv('MSFDB_WS_PASS'):
            token = secrets.token_hex(16)
            TOKENS[token] = True
            return jsonify(jsonrpc='2.0', id=req_id, result={'result': 'success', 'token': token})
        return jsonify(jsonrpc='2.0', id=req_id, error={'code': -32000, 'message': 'login failed'})
    if method == 'core.version':
        return jsonify(jsonrpc='2.0', id=req_id, result={'version': 'python-stub', 'api': 2})
    return jsonify(jsonrpc='2.0', id=req_id, error={'code': -32601, 'message': 'Method not implemented'})


@app.get('/status')
def status():
    return jsonify(status='ok', time=datetime.utcnow().isoformat())


def main():
    import argparse, ssl
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5443)
    args = parser.parse_args()
    use_ssl = os.getenv('MSFDB_SSL') == '1'
    cert = os.getenv('MSFDB_SSL_CERT')
    key = os.getenv('MSFDB_SSL_KEY')
    ctx: Optional[ssl.SSLContext] = None
    if use_ssl and cert and key and Path(cert).is_file() and Path(key).is_file():
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
    app.run(host=args.host, port=args.port, ssl_context=ctx)


if __name__ == '__main__':
    main()
