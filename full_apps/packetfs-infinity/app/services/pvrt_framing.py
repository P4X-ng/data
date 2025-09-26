# PVRT framing utilities (simple MVP)
import struct
from typing import List, Tuple

MAGIC_PREFACE = b"PVRT"
MAGIC_FRAME = b"PF"
VER = 1

# Flags
FLAG_CTRL = 0x01  # control frame carrying JSON or small metadata
FLAG_DATA = 0x00  # data frame (PVRT ops / payload)

# Preface format (variable-length fields):
# magic[4] VER[1] FLAGS[1] CHANNELS[2] CH_ID[2]
# TID_LEN[1] TID[tid_len]
# BLOB_LEN[1] BLOB[b_len]
# OBJ_LEN[1] OBJ[obj_len]
# PSK_LEN[1] PSK[psk_len]
# [ANCHOR_LEN=8 ANCHOR[8]] if flags & 0x01

# Preface flags
PREFACE_FLAG_ANCHOR = 0x01

def build_preface(
    transfer_id: str,
    channels: int,
    channel_id: int,
    blob_fingerprint: str,
    object_sha256: str,
    psk: str | None = None,
    flags: int = 0,
    anchor: int | None = None,
) -> bytes:
    tid_b = transfer_id.encode("utf-8")
    blob_b = blob_fingerprint.encode("utf-8")
    obj_b = object_sha256.encode("utf-8")
    psk_b = (psk or "").encode("utf-8")
    # manage anchor flag
    if anchor is not None:
        flags |= PREFACE_FLAG_ANCHOR
    hdr = [MAGIC_PREFACE, struct.pack("!BBHH", VER, flags, channels, channel_id)]
    parts = [
        b"".join(hdr),
        struct.pack("!B", len(tid_b)), tid_b,
        struct.pack("!B", len(blob_b)), blob_b,
        struct.pack("!B", len(obj_b)), obj_b,
        struct.pack("!B", len(psk_b)), psk_b,
    ]
    if (flags & PREFACE_FLAG_ANCHOR) != 0:
        anc_b = int(anchor or 0).to_bytes(8, 'big', signed=False)
        parts += [struct.pack("!B", len(anc_b)), anc_b]
    return b"".join(parts)


def parse_preface(data: bytes) -> dict:
    if len(data) < 4 or data[:4] != MAGIC_PREFACE:
        raise ValueError("bad preface magic")
    off = 4
    if len(data) < off + 6:
        raise ValueError("preface too short")
    ver, flags, channels, ch_id = struct.unpack("!BBHH", data[off:off+6])
    off += 6
    def read_field() -> bytes:
        nonlocal off
        if off >= len(data):
            raise ValueError("preface truncated")
        ln = data[off]
        off += 1
        if off + ln > len(data):
            raise ValueError("preface truncated field")
        b = data[off:off+ln]
        off += ln
        return b
    tid = read_field().decode("utf-8")
    blob = read_field().decode("utf-8")
    obj = read_field().decode("utf-8")
    psk = read_field().decode("utf-8")
    anchor = 0
    # Optional anchor field
    try:
        if (flags & PREFACE_FLAG_ANCHOR) != 0 and off < len(data):
            anc_b = read_field()
            if anc_b and len(anc_b) in (8, 4):
                anchor = int.from_bytes(anc_b, 'big', signed=False)
    except Exception:
        anchor = 0
    return {"version": ver, "flags": flags, "channels": channels, "channel_id": ch_id,
            "transfer_id": tid, "blob": blob, "object": obj, "psk": psk, "anchor": anchor}


# Frame: MAGIC_FRAME[2] SEQ[8] LEN[4] FLAGS[1] PAYLOAD[len]

def build_frames_from_data(data: bytes, start_seq: int = 0, window_size: int = 1024, flags: int = FLAG_DATA) -> bytes:
    out = bytearray()
    seq = start_seq
    for i in range(0, len(data), window_size):
        chunk = data[i:i+window_size]
        out += MAGIC_FRAME
        out += struct.pack("!QIB", seq, len(chunk), flags)
        out += chunk
        seq += 1
    return bytes(out)


def parse_frames_concat(buf: bytes) -> List[Tuple[int, int, bytes]]:
    res: List[Tuple[int, int, bytes]] = []
    off = 0
    while off + 2 + 8 + 4 + 1 <= len(buf):
        if buf[off:off+2] != MAGIC_FRAME:
            raise ValueError("bad frame magic")
        off += 2
        seq, ln, flags = struct.unpack("!QIB", buf[off:off+13])
        off += 13
        if off + ln > len(buf):
            raise ValueError("truncated frame")
        payload = buf[off:off+ln]
        off += ln
        res.append((seq, flags, payload))
    return res

# Control frames as JSON payloads (legacy and WS)
import json as _json

# Binary ctrl types (QUIC optimized)
CTRL_BIN_WIN = 0xA1  # 1 byte type + 4 byte idx
CTRL_BIN_END = 0xA2  # 1 byte type + 4 byte idx + 16 byte hash
CTRL_BIN_DONE = 0xA3 # 1 byte type + 32 byte sha256


def build_ctrl_json_frame(ctrl_type: str, obj: dict) -> bytes:
    payload = dict(obj)
    payload["type"] = ctrl_type
    data = _json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return build_frames_from_data(data, window_size=len(data), flags=FLAG_CTRL)


def build_ctrl_bin_win(idx: int) -> bytes:
    data = bytes([CTRL_BIN_WIN]) + int(idx).to_bytes(4, 'big')
    return build_frames_from_data(data, window_size=len(data), flags=FLAG_CTRL)


def build_ctrl_bin_end(idx: int, hash16: bytes | None = None) -> bytes:
    h = (hash16 or b'\x00' * 16)[:16]
    data = bytes([CTRL_BIN_END]) + int(idx).to_bytes(4, 'big') + h
    return build_frames_from_data(data, window_size=len(data), flags=FLAG_CTRL)


def parse_ctrl_bin(payload: bytes):
    if not payload:
        return None
    t = payload[0]
    if t == CTRL_BIN_WIN and len(payload) == 1 + 4:
        idx = int.from_bytes(payload[1:5], 'big')
        return ('WIN', idx, None)
    if t == CTRL_BIN_END and len(payload) == 1 + 4 + 16:
        idx = int.from_bytes(payload[1:5], 'big')
        h = payload[5:21]
        return ('END', idx, h)
    if t == CTRL_BIN_DONE and len(payload) == 1 + 32:
        sha = payload[1:33].hex()
        return ('DONE', None, sha)
    return None


def is_ctrl(flags: int) -> bool:
    return (flags & FLAG_CTRL) != 0

# Window hashing helpers
import hashlib
from typing import List as _List

def compute_window_hashes(data: bytes, window_size: int = 65536, digest_bytes: int = 16) -> _List[bytes]:
    hashes: _List[bytes] = []
    for i in range(0, len(data), window_size):
        h = hashlib.sha256(data[i:i+window_size]).digest()[:digest_bytes]
        hashes.append(h)
    return hashes


def compute_needed_from_manifest(local_hashes: _List[bytes], remote_hashes: _List[bytes]) -> _List[int]:
    needed: _List[int] = []
    for idx, rh in enumerate(remote_hashes):
        lh = local_hashes[idx] if idx < len(local_hashes) else None
        if lh != rh:
            needed.append(idx)
    return needed


def frames_for_needed_windows(data: bytes, needed: _List[int], window_size: int = 65536, frame_window: int = 1024) -> bytes:
    out = bytearray()
    for widx in needed:
        start = widx * window_size
        end = min(start + window_size, len(data))
        if start >= len(data):
            continue
        out += build_frames_from_data(data[start:end], window_size=frame_window, flags=FLAG_DATA)
    return bytes(out)
