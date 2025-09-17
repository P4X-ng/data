#!/usr/bin/env python3
"""
pattern_scan.py — Production analysis tool for binary pattern discovery

Features (streaming-friendly):
- Byte histogram (global)
- Shannon entropy per window (default 4096 bytes)
- 2-gram (byte pairs) frequency analysis (top K)
- Offset-modulo profiles (aggregated per remainder; dominant byte approximation)
- Bitplane density per window (8 bit positions)
- Run-length stats (0x00, 0xFF, and any repeated byte)
- CRC32 per window

Inputs:
- scan-file: analyze a file path
- scan-blob: snapshot a VirtualBlob (name,size,seed) into a temp file under logs/patterns and analyze it

Outputs (under logs/patterns/<timestamp>/):
- <base>.summary.txt
- <base>.hist.csv
- <base>.entropy.csv
- <base>.ngrams.csv
- <base>.offsetmod.csv    # aggregated per remainder: approximated dominant byte via mean value
- <base>.bitplanes.csv
- <base>.runlengths.csv
- <base>.crc32.csv
- scan_manifest.json

Plan file support:
- --plan path/to/json uses a config with keys:
  {
    "window_size": 4096,
    "top_k_ngrams": 50,
    "offset_modulos": [64,128,512,4096],
    "keep_snapshot": false
  }

Notes:
- Uses only Python stdlib for portability and to avoid heavy dependencies.
- VirtualBlob is imported from realsrc; the script adjusts sys.path accordingly.
- Offset-modulo profile here aggregates by remainder: it records count and mean(byte) per remainder
  and reports the "dominant_byte" as round(mean). This is fast and scalable; if you want full
  per-byte histograms per remainder (M*256), we can add a flag to enable it later.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import datetime as dt
import hashlib
import json
import math
import os
import stat
import sys
import tempfile
from array import array
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import zlib

# Make realsrc importable for VirtualBlob
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REALSRC = _REPO_ROOT / "realsrc"
if _REALSRC.exists():
    sys.path.insert(0, str(_REALSRC))

try:
    from packetfs.filesystem.virtual_blob import VirtualBlob  # type: ignore
except Exception:
    VirtualBlob = None  # type: ignore


def sha256_file(path: Path, bufsize: int = 8 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024.0:
            return f"{x:.2f} {u}"
        x /= 1024.0
    return f"{x:.2f} PB"


def ensure_outdir() -> Path:
    ts = dt.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
    outdir = _REPO_ROOT / "logs" / "patterns" / ts
    outdir.mkdir(parents=True, exist_ok=True)
    return outdir


def write_csv(path: Path, header: List[str], rows: Iterable[Iterable[object]]) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        if header:
            w.writerow(header)
        for row in rows:
            w.writerow(row)


def window_iter(stream: Iterable[bytes], win: int) -> Iterable[Tuple[int, bytes]]:
    """Yield (absolute_offset, window_bytes) from a stream of chunks, stitching boundaries."""
    leftover = b""
    ofs = 0
    for chunk in stream:
        if not chunk:
            continue
        buf = leftover + chunk
        take = (len(buf) // win) * win
        i = 0
        while i < take:
            w = buf[i : i + win]
            yield (ofs + i, w)
            i += win
        leftover = buf[take:]
        ofs += take
    if leftover:
        yield (ofs, leftover)


def chunk_reader(path: Path, chunk: int = 8 << 20) -> Iterable[bytes]:
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            yield b


def analyze_file(
    in_path: Path,
    outdir: Path,
    window_size: int = 4096,
    top_k: int = 50,
    mods: List[int] = [64, 128, 512, 4096],
    do_zlib: bool = False,
    do_lags: bool = False,
    lags_set: Optional[List[int]] = None,
    do_delta: bool = False,
    do_dupes: bool = False,
    do_magic: bool = False,
) -> None:
    # Metadata
    st = in_path.stat()
    size = st.st_size
    sha256 = sha256_file(in_path)
    mtime_iso = dt.datetime.utcfromtimestamp(st.st_mtime).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Outputs
    base = in_path.name
    summary_path = outdir / f"{base}.summary.txt"
    hist_path = outdir / f"{base}.hist.csv"
    entropy_path = outdir / f"{base}.entropy.csv"
    ngrams_path = outdir / f"{base}.ngrams.csv"
    offsetmod_path = outdir / f"{base}.offsetmod.csv"
    bitplanes_path = outdir / f"{base}.bitplanes.csv"
    runlengths_path = outdir / f"{base}.runlengths.csv"
    crc32_path = outdir / f"{base}.crc32.csv"
    manifest_path = outdir / "scan_manifest.json"
    zlib_path = outdir / f"{base}.zlib.csv"
    lags_path = outdir / f"{base}.lags.csv"
    delta_entropy_path = outdir / f"{base}.delta_entropy.csv"
    dupes_path = outdir / f"{base}.dupes.csv"
    magic_path = outdir / f"{base}.magic.txt"

    # Accumulators
    hist = array("Q", [0] * 256)
    ngram2 = array("Q", [0] * 65536)

    # Offset-mod aggregates: per M -> (counts[remainder], sums[remainder])
    mods = sorted(set(int(m) for m in mods if int(m) > 0))
    mod_counts: Dict[int, array] = {}
    mod_sums: Dict[int, array] = {}
    for m in mods:
        mod_counts[m] = array("Q", [0] * m)
        mod_sums[m] = array("Q", [0] * m)

    # Run-length trackers
    longest_zero = {"len": 0, "start": -1}
    longest_ff = {"len": 0, "start": -1}
    longest_any = {"len": 0, "start": -1, "byte": None}
    cur_byte = None
    cur_len = 0
    cur_start = 0

    # For 2-gram continuity
    prev = None

    # Writers for per-window outputs
    entropy_rows: List[Tuple[int, float, float]] = []
    bitplane_rows: List[Tuple[int, int, float]] = []  # (win_ofs, bit_pos, density)
    crc_rows: List[Tuple[int, int, int]] = []  # (win_ofs, crc32, win_len)
    zlib_rows: List[Tuple[int, int, int, float]] = []  # (win_ofs, raw_len, comp_len, ratio)
    lags_rows: List[Tuple[int, int, float]] = []  # (win_ofs, lag, corr)
    delta_entropy_rows: List[Tuple[int, float]] = []  # (win_ofs, delta_entropy)

    # Stream analysis
    total_consumed = 0
    if do_lags and (lags_set is None or len(lags_set) == 0):
        lags_set = [1, 2, 4, 8, 16, 32, 64]
    for win_ofs, w in window_iter(chunk_reader(in_path), window_size):
        wl = len(w)
        if wl == 0:
            continue
        total_consumed += wl

        # Global hist + ngram + offset-mod + run-length
        # Hist and n-grams
        for i, b in enumerate(w):
            hist[b] += 1
            if prev is not None:
                pair = (prev << 8) | b
                ngram2[pair] += 1
            prev = b

        # Offset-mod aggregates (counts and sums)
        if mods:
            # Using absolute offsets for this window
            for i, b in enumerate(w):
                abs_ofs = win_ofs + i
                for m in mods:
                    r = abs_ofs % m
                    mod_counts[m][r] += 1
                    mod_sums[m][r] += b

        # Run-length tracking across windows (any repeated byte)
        i = 0
        while i < wl:
            b = w[i]
            if cur_byte is None:
                cur_byte = b
                cur_len = 1
                cur_start = win_ofs + i
            elif b == cur_byte:
                cur_len += 1
            else:
                # finalize previous run
                if cur_byte == 0x00 and cur_len > longest_zero["len"]:
                    longest_zero.update({"len": cur_len, "start": cur_start})
                if cur_byte == 0xFF and cur_len > longest_ff["len"]:
                    longest_ff.update({"len": cur_len, "start": cur_start})
                if cur_len > longest_any["len"]:
                    longest_any.update({"len": cur_len, "start": cur_start, "byte": cur_byte})
                # start new
                cur_byte = b
                cur_len = 1
                cur_start = win_ofs + i
            i += 1

        # Per-window entropy and bitplane density and CRC32
        # Entropy
        # Build local hist quickly
        wh = [0] * 256
        for b in w:
            wh[b] += 1
        e = 0.0
        for c in wh:
            if c:
                p = c / wl
                e -= p * math.log2(p)
        entropy_rows.append((win_ofs, e, e / 8.0))

        # Bitplane density: fraction of set bits per bit position
        # Compute counts efficiently
        bit_counts = [0] * 8
        for b in w:
            for bit in range(8):
                bit_counts[bit] += (b >> bit) & 1
        for bit in range(8):
            density = bit_counts[bit] / wl
            bitplane_rows.append((win_ofs, bit, density))

        # CRC32
        crc = binascii.crc32(w) & 0xFFFFFFFF
        crc_rows.append((win_ofs, crc, wl))

        # Optional zlib compressibility per window
        if do_zlib:
            try:
                comp = zlib.compress(w, level=6)
                comp_len = len(comp)
                ratio = comp_len / wl if wl else 1.0
                zlib_rows.append((win_ofs, wl, comp_len, ratio))
            except Exception:
                zlib_rows.append((win_ofs, wl, wl, 1.0))

        # Optional lag correlations
        if do_lags and lags_set:
            for lag in lags_set:
                if lag <= 0 or lag >= wl:
                    continue
                a = w[:-lag]
                b = w[lag:]
                # Compute Pearson r quickly
                n = len(a)
                if n <= 1:
                    continue
                sum_a = sum(a)
                sum_b = sum(b)
                sum_a2 = sum(x * x for x in a)
                sum_b2 = sum(y * y for y in b)
                sum_ab = sum(x * y for x, y in zip(a, b))
                num = n * sum_ab - sum_a * sum_b
                den_sq = (n * sum_a2 - sum_a * sum_a) * (n * sum_b2 - sum_b * sum_b)
                if den_sq <= 0:
                    corr = 0.0
                else:
                    corr = num / (den_sq ** 0.5)
                # Clamp numerical noise
                if corr != corr:
                    corr = 0.0
                if corr > 1.0:
                    corr = 1.0
                if corr < -1.0:
                    corr = -1.0
                lags_rows.append((win_ofs, lag, corr))

        # Optional delta-entropy (entropy of byte diffs)
        if do_delta:
            if wl > 1:
                dh = [0] * 256
                prev = w[0]
                for j in range(1, wl):
                    d = (w[j] - prev) & 0xFF
                    dh[d] += 1
                    prev = w[j]
                de = 0.0
                total = wl - 1
                for c in dh:
                    if c:
                        p = c / total
                        de -= p * math.log2(p)
                delta_entropy_rows.append((win_ofs, de))
            else:
                delta_entropy_rows.append((win_ofs, 0.0))

    # finalize tail run
    if cur_byte is not None:
        if cur_byte == 0x00 and cur_len > longest_zero["len"]:
            longest_zero.update({"len": cur_len, "start": cur_start})
        if cur_byte == 0xFF and cur_len > longest_ff["len"]:
            longest_ff.update({"len": cur_len, "start": cur_start})
        if cur_len > longest_any["len"]:
            longest_any.update({"len": cur_len, "start": cur_start, "byte": cur_byte})

    # Write outputs
    # Histogram
    rows = ((i, int(hist[i]), (hist[i] / size) if size else 0.0) for i in range(256))
    write_csv(hist_path, ["byte", "count", "freq"], rows)

    # Entropy per window
    write_csv(entropy_path, ["offset", "entropy", "normalized"], entropy_rows)

    # Optional extras
    if do_zlib and zlib_rows:
        write_csv(zlib_path, ["offset", "raw_len", "zlib_len", "ratio"], zlib_rows)
    if do_lags and lags_rows:
        write_csv(lags_path, ["offset", "lag", "corr"], lags_rows)
    if do_delta and delta_entropy_rows:
        write_csv(delta_entropy_path, ["offset", "delta_entropy"], delta_entropy_rows)

    # N-grams top K
    # Build list of (count, hi, lo) and take top_k
    top_pairs: List[Tuple[int, int, int]] = []
    for idx, c in enumerate(ngram2):
        if c:
            hi = (idx >> 8) & 0xFF
            lo = idx & 0xFF
            top_pairs.append((int(c), hi, lo))
    top_pairs.sort(reverse=True, key=lambda t: t[0])
    top_pairs = top_pairs[:top_k]
    write_csv(ngrams_path, ["byte1", "byte2", "count", "freq"], ((hi, lo, c, c / (size - 1) if size > 1 else 0.0) for c, hi, lo in top_pairs))

    # Offset-mod aggregated profile (dominant byte approximation via mean)
    # For each modulo M and remainder r, we report count and approx dominant_byte = round(sum/count)
    om_rows: List[Tuple[int, int, int, int]] = []  # (mod, remainder, approx_byte, count)
    for m in mods:
        counts = mod_counts[m]
        sums = mod_sums[m]
        for r in range(m):
            c = int(counts[r])
            if c == 0:
                continue
            approx_b = int(round(sums[r] / c))
            # Clamp
            if approx_b < 0:
                approx_b = 0
            if approx_b > 255:
                approx_b = 255
            om_rows.append((m, r, approx_b, c))
    # Optionally, to keep file sizes manageable, we can sort by count and cap total rows
    # Here we keep all rows but you can post-filter with tools/plotters as needed.
    write_csv(offsetmod_path, ["modulo", "remainder", "approx_byte", "count"], om_rows)

    # Bitplanes
    write_csv(bitplanes_path, ["offset", "bit", "density"], bitplane_rows)

    # Run-lengths summary CSV
    run_rows = [
        ("zero", longest_zero["len"], longest_zero["start"]),
        ("ff", longest_ff["len"], longest_ff["start"]),
        ("any", longest_any["len"], longest_any["start"], longest_any["byte"]),
    ]
    # Align header columns: for 'any', include byte value column
    with runlengths_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["type", "max_run_len", "start_offset", "byte_value(optional)"])
        for row in run_rows:
            w.writerow(row)

    # CRC32
    write_csv(crc32_path, ["offset", "crc32", "size"], crc_rows)

    # Optional duplicates detection using CRC32 groups
    if do_dupes:
        groups: Dict[Tuple[int, int], List[int]] = {}
        for ofs, crc_val, wlen in crc_rows:
            key = (wlen, crc_val)
            groups.setdefault(key, []).append(ofs)
        dupe_rows: List[Tuple[int, int, str]] = []  # (size, crc32_hex, offsets_csv)
        for (wlen, crc_val), offs in groups.items():
            if len(offs) > 1:
                dupe_rows.append((wlen, crc_val, ";".join(str(o) for o in offs)))
        write_csv(dupes_path, ["win_size", "crc32", "offsets"], ((sz, f"0x{crc:08x}", offcsv) for sz, crc, offcsv in dupe_rows))

    # Optional magic detection (simple, header-based)
    if do_magic:
        try:
            with in_path.open("rb") as fh:
                head = fh.read(4096)
            lines = []
            def has(sig: bytes, ofs: int = 0) -> bool:
                return len(head) >= ofs + len(sig) and head[ofs:ofs+len(sig)] == sig
            if has(b"\x7fELF", 0):
                lines.append("ELF header at 0x0")
            if has(b"MZ", 0):
                lines.append("MZ header at 0x0 (PE/COFF)")
            if has(b"PK\x03\x04", 0):
                lines.append("ZIP local header at 0x0")
            if has(b"\x1f\x8b", 0):
                lines.append("GZIP header at 0x0")
            if has(b"\x89PNG\r\n\x1a\n", 0):
                lines.append("PNG header at 0x0")
            if lines:
                magic_path.write_text("\n".join(lines) + "\n")
            else:
                magic_path.write_text("(no recognized header-level magic)\n")
        except Exception:
            pass

    # Summary
    with summary_path.open("w") as f:
        f.write("Pattern scan summary\n")
        f.write("====================\n\n")
        f.write(f"File: {in_path}\n")
        f.write(f"Size: {size} bytes ({human_bytes(size)})\n")
        f.write(f"SHA256: {sha256}\n")
        f.write(f"mtime: {mtime_iso} UTC\n")
        f.write(f"Window: {window_size} bytes\n")
        f.write(f"Top K 2-grams: {top_k}\n")
        f.write(f"Offset modulos: {mods}\n\n")

        # Basic insights
        # Most frequent bytes
        topb = sorted(((int(hist[i]), i) for i in range(256)), reverse=True)[:8]
        f.write("Top bytes (count, byte):\n")
        for c, i in topb:
            freq = c / size if size else 0.0
            f.write(f"  {c:12d} 0x{i:02x} ({i:3d})  freq={freq:.6f}\n")
        f.write("\n")

        # Entropy stats
        if entropy_rows:
            es = [e for _, e, _ in entropy_rows]
            f.write(f"Entropy per-window: min={min(es):.4f} max={max(es):.4f} avg={sum(es)/len(es):.4f} (bits/byte)\n")
        else:
            f.write("Entropy per-window: (no windows)\n")
        f.write("\n")

        # Longest runs
        f.write("Longest runs:\n")
        f.write(f"  zero: len={longest_zero['len']} start={longest_zero['start']}\n")
        f.write(f"  ff:   len={longest_ff['len']} start={longest_ff['start']}\n")
        anyb = longest_any.get("byte")
        f.write(f"  any:  len={longest_any['len']} start={longest_any['start']} byte={('0x%02x'%anyb) if anyb is not None else 'n/a'}\n")

    # Manifest
    manifest = {
        "plan_version": "1.0.0",
        "tool": {"name": "pattern_scan", "version": "0.1.0"},
        "input": {
            "path": str(in_path),
            "size_bytes": size,
            "mtime_utc": mtime_iso,
            "sha256": sha256,
        },
        "analysis": {
            "window_size": window_size,
            "top_k_ngrams": top_k,
            "offset_modulos": mods,
            "zlib": do_zlib,
            "lags": (lags_set if do_lags else []),
            "delta_entropy": do_delta,
            "dupes": do_dupes,
            "magic": do_magic,
        },
        "outputs": {
            "summary": str(summary_path),
            "hist_csv": str(hist_path),
            "entropy_csv": str(entropy_path),
            "ngrams_csv": str(ngrams_path),
            "offsetmod_csv": str(offsetmod_path),
            "bitplanes_csv": str(bitplanes_path),
            "runlengths_csv": str(runlengths_path),
            "crc32_csv": str(crc32_path),
        },
    }
    with manifest_path.open("w") as f:
        json.dump(manifest, f, indent=2)


def handle_scan_file(args: argparse.Namespace) -> int:
    plan = load_plan(args.plan) if args.plan else {}
    window = int(plan.get("window_size", args.win))
    top_k = int(plan.get("top_k_ngrams", args.k))
    mods = plan.get("offset_modulos", parse_mods(args.mods))
    do_zlib = bool(plan.get("zlib", args.zlib))
    do_lags = bool(plan.get("lags", args.lags))
    lags_set = parse_mods(args.lags_set) if args.lags_set else plan.get("lags", [])
    do_delta = bool(plan.get("delta_entropy", args.delta))
    do_dupes = bool(plan.get("dupes", args.dupes))
    do_magic = bool(plan.get("magic", args.magic))

    in_path = Path(args.path)
    if not in_path.is_file():
        print(f"ERROR: File not found: {in_path}")
        return 2
    outdir = ensure_outdir()
    analyze_file(
        in_path,
        outdir,
        window_size=window,
        top_k=top_k,
        mods=mods,
        do_zlib=do_zlib,
        do_lags=do_lags,
        lags_set=lags_set if isinstance(lags_set, list) else [],
        do_delta=do_delta,
        do_dupes=do_dupes,
        do_magic=do_magic,
    )
    print(f"[OK] Wrote outputs to: {outdir}")
    return 0


def load_plan(plan_path: Optional[str]) -> Dict:
    if not plan_path:
        return {}
    p = Path(plan_path)
    if not p.exists():
        print(f"WARNING: plan file not found: {p}")
        return {}
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"WARNING: failed to parse plan JSON: {e}")
        return {}


def parse_mods(s: str) -> List[int]:
    if not s:
        return []
    out: List[int] = []
    for part in s.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out


def handle_scan_blob(args: argparse.Namespace) -> int:
    if VirtualBlob is None:
        print("ERROR: VirtualBlob not importable (realsrc not available)")
        return 2

    plan = load_plan(args.plan) if args.plan else {}
    window = int(plan.get("window_size", args.win))
    top_k = int(plan.get("top_k_ngrams", args.k))
    mods = plan.get("offset_modulos", parse_mods(args.mods))
    keep = bool(plan.get("keep_snapshot", args.keep_snapshot))
    do_zlib = bool(plan.get("zlib", args.zlib))
    do_lags = bool(plan.get("lags", args.lags))
    lags_set = parse_mods(args.lags_set) if args.lags_set else plan.get("lags", [])
    do_delta = bool(plan.get("delta_entropy", args.delta))
    do_dupes = bool(plan.get("dupes", args.dupes))
    do_magic = bool(plan.get("magic", args.magic))

    # Create and fill blob
    blob_name = args.name
    blob_size = int(args.size_mb) * (1 << 20)
    seed = int(args.seed)

    vb = VirtualBlob(name=blob_name, size_bytes=blob_size, seed=seed)
    vb.create_or_attach(create=True)
    vb.ensure_filled()
    try:
        # Snapshot to temp file inside outdir for reuse/debug
        outdir = ensure_outdir()
        snap_path = outdir / f"blob_{blob_name}_{args.size_mb}MB_{seed}.bin"
        with snap_path.open("wb") as f:
            # Read in 8MiB chunks via .read with wrap-around
            chunk = 8 << 20
            remaining = blob_size
            ofs = 0
            while remaining > 0:
                n = min(chunk, remaining)
                f.write(vb.read(ofs, n))
                ofs += n
                remaining -= n
        analyze_file(
            snap_path,
            outdir,
            window_size=window,
            top_k=top_k,
            mods=mods,
            do_zlib=do_zlib,
            do_lags=do_lags,
            lags_set=lags_set if isinstance(lags_set, list) else [],
            do_delta=do_delta,
            do_dupes=do_dupes,
            do_magic=do_magic,
        )
        print(f"[OK] Wrote outputs to: {outdir}")
        if not keep:
            try:
                snap_path.unlink()
            except Exception:
                pass
        # Update manifest with blob metadata (append or rewrite)
        man = outdir / "scan_manifest.json"
        try:
            j = json.loads(man.read_text())
        except Exception:
            j = {}
        j.setdefault("blob", {})
        j["blob"].update({
            "name": blob_name,
            "size_bytes": blob_size,
            "seed": seed,
        })
        man.write_text(json.dumps(j, indent=2))
        return 0
    finally:
        try:
            vb.close()
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PacketFS pattern scanner")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("scan-file", help="Scan a regular file")
    pf.add_argument("--path", required=True, help="File to scan")
    pf.add_argument("--win", type=int, default=4096, help="Window size for per-window metrics")
    pf.add_argument("--k", type=int, default=50, help="Top K 2-grams")
    pf.add_argument("--mods", default="64,128,512,4096", help="Comma-separated offset modulos")
    pf.add_argument("--plan", default="", help="Optional plan JSON path")
    pf.add_argument("--zlib", action="store_true", help="Compute zlib compressibility per window")
    pf.add_argument("--lags", action="store_true", help="Compute lag correlations for common lags")
    pf.add_argument("--lags-set", default="", help="Comma-separated lags (e.g., 1,2,4,8,16,32,64)")
    pf.add_argument("--delta", action="store_true", help="Compute delta-entropy per window")
    pf.add_argument("--dupes", action="store_true", help="Detect duplicate windows via CRC32 groups")
    pf.add_argument("--magic", action="store_true", help="Detect simple file magic (header)")
    pf.set_defaults(func=handle_scan_file)

    pb = sub.add_parser("scan-blob", help="Scan a VirtualBlob snapshot")
    pb.add_argument("--name", default="pfs_vblob_test", help="VirtualBlob name")
    pb.add_argument("--size-mb", dest="size_mb", type=int, default=100, help="VirtualBlob size (MB)")
    pb.add_argument("--seed", type=int, default=1337, help="VirtualBlob seed")
    pb.add_argument("--win", type=int, default=4096, help="Window size for per-window metrics")
    pb.add_argument("--k", type=int, default=50, help="Top K 2-grams")
    pb.add_argument("--mods", default="64,128,512,4096", help="Comma-separated offset modulos")
    pb.add_argument("--keep-snapshot", action="store_true", help="Keep blob snapshot file after analysis")
    pb.add_argument("--plan", default="", help="Optional plan JSON path")
    pb.add_argument("--zlib", action="store_true", help="Compute zlib compressibility per window")
    pb.add_argument("--lags", action="store_true", help="Compute lag correlations for common lags")
    pb.add_argument("--lags-set", default="", help="Comma-separated lags (e.g., 1,2,4,8,16,32,64)")
    pb.add_argument("--delta", action="store_true", help="Compute delta-entropy per window")
    pb.add_argument("--dupes", action="store_true", help="Detect duplicate windows via CRC32 groups")
    pb.add_argument("--magic", action="store_true", help="Detect simple file magic (header)")
    pb.set_defaults(func=handle_scan_blob)

    return p


def main() -> int:
    p = build_parser()
    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
