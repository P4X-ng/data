#!/usr/bin/env python3
import argparse
import json
import pickle
import struct
from pathlib import Path

# Planner: emit blueprint.json using {id, xor imm8, add imm8}; default 4KB windows.

def rh4(b: bytes) -> int:
    x = struct.unpack('<I', b)[0]
    x ^= (x >> 13)
    x *= 0x9E3779B1
    x &= 0xFFFFFFFF
    return x


def try_match_with_anchor(win: bytes, blob: bytes, anchor: int, cand_offsets: list[int], confirm_len: int = 128, soft_id: bool = False, soft_thresh: float = 0.92):
    """Attempt match at a given anchor within the window using candidate blob offsets.
    Returns (off_win, imm8, mode) where off_win is blob offset corresponding to win[0].
    If soft_id is True, allow approximate identity match when equality ratio >= soft_thresh on confirm_len.
    """
    if anchor < 0 or anchor + 4 > len(win):
        return None
    # identity
    for off in cand_offsets:
        off_win = off - anchor
        if off_win < 0 or off_win + confirm_len > len(blob):
            continue
        if blob[off_win:off_win+confirm_len] == win[:confirm_len]:
            return (off_win, 0, 'id')
        if soft_id:
            # approximate identity: allow small diff fraction
            limit = min(confirm_len, len(win), len(blob) - off_win)
            same = 0
            bw = blob[off_win:off_win+limit]
            ww = win[:limit]
            for j in range(limit):
                if ww[j] == bw[j]:
                    same += 1
            if limit > 0 and (same / float(limit)) >= soft_thresh:
                return (off_win, 0, 'id')
    # xor imm8
    sample_pos = (0, 7, 15, 31)
    for off in cand_offsets:
        off_win = off - anchor
        if off_win < 0 or off_win + 64 > len(blob):
            continue
        key0 = win[sample_pos[0]] ^ blob[off_win + sample_pos[0]]
        if all((win[sp] ^ blob[off_win + sp]) == key0 for sp in sample_pos[1:]):
            limit = min(confirm_len, len(win), len(blob) - off_win)
            if all((win[j] ^ key0) == blob[off_win + j] for j in range(limit)):
                return (off_win, key0 & 0xFF, 'xor')
    # add imm8
    for off in cand_offsets:
        off_win = off - anchor
        if off_win < 0 or off_win + 64 > len(blob):
            continue
        key0 = (win[sample_pos[0]] - blob[off_win + sample_pos[0]]) & 0xFF
        if all(((win[sp] - blob[off_win + sp]) & 0xFF) == key0 for sp in sample_pos[1:]):
            limit = min(confirm_len, len(win), len(blob) - off_win)
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
    ap.add_argument("--hints", default="", help="LLVM-aware hints JSON (sections: text/rodata/pltgot/other)")
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

    # Load hints (section ranges in file offsets)
    sections = []
    if args.hints:
        try:
            hj = json.loads(Path(args.hints).read_text())
            sections = hj.get('sections', [])
        except Exception:
            sections = []

    def sec_kind(file_off: int) -> str:
        for s in sections:
            try:
                if s['start'] <= file_off < s['end']:
                    return s.get('kind', 'other')
            except Exception:
                continue
        return 'other'

    pos = 0
    n = len(data)
    out = []
    raw_spill = 0
    base_anchors = (0, 16, 32, 64, 128, 256)
    while pos < n:
        win = data[pos:pos+args.win]
        if len(win) < 32:
            # spill small tail
            out.append({"mode":"raw","offset":None,"len":len(win)})
            raw_spill += len(win)
            break
        kind = sec_kind(pos)
        # Bias by section kind
        if kind == 'text':
            anchors = base_anchors + (192,)
            confirm_len = 256
            slides = (0, 4, 8, 12)
        elif kind == 'rodata':
            anchors = base_anchors
            confirm_len = 128
            slides = (0,)
        else:
            anchors = base_anchors
            confirm_len = 128
            slides = (0,)

        m = None
        # Try anchors with idx, then idx2; include small slide adjustments for text
        for a in anchors:
            for sld in slides:
                a2 = a + sld
                if a2 + 4 <= len(win):
                    h4 = rh4(win[a2:a2+4])
                    cand = idx.get(h4, [])
                    if cand:
                        m = try_match_with_anchor(win, blob, a2, cand, confirm_len=confirm_len, soft_id=(kind=='text'))
                        if m:
                            break
                if not m and idx2 and a2 + 8 <= len(win):
                    FNV64_OFF = 0xcbf29ce484222325
                    FNV64_PRIME = 0x100000001b3
                    h = FNV64_OFF
                    for by in win[a2:a2+8]:
                        h ^= by
                        h = (h * FNV64_PRIME) & 0xFFFFFFFFFFFFFFFF
                    cand2 = idx2.get(h, []) if isinstance(idx2, dict) else []
                    if cand2:
                        m = try_match_with_anchor(win, blob, a2, cand2, confirm_len=confirm_len, soft_id=(kind=='text'))
                        if m:
                            break
            if m:
                break

        if m is None:
            # no match → raw
            new_seg = {"mode":"raw","offset":None,"len":len(win)}
            if out and out[-1]['mode'] == 'raw':
                out[-1]['len'] += new_seg['len']
            else:
                out.append(new_seg)
            raw_spill += len(win)
        else:
            off, key, mode = m
            seg_len = len(win)
            new_seg = {"mode":mode, "offset":off, "len":seg_len}
            if mode != 'id':
                new_seg["imm8"] = key
            # coalesce with previous if contiguous and same mode (+imm)
            if out and out[-1]['mode'] == mode and out[-1]['mode'] != 'raw':
                prev = out[-1]
                same_imm = (('imm8' not in prev and 'imm8' not in new_seg) or (prev.get('imm8') == new_seg.get('imm8')))
                if same_imm and prev['offset'] + prev['len'] == new_seg['offset']:
                    prev['len'] += new_seg['len']
                else:
                    out.append(new_seg)
            else:
                out.append(new_seg)
        pos += len(win)

    plan = {
        "plan_version": "1.0.0",
        "file": str(Path(args.path).resolve()),
        "win": args.win,
        "segments": out,
        "raw_spill_bytes": raw_spill,
        "hints_used": bool(sections),
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
