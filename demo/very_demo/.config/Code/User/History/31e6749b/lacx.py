"""
Safe Python stub for linux/local pkexec (metadata + non-destructive checks).
This file intentionally does NOT perform any privilege escalation. It only
implements harmless discovery and reporting to be used by the test harness.
"""
from msf_exploit import LocalExploit, CheckCode
import shutil
import subprocess
import re


class MetasploitModule(LocalExploit):
    """Non-destructive pkexec check stub."""

    def check(self):
        # Is pkexec present on PATH?
        pk = shutil.which("pkexec")
        if not pk:
            return CheckCode.Safe("pkexec not found on PATH")

        # Try to obtain a version string in a safe way.
        try:
            out = subprocess.check_output([pk, "--version"], stderr=subprocess.STDOUT, text=True, timeout=3)
            m = re.search(r"(\d+(?:\.\d+)+)", out)
            if m:
                ver = m.group(1)
                return CheckCode.Appears(f"pkexec found: {pk} (version {ver})")
        except Exception:
            # If we cannot obtain a version, still report that pkexec exists
            return CheckCode.Appears(f"pkexec found: {pk}")

        return CheckCode.Detected

    def exploit(self):
        # Intentionally do nothing; this is a safety-first stub.
        return None
