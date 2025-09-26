from __future__ import annotations
from typing import Dict
from app.services.pvrt_framing import build_preface, build_frames_from_data, build_ctrl_json_frame

def build_iprog_http_payload(iprog: Dict, transfer_id: str) -> bytes:
    """Build a single binary payload suitable for POST /arith/offsets.
    Layout: PVRT preface followed by PF frames (MFST, WIN/PVRT/END..., DONE)
    """
    blob = iprog.get("blob", {}) if isinstance(iprog, dict) else {}
    blob_name = blob.get('name','')
    blob_size = int(blob.get('size','0') or 0)
    blob_seed = int(blob.get('seed','0') or 0)
    blob_fp = f"{blob_name}:{blob_size}:{blob_seed}"
    sha = str(iprog.get("sha256", ""))
    window_size = int(iprog.get("window_size", 65536))
    windows = iprog.get("windows", [])
    anchor = blob_size // 2 if blob_size > 0 else 0
    # Preface
    out = bytearray()
    out += build_preface(transfer_id, channels=1, channel_id=0, blob_fingerprint=blob_fp, object_sha256=sha, psk=None, anchor=anchor)
    # Manifest
    manifest = {
        "algo": "sha256-16",
        "window_size": window_size,
        "total_windows": len(windows),
        "hashes": [w.get("hash16", "") for w in windows],
    }
    out += build_ctrl_json_frame("MFST", manifest)
    # Windows: PVRT with relative BREF only
    from packetfs.filesystem.pvrt_container import build_container  # type: ignore
    for w in windows:
        idx = int(w.get("idx", 0))
        out += build_ctrl_json_frame("WIN", {"idx": idx})
        bref = w.get("bref") or []
        if bref:
            rel_chunks = []
            for (o,l,f) in bref:
                delta = int(o) - anchor
                rel_chunks.append((int(delta) & ((1<<64)-1), int(l), int(f) | 0x01))
            pvrt = build_container(proto=None, bref_chunks=rel_chunks)
            out += build_frames_from_data(pvrt, window_size=1024)
        out += build_ctrl_json_frame("END", {"idx": idx, "h": w.get("hash16", "")})
    out += build_ctrl_json_frame("DONE", {"sha": sha, "tw": len(windows), "ws": window_size})
    return bytes(out)