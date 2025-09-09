"""
Safe Python stub for Dirty Pipe (CVE-2022-0847).
This stub performs environment checks and reports potential vulnerability
without attempting any unsafe writes or payload uploads.
"""
from msf_exploit import LocalExploit, CheckCode
import platform
import subprocess
import re


class MetasploitModule(LocalExploit):
    def check(self):
        # Check kernel version safely
        try:
            uname = platform.uname()
            release = uname.release
            # normalize leading version part
            m = re.match(r"(\d+\.\d+\.\d+)", release)
            if not m:
                return CheckCode.Unknown
            ver = tuple(int(x) for x in m.group(1).split('.'))
            # vulnerable between 5.8 and <5.16.11 (rough heuristic)
            if ver >= (5, 8, 0) and ver < (5, 16, 11):
                return CheckCode.Appears(f"Linux kernel looks vulnerable: {release}")
            return CheckCode.Safe(f"Linux kernel not in vulnerable range: {release}")
        except Exception:
            return CheckCode.Unknown

    def exploit(self):
        # Not implemented for safety.
        return None
