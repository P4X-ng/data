#!/usr/bin/env python3
"""Minimal Python scaffolding mirroring a subset of Metasploit's exploit class model.

This is NOT a full reimplementation of Metasploit. It provides just enough
structure to author *local* style exploit modules in Python in a style roughly
analogous to the Ruby API exposed by `Msf::Exploit` and `Msf::Exploit::Local`.

Core elements included:
  * ExploitType constants (REMOTE, LOCAL, OMNI)
  * CheckCode class with canonical codes (unknown, safe, detected, appears, vulnerable, unsupported)
  * Exploit base class: provides metadata, simple run orchestration, error types
  * LocalExploit subclass: exploit_type() -> LOCAL, run_simple helper
  * Timespec validator (ported from Ruby regex) for scheduling helpers

Deliberate omissions (future work potential):
  * Payload generation / sessions abstraction
  * Target selection matrices
  * Advanced reporting, datastore, mixins
  * Network transport abstractions

Intended usage example:

    from msf_exploit import LocalExploit

    class ExamplePrivEsc(LocalExploit):
        NAME = "Example Local Priv Esc"
        DESCRIPTION = "Demonstrates structure of a local exploit stub"
        AUTHOR = ["you"]

        def check(self):
            # Return a CheckCode value
            if self.env.get('kernel_version') == '1.2.3':
                return self.CheckCode.VULNERABLE("Kernel version 1.2.3 present")
            return self.CheckCode.SAFE("Not matching vulnerable version")

        def exploit(self):
            self.log("Performing exploit steps...")
            # ... perform actions ...
            self.success("Exploit complete (demo)")

    if __name__ == '__main__':
        ExamplePrivEsc().run_simple()

"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import sys
import time
from typing import Any, Callable, List, Optional


class ExploitError(RuntimeError):
    """Generic exploit error."""


class ExploitComplete(ExploitError):
    """Signal exploit completed (used for early exit)."""


class ExploitFailed(ExploitError):
    """Signal exploit failed (used for early exit)."""


class ExploitType:
    REMOTE = "remote"
    LOCAL = "local"
    OMNI = "omnipresent"


@dataclass
class CheckCode:
    code: str
    message: str = ""
    reason: Optional[str] = None
    details: Optional[dict] = None

    def __str__(self):  # pragma: no cover - trivial
        return f"{self.code}: {self.message}".strip()

    # Named constructors akin to Ruby constants
    @classmethod
    def UNKNOWN(cls, reason: str | None = None, details: Optional[dict] = None):
        return cls('unknown', _default_msg('unknown', reason), reason, details)

    @classmethod
    def SAFE(cls, reason: str | None = None, details: Optional[dict] = None):
        return cls('safe', _default_msg('safe', reason), reason, details)

    @classmethod
    def DETECTED(cls, reason: str | None = None, details: Optional[dict] = None):
        return cls('detected', _default_msg('detected', reason), reason, details)

    @classmethod
    def APPEARS(cls, reason: str | None = None, details: Optional[dict] = None):
        return cls('appears', _default_msg('appears', reason), reason, details)

    @classmethod
    def VULNERABLE(cls, reason: str | None = None, details: Optional[dict] = None):
        return cls('vulnerable', _default_msg('vulnerable', reason), reason, details)

    @classmethod
    def UNSUPPORTED(cls, reason: str | None = None, details: Optional[dict] = None):
        return cls('unsupported', _default_msg('unsupported', reason), reason, details)


def _default_msg(code: str, reason: str | None) -> str:
    base = {
        'unknown': 'Cannot reliably check exploitability.',
        'safe': 'The target is not exploitable.',
        'detected': 'The service is running, but could not be validated.',
        'appears': 'The target appears to be vulnerable.',
        'vulnerable': 'The target is vulnerable.',
        'unsupported': 'This module does not support check.'
    }.get(code, '')
    return (base + (' ' + reason if reason else '')).strip()


class Exploit:
    # Metadata placeholders (override in subclasses)
    NAME: str = "Unnamed Exploit"
    DESCRIPTION: str = ""
    AUTHOR: List[str] = []
    REFERENCES: List[str] = []
    LICENSE: str = "BSD-3-Clause"

    CheckCode = CheckCode  # expose alias inside subclass namespace

    def __init__(self, **kwargs: Any):
        self.datastore: dict[str, Any] = kwargs
        self.env: dict[str, Any] = {}
        self._start_time = None

    # ===== Interface expected to be overridden =====
    def exploit_type(self) -> str:
        return ExploitType.REMOTE

    def check(self) -> CheckCode:
        return self.CheckCode.UNSUPPORTED()

    def exploit(self) -> None:  # override in subclass
        raise NotImplementedError("exploit() must be implemented by subclass")

    # ===== Helpers =====
    def log(self, msg: str):  # pragma: no cover - IO
        print(f"[*] {msg}")

    def status(self, msg: str):  # pragma: no cover - IO
        print(f"[.] {msg}")

    def success(self, msg: str):  # pragma: no cover - IO
        print(f"[+] {msg}")

    def warning(self, msg: str):  # pragma: no cover - IO
        print(f"[!] {msg}")

    def error(self, msg: str):  # pragma: no cover - IO
        print(f"[-] {msg}")

    # ===== Execution Orchestration =====
    def run_simple(self, auto_check: bool = True) -> None:
        """Basic run wrapper similar to Msf::Simple::Exploit.exploit_simple.

        Steps:
          1. Optional check()
          2. exploit()
        Exceptions ExploitFailed / ExploitComplete are caught and logged.
        """
        self._start_time = time.time()
        try:
            if auto_check:
                cc = self.check()
                self.status(f"Check result => {cc.code}: {cc.message}")
                if cc.code == 'safe':
                    self.warning('Target appears safe; continuing anyway (override behaviour)')
            self.exploit()
            self.success('Exploit finished (no explicit failure signaled)')
        except ExploitComplete as e:  # pragma: no cover - control flow
            self.success(f'Exploit complete: {e}')
        except ExploitFailed as e:  # pragma: no cover - control flow
            self.error(f'Exploit failed: {e}')
        except KeyboardInterrupt:  # pragma: no cover - interactive
            self.warning('Interrupted by user')
        except Exception as e:  # noqa: BLE001
            self.error(f'Unhandled exception: {e}')
            if self.datastore.get('debug'):
                import traceback
                traceback.print_exc()
        finally:
            elapsed = time.time() - self._start_time
            self.status(f'Run finished in {elapsed:.2f}s')

    # Utility for JSON output (for automation)
    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.NAME,
            'description': self.DESCRIPTION,
            'author': self.AUTHOR,
            'exploit_type': self.exploit_type(),
            'references': self.REFERENCES,
            'license': self.LICENSE,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class LocalExploit(Exploit):
    """Specialization for local (non-network) exploits."""

    def exploit_type(self) -> str:  # matches Ruby exploit_type override
        return ExploitType.LOCAL

    # Provide identical method name for parity
    def run_simple(self, opts: Optional[dict[str, Any]] = None, **kwargs):  # type: ignore[override]
        # opts currently ignored; kept for signature similarity
        super().run_simple(**kwargs)


# ===== Timespec Support (ported regex) =====
TIMESPEC_REGEX = re.compile(r"""
    \b(
      (?:[01]?\d|2[0-3]):[0-5]\d(?:\s?(?:AM|PM))? |            # HH:MM 12/24h
      midnight | noon | teatime | now |                          # keywords
      now\s?\+\s?\d+\s?(?:minutes?|hours?|days?|weeks?) |      # relative
      (?:mon|tue|wed|thu|fri|sat|sun)(?:day)? |                  # weekday
      (?:next|last)\s(?:mon|tue|wed|thu|fri|sat|sun)(?:day)? |   # next/last weekday
      \d{1,2}/\d{1,2}/\d{2,4} |                                # MM/DD/YY(YY)
      \d{1,2}\.\d{1,2}\.\d{2,4} |                            # DD.MM.YY(YY)
      \d{6} | \d{8}                                            # MMDDYY or MMDDYYYY
    )\b
""", re.IGNORECASE | re.VERBOSE)


def valid_timespec(spec: str) -> bool:
    return bool(TIMESPEC_REGEX.search(spec or ''))


__all__ = [
    'Exploit',
    'LocalExploit',
    'ExploitType',
    'CheckCode',
    'ExploitError',
    'ExploitFailed',
    'ExploitComplete',
    'valid_timespec'
]
