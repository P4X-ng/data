from __future__ import annotations

import asyncio
import os
from typing import Optional, Dict

from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, QuicEvent

from app.services.pvrt_framing import parse_preface, parse_frames_concat, is_ctrl
from app.services.pvrt_ops import extract_sections, SEC_RAW, SEC_PROTO
import hashlib

class PfsQuicProtocol(QuicConnectionProtocol):
    def __init__(self, *args, app_state=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._streams: Dict[int, bytearray] = {}
        self.app_state = app_state or {}

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            buf = self._streams.setdefault(event.stream_id, bytearray())
            buf += event.data
            if event.end_stream:
                asyncio.create_task(self._handle_stream(event.stream_id, bytes(buf)))

    async def _handle_stream(self, stream_id: int, data: bytes):
        try:
            # Expect preface first, then frames
            if len(data) < 4:
                return
            # Preface is at the start; parse it
            preface = parse_preface(data)
            # Remaining bytes are frames (for simplicity, assume rest after preface length)
            # Our preface is variable; recompute by re-encoding fields we parsed to find offset
            # Instead, attempt frames parsing from the end backwards until valid; fallback to scanning from after first control
            # For now, assume client sent preface and then a single frames buffer event after
            # Try parsing frames from the tail of data (after 4 + variable fields)
            # We search for the first frame magic 'PF' starting at some offset
            off = 0
            while off + 2 <= len(data) and data[off:off+2] != b'PF':
                off += 1
            frames = parse_frames_concat(data[off:])
            # Aggregate windows similar to WS handler
            agg_windows: Dict[int, bytearray] = {}
            current_win = None
            for (_seq, fl, payload) in frames:
                if is_ctrl(fl):
                    # Try binary control first
                    from app.services.pvrt_framing import parse_ctrl_bin
                    parsed = parse_ctrl_bin(payload)
                    if parsed:
                        t, idx, extra = parsed
                        if t == 'WIN':
                            current_win = int(idx)
                            agg_windows.setdefault(current_win, bytearray())
                        elif t == 'END':
                            # hash16 in 'extra' if needed
                            pass
                        elif t == 'DONE':
                            pass
                        continue
                    # Fallback to JSON control
                    try:
                        import json as _json
                        ctrl = _json.loads(payload.decode('utf-8'))
                        t = ctrl.get('type')
                        if t == 'WIN':
                            current_win = int(ctrl.get('idx', 0))
                            agg_windows.setdefault(current_win, bytearray())
                        elif t == 'END':
                            pass
                        elif t == 'DONE':
                            pass
                    except Exception:
                        continue
                else:
                    if current_win is not None:
                        agg_windows.setdefault(current_win, bytearray()).extend(payload)
            # Reconstruct and basic validation
            # Access CURRENT_BLOB from app state
            CURRENT_BLOB = self.app_state.get('CURRENT_BLOB', {})
            for widx, buf in agg_windows.items():
                secs = extract_sections(bytes(buf))
                raw = secs.get(SEC_RAW)
                proto = secs.get(SEC_PROTO)
                win_bytes = bytes(raw or b"")
                if proto is not None and CURRENT_BLOB:
                    from app.services.pvrt_ops import execute_proto_window
                    vb_meta = {"name": CURRENT_BLOB.get("name"), "size": CURRENT_BLOB.get("size"), "seed": CURRENT_BLOB.get("seed")}
                    recon = execute_proto_window(bytes(buf), vb_meta)
                    if recon is not None and len(recon) > 0:
                        win_bytes = recon
                # we could store or discard; for now, just acknowledge
            # Send ack 'done' back on the same stream
            try:
                self._quic.send_stream_data(stream_id, b'done', end_stream=True)
                await self._network_changed()
            except Exception:
                pass
        except Exception:
            # swallow errors for robustness in dev
            pass

async def run_quic_server(host: str, port: int, cert: str, key: str, app_state: dict):
    cfg = QuicConfiguration(is_client=False, alpn_protocols=["pfs-arith"])
    cfg.load_cert_chain(certfile=cert, keyfile=key)
    await serve(host, port, configuration=cfg, create_protocol=lambda *a, **kw: PfsQuicProtocol(*a, app_state=app_state, **kw))