#!/usr/bin/env python3
from app.tools.vpcpu.registry import list_assets

if __name__ == '__main__':
    for a in list_assets():
        print(f"- {a.name} [{a.kind}] {a.endpoint} attrs={a.attrs}")