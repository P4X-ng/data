#!/usr/bin/env python3
"""WSGI entrypoint roughly equivalent to `msf-json-rpc.ru`.

This creates a small Flask `app` exposing a JSON-RPC style health endpoint and
executes a warmup check (calling the app via Flask's test client) to ensure the
app responds with the expected JSON before the module import completes. This
mirrors the Rack `warmup` behavior in the original Ruby file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from flask import Flask, jsonify, request

# Ensure project lib/ is on sys.path like the Ruby app does
root = Path(os.getenv('MSF_FRAMEWORK_PATH', '.')).resolve()
lib_path = root / 'lib'
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

try:
    import msfenv  # type: ignore
except Exception:
    msfenv = None  # type: ignore

app = Flask('msf-json-rpc')


@app.route('/api/v1/health', methods=['GET'])
def api_health():
    return jsonify(data={'status': 'UP'})


@app.route('/api/v1/json-rpc', methods=['POST'])
def json_rpc():
    payload = request.get_json(silent=True) or {}
    # The real app would dispatch JSON-RPC methods. This stub returns a
    # minimal error response for unknown methods and supports a simple
    # `core.version` method for compatibility tests.
    method = payload.get('method')
    req_id = payload.get('id')
    if method == 'core.version':
        return jsonify(jsonrpc='2.0', id=req_id, result={'version': 'python-stub', 'api': 2})
    return jsonify(jsonrpc='2.0', id=req_id, error={'code': -32601, 'message': 'Method not implemented'})


def _warmup_check():
    """Perform an internal test request to /api/v1/health to validate startup.

    Raises RuntimeError if the check fails.
    """
    with app.test_client() as c:
        resp = c.get('/api/v1/health')
        try:
            data = json.loads(resp.get_data(as_text=True) or '{}')
        except Exception as e:
            raise RuntimeError('Metasploit JSON RPC did not successfully start up (invalid JSON)') from e
        expected = {'data': {'status': 'UP'}}
        if data != expected:
            raise RuntimeError(f"Metasploit JSON RPC did not successfully start up. Unexpected response: {data}")


# Execute warmup on import to mimic the Ruby rack warmup block
_warmup_check()


if __name__ == '__main__':
    app.run(host=os.getenv('MSF_JSON_RPC_HOST', '127.0.0.1'), port=int(os.getenv('MSF_JSON_RPC_PORT', '8081')))
