#!/usr/bin/env python3
from app.tools.vpcpu.registry import _ensure_db

if __name__ == '__main__':
    _ensure_db()
    print('[vpcpu] db ready at var/vpcpu/assets.db')