"""
Safe macOS Dirty Cow stub (CVE-2022-46689).
Performs harmless system version checks and reports possible vulnerability.
"""
from msf_exploit import LocalExploit, CheckCode
import platform
import subprocess
import re


class MetasploitModule(LocalExploit):
    def check(self):
        try:
            ver = platform.mac_ver()[0]
            if not ver:
                return CheckCode.Safe('Not macOS')
            # Rudimentary parsing: treat modern macOS versions >= 13 as potentially vulnerable
            m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", ver)
            if not m:
                return CheckCode.Unknown
            major = int(m.group(1))
            if major >= 13:
                return CheckCode.Appears(f'macOS version {ver} — review advisory')
            return CheckCode.Safe(f'macOS version {ver} — likely not vulnerable')
        except Exception:
            return CheckCode.Unknown

    def exploit(self):
        return None
