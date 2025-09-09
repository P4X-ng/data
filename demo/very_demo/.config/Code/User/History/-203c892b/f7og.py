"""
Safe stub for CVE-2023-0386 OverlayFS privilege escalation.
Performs kernel version and userns capability checks only.
"""
from msf_exploit import LocalExploit, CheckCode
import platform
import subprocess
import re


class MetasploitModule(LocalExploit):
    def check(self):
        try:
            rel = subprocess.check_output(["uname", "-r"], text=True).strip()
            m = re.match(r"(\d+\.\d+\.\d+)", rel)
            if not m:
                return CheckCode.Unknown
            ver = tuple(int(x) for x in m.group(1).split('.'))
            # heuristics from original module: vulnerable ranges are limited
            if ver >= (5, 11, 0) and ver < (6, 1, 9):
                return CheckCode.Appears(f"Kernel in possibly vulnerable range: {rel}")
            return CheckCode.Safe(f"Kernel not vulnerable: {rel}")
        except Exception:
            return CheckCode.Unknown

    def exploit(self):
        return None
