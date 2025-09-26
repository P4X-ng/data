from __future__ import annotations
import asyncio
from typing import Dict, Tuple

from app.services.pvrt_framing import parse_preface, parse_frames_concat, is_ctrl, build_ctrl_json_frame
from app.services.pvrt_framing import parse_ctrl_bin  # reuse ctrl parser
from app.services.pvrt_ops import extract_sections, SEC_RAW, SEC_PROTO
import hashlib

MAGIC = b"PVU1"
T_PREFACE = 0x01
T_WIN = 0x10
T_PVRT = 0x11
T_END = 0x12
T_DONE = 0x13
T_ACK = 0xE0

class UdpOffsetsProtocol(asyncio.DatagramProtocol):
    def __init__(self, app_state: dict):
        self.app_state = app_state
        self.addr_last_tid: Dict[Tuple[str,int], str] = {}
        self.sessions: Dict[str, dict] = {}

    def datagram_received(self, data: bytes, addr):  # type: ignore[override]
        try:
            if len(data) < 5 or data[:4] != MAGIC:
                return
            t = data[4]
            off = 5
            if t == T_PREFACE:
                # MAGIC | T | tl | tid | bl | blob | sl | sha | anchor(8) | ws(4) | tw(4)
                if off >= len(data):
                    return
                tl = data[off]; off += 1
                tid = data[off:off+tl].decode('utf-8', errors='ignore'); off += tl
                bl = data[off]; off += 1
                blob_fp = data[off:off+bl].decode('utf-8', errors='ignore'); off += bl
                sl = data[off]; off += 1
                sha = data[off:off+sl].decode('utf-8', errors='ignore'); off += sl
                if off + 8 + 4 + 4 > len(data):
                    return
                anchor = int.from_bytes(data[off:off+8], 'big'); off += 8
                ws = int.from_bytes(data[off:off+4], 'big'); off += 4
                tw = int.from_bytes(data[off:off+4], 'big'); off += 4
                self.addr_last_tid[addr] = tid
                self.sessions[tid] = {
                    'anchor': anchor,
                    'ws': ws,
                    'tw': tw,
                    'sha': sha,
                    'windows': {},
                }
                return
            # Look up session by last preface from this addr
            tid = self.addr_last_tid.get(addr)
            if not tid:
                return
            sess = self.sessions.get(tid)
            if not sess:
                return
            if t == T_WIN:
                # we don't track current window for UDP; pvrt packet carries idx
                return
            if t == T_PVRT:
                if off + 4 > len(data):
                    return
                idx = int.from_bytes(data[off:off+4], 'big'); off += 4
                pvrt = data[off:]
                # Reconstruct from CURRENT_BLOB
                CURRENT_BLOB = (self.app_state or {}).get('CURRENT_BLOB', {}) or {}
                vb = CURRENT_BLOB.get('vb') if isinstance(CURRENT_BLOB, dict) else None
                if vb is None:
                    return
                try:
                    from packetfs.filesystem.pvrt_container import parse_container, SEC_BREF  # type: ignore
                    secs = parse_container(pvrt)
                    bref = secs.get(SEC_BREF)
                    out = bytearray()
                    if bref and len(bref) >= 2:
                        i2 = 2
                        cnt = int.from_bytes(bref[0:2], 'big')
                        anchor = int(sess.get('anchor', 0))
                        size = int(CURRENT_BLOB.get('size', getattr(vb, 'size', 0)))
                        for _ in range(cnt):
                            if i2 + 13 > len(bref): break
                            off_b = bref[i2:i2+8]; i2 += 8
                            ln = int.from_bytes(bref[i2:i2+4], 'big'); i2 += 4
                            fl = bref[i2]; i2 += 1
                            if ln <= 0: continue
                            if (fl & 0x01) != 0:
                                delta = int.from_bytes(off_b, 'big', signed=True)
                                o = (anchor + delta) % max(1, size)
                            else:
                                o = int.from_bytes(off_b, 'big', signed=False)
                            out += vb.read(o, ln)
                        sess['windows'][idx] = bytes(out)
                except Exception:
                    return
                return
            if t == T_END:
                # ignore; optional hash check could be added
                return
            if t == T_DONE:
                # Assemble and store
                win = sess.get('windows', {})
                tw = int(sess.get('tw', 0))
                ws = int(sess.get('ws', 65536))
                assembled = bytearray()
                for w in range(tw):
                    assembled.extend(win.get(w, b""))
                sha = sess.get('sha') or ''
                from app.core.state import BLUEPRINTS
                BLUEPRINTS[f"recv:{sha}"] = {
                    'version': 1,
                    'size': len(assembled),
                    'sha256': hashlib.sha256(assembled).hexdigest(),
                    'windows': sorted(list(win.keys())),
                    'bytes': bytes(assembled),
                }
                # ACK
                try:
                    ack = MAGIC + bytes([T_ACK])
                    self.transport.sendto(ack, addr)  # type: ignore[attr-defined]
                except Exception:
                    pass
                # cleanup
                self.sessions.pop(tid, None)
                return
        except Exception:
            return

async def run_udp_offsets_server(host: str, port: int, app_state: dict):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(lambda: UdpOffsetsProtocol(app_state), local_addr=(host, port))
    try:
        await asyncio.sleep(1e9)  # run forever
    finally:
        transport.close()