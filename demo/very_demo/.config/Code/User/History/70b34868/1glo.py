#!/usr/bin/env python3
"""Example local exploit module (Python port/demo).

This is a small demonstration module written against `msf_exploit.LocalExploit`.
It implements `check()` and `exploit()` with harmless, illustrative behavior.
"""
from __future__ import annotations

import os
import time
import sys
from pathlib import Path
# Ensure project root is importable when run directly
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from msf_exploit import LocalExploit


class ExamplePrivEsc(LocalExploit):
    NAME = "Example Local PrivEsc"
    DESCRIPTION = "Demo local exploit that simulates privilege escalation steps"
    AUTHOR = ["example"]

    def check(self):
        # Simple, harmless check: does /etc/passwd exist and is world-readable?
        path = '/etc/passwd'
        if os.path.exists(path) and os.access(path, os.R_OK):
            return self.CheckCode.APPEARS(f"{path} exists and is readable")
        return self.CheckCode.SAFE(f"{path} not present or not readable")

    def exploit(self):
        self.log('Starting example exploit flow...')
        # Simulate some local steps
        for i in range(3):
            self.status(f'Step {i+1}/3: performing harmless action')
            time.sleep(0.1)
        # Indicate success
        self.success('Example exploit completed successfully (no real action taken)')


if __name__ == '__main__':
    ExamplePrivEsc().run_simple()
