import pathlib
import sys
import shutil

# Ensure repo root is importable when running this file directly
parents = pathlib.Path(__file__).resolve().parents
if len(parents) > 3:
    sys.path.insert(0, str(parents[3]))

from msf_exploit import LocalExploit, CheckCode


class MetasploitModule(LocalExploit):
    NAME = "Emacs movemail Privilege Escalation (stub)"
    DESCRIPTION = "Safe stub: detects movemail and reports non-destructive actions."
    AUTHORS = ["Markus Hess", "Cliff Stoll", "wvu"]

    PLATFORM = "unix"

    def movemail_path(self):
        return self.datastore.get('MOVEMAIL', '/etc/movemail')

    def check(self) -> CheckCode:
        path = self.movemail_path()
        if not shutil.which(path) and not pathlib.Path(path).exists():
            return CheckCode.Safe
        # We avoid checking SUID bits in the stub for safety
        return CheckCode.Appears

    def exploit(self) -> None:
        self.print_warning('Exploit disabled in stub: would attempt to write to /usr/lib/crontab.local via movemail')
