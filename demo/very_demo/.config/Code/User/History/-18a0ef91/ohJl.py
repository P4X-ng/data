import os
import shutil
import pathlib
import sys
from typing import Any

# Make the repository root importable when running this file directly
parents = pathlib.Path(__file__).resolve().parents
if len(parents) > 3:
    sys.path.insert(0, str(parents[3]))

from msf_exploit import LocalExploit, CheckCode


class MetasploitModule(LocalExploit):
    """Safe Python port (non-destructive) of the chkrootkit local module.

    Note: This file intentionally does NOT implement any real exploit steps.
    It's a metadata-compatible stub for development and testing only.
    """

    NAME = "Chkrootkit Local Privilege Escalation (stub)"
    DESCRIPTION = (
        "Chkrootkit before 0.50 runs certain binaries with elevated privileges. "
        "This Python port is a safe, non-destructive stub that only detects the "
        "presence of chkrootkit on the target and does NOT perform any exploit.")
    AUTHORS = ["Thomas Stangner (original)", 'Julien "jvoisin" Voisin (module)']
    REFERENCES = [
        ("CVE", "2014-0476"),
    ]

    PLATFORM = "unix"
    ARCH = "cmd"

    def check(self) -> CheckCode:
        """Non-destructive check: report if a chkrootkit binary exists on PATH.

        Returns CheckCode::Appears if chkrootkit is present, otherwise Safe.
        """
        chk = shutil.which("chkrootkit") or shutil.which("/usr/sbin/chkrootkit")
        if chk:
            # We don't try to parse versions or execute binaries here.
            return CheckCode.Appears
        return CheckCode.Safe

    def exploit(self) -> None:
        # For safety, we do not implement the privilege escalation.
        self.print_warning("Exploit steps are disabled in this Python stub for safety.")
        self.print_status("Detected chkrootkit present: if this were the real module, "
                          "exploit actions would follow. No actions performed.")
