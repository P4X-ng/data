"""
Safe stub for CVE-2021-3493 (OverlayFS LPE). Performs non-destructive checks.
"""
from msf_exploit import LocalExploit, CheckCode
import platform
import subprocess
import re


class MetasploitModule(LocalExploit):
    def check(self):
        try:
            rel = subprocess.check_output(["uname", "-r"], text=True).strip()
            # rudimentary check for Ubuntu kernels
            if 'ubuntu' not in platform.platform().lower():
                return CheckCode.Safe('Target does not appear to be Ubuntu')
            # extract kernel major version
            m = re.match(r"(\d+\.\d+\.\d+)", rel)
            if not m:
                return CheckCode.Unknown
            ver = tuple(int(x) for x in m.group(1).split('.'))
            if ver[0] < 3 or ver[0] > 5:
                return CheckCode.Safe(f'Kernel {rel} outside expected range')
            return CheckCode.Appears(f'OverlayFS-related kernel: {rel}')
        except Exception:
            return CheckCode.Unknown

    def exploit(self):
        # Not implemented: destructive exploit omitted for safety.
        return None


# NOTE: This Python port is an incomplete, non-destructive stub and does not
# implement the original exploit behavior. It is provided for metadata and
# safe discovery only.
