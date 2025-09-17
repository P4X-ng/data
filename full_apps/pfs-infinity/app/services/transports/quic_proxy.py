# Simple QUIC proxy that sends a single payload as one stream
import asyncio
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.connection import QuicConnection
from aioquic.tls import SessionTicket
from aioquic.asyncio import connect
from app.services.pvrt_framing import (
    build_preface,
    build_frames_from_data,
    build_ctrl_json_frame,
    build_ctrl_bin_win,
    build_ctrl_bin_end,
    compute_window_hashes,
)

async def send_bytes_quic(host: str, port: int, payload: bytes) -> bool:
    try:
        config = QuicConfiguration(is_client=True, alpn_protocols=["pfs-arith"], verify_mode=False)
        async with connect(host, port, configuration=config) as client:
            quic: QuicConnection = client._quic  # type: ignore
            stream_id = quic.get_next_available_stream_id()
            client._quic.send_stream_data(stream_id, payload, end_stream=True)  # type: ignore
            await client._network_changed()
        return True
    except Exception:
        return False

async def send_plan_quic(host: str, port: int, payload: bytes, transfer_id: str, object_sha: str) -> bool:
    try:
        config = QuicConfiguration(is_client=True, alpn_protocols=["pfs-arith"], verify_mode=False)
        async with connect(host, port, configuration=config) as client:
            quic: QuicConnection = client._quic  # type: ignore
            stream_id = quic.get_next_available_stream_id()
            # Preface
            preface = build_preface(transfer_id, channels=1, channel_id=0,
                                    blob_fingerprint="default", object_sha256=object_sha, psk=None)
            client._quic.send_stream_data(stream_id, preface, end_stream=False)  # type: ignore
            # Manifest
            window_size = 65536
            hashes = compute_window_hashes(payload, window_size=window_size, digest_bytes=16)
            manifest = {
                "algo": "sha256-16",
                "window_size": window_size,
                "total_windows": len(hashes),
                "size": len(payload),
                "hashes": [h.hex() for h in hashes],
            }
            client._quic.send_stream_data(stream_id, build_ctrl_json_frame("MFST", manifest), end_stream=False)  # type: ignore
            await client._network_changed()
            # We can’t reliably await NEED with aioquic here without a dedicated receive loop; assume all windows
            needed = list(range(len(hashes)))
            # Send windows
            from app.services.pvrt_ops import encode_window_ops
            frames_out = bytearray()
            for w in needed:
                # Binary WIN/END controls to reduce overhead
                frames_out += build_ctrl_bin_win(int(w))
                start = w * window_size
                end = min(start + window_size, len(payload))
                bref = [(start, end - start, 0)]
                ops_payload = encode_window_ops(payload[start:end], bref_chunks=bref)
                frames_out += build_frames_from_data(ops_payload, window_size=1024)
                frames_out += build_ctrl_bin_end(int(w), hashes[w])
            frames_out += build_ctrl_json_frame("DONE", {"sha": object_sha, "tw": len(hashes), "ws": window_size})
            client._quic.send_stream_data(stream_id, bytes(frames_out), end_stream=True)  # type: ignore
            await client._network_changed()
        return True
    except Exception:
        return False
