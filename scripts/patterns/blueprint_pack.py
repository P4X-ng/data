#!/usr/bin/env python3
import argparse
import json
import lzma
from pathlib import Path

# Simple binary blueprint packer (.pbb) with two integer encodings:
# - LEB128 varint (7-bit payload)
# - Packed base-32 digits (5 bits per digit)
# Chooses smaller per integer. Packs op as 1 byte (0=id,1=xor,2=add,3=raw).
# NOTE: This packs metadata only (no raw payloads). For full reconstruction,
# raw segments must carry bytes or be sent separately.


def leb128_u(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def base32_packed_u(n: int) -> bytes:
    # Encode unsigned integer to packed 5-bit digits (LSB-first), then pack into bytes.
    if n == 0:
        digits = [0]
    else:
        digits = []
        while n:
            digits.append(n & 0x1F)
            n >>= 5
    out = bytearray()
    acc = 0
    bits = 0
    for d in digits:
        acc |= (d & 0x1F) << bits
        bits += 5
        while bits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            bits -= 8
    if bits:
        out.append(acc & 0xFF)
    return bytes(out)


def enc_int_best(n: int) -> bytes:
    a = leb128_u(n)
    b = base32_packed_u(n)
    # prefix 0x00 for leb128, 0x01 for base32packed
    if len(a) <= len(b):
        return b"\x00" + a
    else:
        return b"\x01" + b


def pack_blueprint(bp_path: Path) -> bytes:
    bp = json.loads(bp_path.read_text())
    segs = bp.get("segments", [])
    out = bytearray()
    out += b"PBB1"  # magic
    out += enc_int_best(len(segs))
    for s in segs:
        mode = s["mode"]
        if mode == "id":
            out.append(0)
            out += enc_int_best(int(s["offset"]))
            out += enc_int_best(int(s["len"]))
        elif mode == "xor":
            out.append(1)
            out += enc_int_best(int(s["offset"]))
            out += enc_int_best(int(s["len"]))
            out.append(int(s.get("imm8", 0)) & 0xFF)
        elif mode == "add":
            out.append(2)
            out += enc_int_best(int(s["offset"]))
            out += enc_int_best(int(s["len"]))
            out.append(int(s.get("imm8", 0)) & 0xFF)
        else:
            # raw segment: metadata only!
            out.append(3)
            out += enc_int_best(int(s["len"]))
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Pack blueprint JSON into .pbb and .xz")
    ap.add_argument("--in", dest="inp", required=True, help="Input blueprint JSON path")
    ap.add_argument("--out", dest="out", default="", help="Output .pbb path (defaults beside input)")
    args = ap.parse_args()

    in_path = Path(args.inp)
    out_path = Path(args.out) if args.out else in_path.with_suffix('.pbb')
    data = pack_blueprint(in_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    # xz (LZMA2) compress
    xz_path = out_path.with_suffix(out_path.suffix + '.xz')
    xz_path.write_bytes(lzma.compress(data, preset=6, format=lzma.FORMAT_XZ))
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes), {xz_path} ({xz_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
