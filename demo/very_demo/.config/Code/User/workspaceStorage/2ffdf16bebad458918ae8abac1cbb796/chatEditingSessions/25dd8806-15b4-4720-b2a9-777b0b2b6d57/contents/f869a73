import os
import pathlib
import sys
from typing import Optional

# Ensure repo root is on sys.path when running directly
parents = pathlib.Path(__file__).resolve().parents
if len(parents) > 3:
    sys.path.insert(0, str(parents[3]))

from msf_exploit import LocalExploit, CheckCode


class MetasploitModule(LocalExploit):
    """Safe Python port (non-destructive) of the at(1) persistence module.

    This stub checks whether the 'at' command is usable by the current user
    but will not schedule any real jobs to avoid side effects during testing.
    """

    NAME = "at(1) Persistence (stub)"
    DESCRIPTION = "Uses at(1) to schedule a payload; this stub only checks usability."
    AUTHORS = ["Jon Hart <jon_hart@rapid7.com>"]

    PLATFORM = "unix"
    ARCH = "cmd"

    def check(self) -> CheckCode:
        # Simple non-destructive check: can we run 'atq' and is at present?
        try:
            from subprocess import check_output, CalledProcessError

            out = check_output(["atq"], stderr=subprocess.DEVNULL, timeout=2)
            if out:
                return CheckCode.Vulnerable
        except Exception:
            return CheckCode.Safe
        return CheckCode.Safe

    def exploit(self) -> None:
        # Do not perform any real scheduling in the stub
        self.print_warning("Scheduling jobs via at(1) is disabled in this safe stub.")
        self.print_status("If this were the real module, the payload would be written "
                          "to a temporary file and scheduled via at -f <file>.")
