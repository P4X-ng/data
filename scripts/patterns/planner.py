#!/usr/bin/env python3
import argparse
import json
import pickle
import struct
from pathlib import Path

# Planner: emit blueprint.json using {id, xor imm8, add imm8}; 4KB windows, k=4 index.

def rh4(b: bytes) -> int:
    x = struct.unpack('<I', b)[0]
    x ^= (x >> 13)
    x *= 0x9E3779B1
    x &= 0xFFFFFFFF
    return x


def try_match_with_anchor(win: bytes, blob: bytes, anchor: int, cand_offsets: list[int]):
    """Attempt match at a given anchor within the window using candidate blob offsets.
    Returns (off_win, imm8, mode) where off_win is blob offset corresponding to win[0]."""
    if anchor < 0 or anchor + 4 > len(win):
        return None
    # identity
    for off in cand_offsets:
        off_win = off - anchor
        if off_win < 0 or off_win + 64 > len(blob):
            continue
        if blob[off_win:off_win+64] == win[:64]:
            return (off_win, 0, 'id')
    # xor imm8
    sample_pos = (0, 7, 15, 31)
    for off in cand_offsets:
        off_win = off - anchor
        if off_win < 0 or off_win + 64 > len(blob):
            continue
        key0 = win[sample_pos[0]] ^ blob[off_win + sample_pos[0]]
        if all((win[sp] ^ blob[off_win + sp]) == key0 for sp in sample_pos[1:]):
            limit = min(128, len(win), len(blob) - off_win)
            if all((win[j] ^ key0) == blob[off_win + j] for j in range(limit)):
                return (off_win, key0 & 0xFF, 'xor')
    # add imm8
    for off in cand_offsets:
        off_win = off - anchor
        if off_win < 0 or off_win + 64 > len(blob):
            continue
        key0 = (win[sample_pos[0]] - blob[off_win + sample_pos[0]]) & 0xFF
        if all(((win[sp] - blob[off_win + sp]) & 0xFF) == key0 for sp in sample_pos[1:]):
            limit = min(128, len(win), len(blob) - off_win)
            if all(((blob[off_win + j] + key0) & 0xFF) == win[j] for j in range(limit)):
                return (off_win, key0 & 0xFF, 'add')
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Plan offsets+imm8 transforms against blob index")
    ap.add_argument("--path", required=True, help="File to plan")
    ap.add_argument("--snapshot", required=True, help="Blob snapshot path")
    ap.add_argument("--index", required=True, help="Blob index .pkl path (k=4 recommended)")
    ap.add_argument("--index2", default="", help="Optional secondary index .pkl path (e.g., k=8)")
    ap.add_argument("--win", type=int, default=4096)
    ap.add_argument("--out", default="", help="Output blueprint path (defaults under logs/patterns/<ts>/<basename>.blueprint.json)")
    args = ap.parse_args()

    data = Path(args.path).read_bytes()
    blob = Path(args.snapshot).read_bytes()
    with open(args.index, 'rb') as f:
        idx = pickle.load(f)
    idx2 = None
    if args.index2:
        with open(args.index2, 'rb') as f:
            idx2 = pickle.load(f)

    pos = 0
    n = len(data)
    out = []
    raw_spill = 0
    anchors = (0, 64, 128, 256)
    while pos < n:
        win = data[pos:pos+args.win]
        if len(win) < 32:
            # spill small tail
            out.append({"mode":"raw","offset":None,"len":len(win)})
            raw_spill += len(win)
            break
        m = None
        # Try multiple anchors with idx, then idx2
        for a in anchors:
            if a + 4 <= len(win):
                h4 = rh4(win[a:a+4])
                cand = idx.get(h4, [])
                if cand:
                    m = try_match_with_anchor(win, blob, a, cand)
                    if m:
                        break
            if not m and idx2 and a + 8 <= len(win):
                # 8-byte hash using fnv64 from blob_index_build (duplicated here if needed)
                # Reuse rh4 over 8 by composing; fallback: simple Python hash of bytes (not stable across runs). We will do fnv64 inline:
                FNV64_OFF = 0xcbf29ce484222325
                FNV64_PRIME = 0x100000001b3
                h = FNV64_OFF
                for by in win[a:a+8]:
                    h ^= by
                    h = (h * FNV64_PRIME) & 0xFFFFFFFFFFFFFFFF
                cand2 = idx2.get(h, []) if isinstance(idx2, dict) else []
                if cand2:
                    m = try_match_with_anchor(win, blob, a, cand2)
                    if m:
                        break
        if m is None:
            out.append({"mode":"raw","offset":None,"len":len(win)})
            raw_spill += len(win)
        else:
            off, key, mode = m
            # grow forward as long as contiguous matches hold to coalesce
            seg_len = len(win)
            # simple coalesce attempt over next window only
            # (full coalesce would slide; keep minimal for now)
            seg = {"mode":mode, "offset":off, "len":seg_len}
            if mode != 'id':
                seg["imm8"] = key
            out.append(seg)
        pos += len(win)

    plan = {
        "plan_version": "1.0.0",
        "file": str(Path(args.path).resolve()),
        "win": args.win,
        "segments": out,
        "raw_spill_bytes": raw_spill,
    }

    # Decide output path
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        import time
        ts = time.strftime('%Y-%m-%dT%H-%M-%SZ')
        out_dir = Path('logs/patterns') / ts
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (Path(args.path).name + '.blueprint.json')

    out_path.write_text(json.dumps(plan, indent=2))

    # quick summary stats
    total_segments = len(out)
    id_count = sum(1 for s in out if s['mode'] == 'id')
    xor_count = sum(1 for s in out if s['mode'] == 'xor')
    add_count = sum(1 for s in out if s['mode'] == 'add')
    raw_count = sum(1 for s in out if s['mode'] == 'raw')
    print(f"blueprint: {out_path} segments={total_segments} id={id_count} xor={xor_count} add={add_count} raw={raw_count} raw_spill={raw_spill}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
