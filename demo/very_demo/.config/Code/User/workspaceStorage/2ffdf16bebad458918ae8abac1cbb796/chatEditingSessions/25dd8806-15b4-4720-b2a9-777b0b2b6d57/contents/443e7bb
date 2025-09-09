import pathlib
import sys
import shutil

# Ensure repo root is importable when running this file directly
parents = pathlib.Path(__file__).resolve().parents
if len(parents) > 3:
    sys.path.insert(0, str(parents[3]))

from msf_exploit import LocalExploit, CheckCode


class MetasploitModule(LocalExploit):
    NAME = "Setuid Nmap Exploit (stub)"
    DESCRIPTION = (
        "Safe stub: detects a setuid nmap binary and explains what would be done. "
    )
    AUTHORS = ["egypt"]

    PLATFORM = ["bsd", "linux", "unix"]

    def check(self) -> CheckCode:
        nmap = self.datastore.get('Nmap', '/usr/bin/nmap')
        if not shutil.which(nmap):
            return CheckCode.Safe
        # We don't inspect file bits for safety; report detected
        return CheckCode.Vulnerable

    def exploit(self) -> None:
        self.print_warning("Exploit actions disabled in safe stub. Would write an NSE script and run nmap.")
