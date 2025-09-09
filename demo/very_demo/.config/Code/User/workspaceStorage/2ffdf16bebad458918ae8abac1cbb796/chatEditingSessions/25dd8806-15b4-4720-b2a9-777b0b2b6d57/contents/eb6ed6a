#!/usr/bin/env python3
"""WSGI entrypoint roughly equivalent to `msf-ws.ru`.

Provides a tiny Flask `app` that stands in for `Msf::WebServices::MetasploitApiApp`.
This is a pragmatic Python replacement suitable for running with a WSGI server
such as gunicorn or the Flask development server.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from flask import Flask, jsonify

# Ensure project lib/ is on sys.path to match Ruby's $LOAD_PATH behavior
root = Path(os.getenv('MSF_FRAMEWORK_PATH', '.')).resolve()
lib_path = root / 'lib'
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

# In Rubies `msfenv` sets up environment; here we keep it optional.
try:
    import msfenv  # type: ignore
except Exception:
    # msfenv is optional in this Python shim; proceed anyway
    msfenv = None  # type: ignore

app = Flask('msf-ws')


@app.route('/')
def index():
    return jsonify(message='msf-ws (Python stub)'), 200


@app.route('/api/v1/health')
def health():
    return jsonify(data={'status': 'UP'}), 200


if __name__ == '__main__':
    # Allow running directly for quick smoke tests
    app.run(host=os.getenv('MSF_WS_HOST', '127.0.0.1'), port=int(os.getenv('MSF_WS_PORT', '8080')))
