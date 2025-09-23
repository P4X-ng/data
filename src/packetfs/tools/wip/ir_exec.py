#!/usr/bin/env python3
"""
WIP IR Executor CLI (restored).
Original functionality: parse LLVM IR-ish textual instruction streams, construct packetfs window encodings,
optionally execute via native backend.

Status: WIP (use for experimentation only). Not wired into production packaging or stable APIs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Iterable, Optional, Tuple

# Lightweight placeholder imports: adapt to real modules if/when promoted out of WIP.
try:
    from packetfs.exec.scheduler import WindowedScheduler  # type: ignore
except Exception:  # pragma: no cover - tolerate missing dependency in reduced environments
    WindowedScheduler = None  # type: ignore

@dataclass
class IRInstruction:
    op: str
    args: Tuple[str, ...]

    @staticmethod
    def parse(line: str) -> Optional['IRInstruction']:
        line = line.strip()
        if not line or line.startswith('#'):
            return None
        parts = line.split()
        op = parts[0]
        args: Tuple[str, ...] = tuple(parts[1:])
        return IRInstruction(op=op, args=args)


def parse_ir(lines: Iterable[str]) -> List[IRInstruction]:
    insns: List[IRInstruction] = []
    for ln, raw in enumerate(lines, 1):
        try:
            ins = IRInstruction.parse(raw)
            if ins:
                insns.append(ins)
        except Exception as e:  # pragma: no cover
            print(f"WARN: failed parsing line {ln}: {e}", file=sys.stderr)
    return insns


def encode_windows(insns: Sequence[IRInstruction]):
    if WindowedScheduler is None:
        raise RuntimeError("WindowedScheduler unavailable; ensure packetfs.exec.scheduler importable")
    sched = WindowedScheduler()
    # Hypothetical API surface: adapt to actual method names.
    try:
        enc = sched.encode_ops_only([(i.op, i.args) for i in insns])  # type: ignore[attr-defined]
    except AttributeError:
        # Fallback / placeholder path.
        enc = [(i.op, i.args) for i in insns]
    return enc


def load_input(path: Optional[str]) -> List[str]:
    if path is None or path == '-':
        return sys.stdin.read().splitlines()
    return Path(path).read_text().splitlines()


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog='ir-exec-wip',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """
            WIP IR executor / encoder for packetfs development.

            Input format: whitespace separated tokens per line. First token = op, rest = args.
            Lines beginning with '#': comments.
            Empty lines ignored.
            """
        ),
    )
    p.add_argument('ir', nargs='?', help='IR file (default: stdin)')
    p.add_argument('--json', action='store_true', help='Emit encoded windows as JSON array')
    p.add_argument('--dump-ir', action='store_true', help='Echo normalized parsed IR')
    args = p.parse_args(argv)

    raw_lines = load_input(args.ir)
    insns = parse_ir(raw_lines)

    if args.dump_ir:
        for ins in insns:
            print(ins.op, *ins.args)

    encoded = encode_windows(insns)

    if args.json:
        json.dump(encoded, sys.stdout)
        print()
    else:
        for item in encoded:
            print(item)

    return 0

if __name__ == '__main__':
    raise SystemExit(main())
