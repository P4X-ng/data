#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path

# llvm_hints.py -- parse readelf -S and (optionally) llvm-objdump -d to emit a hints JSON
# Output schema:
# {
#   "sections": [ {"name": ".text", "start": <file_off>, "end": <file_off_end>, "kind": "text"}, ... ]
# }
# (mnemonic windows may be added later)

KIND_MAP = {
    "text": {"prefixes": [".text", ".plt"],},
    "rodata": {"prefixes": [".rodata"],},
    "pltgot": {"prefixes": [".plt", ".got"],},
}

def classify_section(name: str) -> str:
    lname = name.strip().lower()
    for kind, spec in KIND_MAP.items():
        for p in spec["prefixes"]:
            if lname.startswith(p):
                return kind
    return "other"

# Example readelf -W -S lines:
# [ 1] .interp           PROGBITS        0000000000000318  000318  00001c  00   A  0   0  1
# fields: idx name type addr off size ...
SEC_RE = re.compile(r"^\s*\[\s*\d+\]\s+(?P<name>\S+)\s+\S+\s+\S+\s+\S+\s+(?P<off>\S+)\s+(?P<size>\S+)\s+")

def parse_readelf_sections(txt: str):
    secs = []
    for line in txt.splitlines():
        m = SEC_RE.match(line)
        if not m:
            continue
        name = m.group("name")
        try:
            off = int(m.group("off"), 16)
            size = int(m.group("size"), 16)
        except ValueError:
            continue
        secs.append({
            "name": name,
            "start": off,
            "end": off + size,
            "kind": classify_section(name),
        })
    return secs


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit hints JSON from readelf/objdump outputs")
    ap.add_argument("--readelf", required=True, help="Path to readelf -W -S text output")
    ap.add_argument("--objdump", default="", help="Path to llvm-objdump -d output (optional)")
    ap.add_argument("--out", required=True, help="Hints JSON path")
    args = ap.parse_args()

    readelf_txt = Path(args.readelf).read_text(errors="ignore")
    sections = parse_readelf_sections(readelf_txt)

    hints = {"sections": sections}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(hints, indent=2))
    print(f"hints_json: {args.out} sections={len(sections)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
