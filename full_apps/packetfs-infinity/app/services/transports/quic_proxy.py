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

async def send_iprog_quic(host: str, port: int, iprog: dict, transfer_id: str) -> bool:
    try:
        config = QuicConfiguration(is_client=True, alpn_protocols=["pfs-arith"], verify_mode=False)
        async with connect(host, port, configuration=config) as client:
            quic: QuicConnection = client._quic  # type: ignore
            stream_id = quic.get_next_available_stream_id()
            # Preface with anchor
            blob = iprog.get("blob", {})
            blob_name = blob.get('name','')
            blob_size = int(blob.get('size','0') or 0)
            blob_seed = int(blob.get('seed','0') or 0)
            blob_fp = f"{blob_name}:{blob_size}:{blob_seed}"
            sha = str(iprog.get("sha256", ""))
            anchor = blob_size // 2 if blob_size > 0 else 0
            preface = build_preface(transfer_id, channels=1, channel_id=0,
                                    blob_fingerprint=blob_fp, object_sha256=sha, psk=None, anchor=anchor)
            import os as _os
            use_arith = _os.environ.get('PFS_ARITH', '1') in ('1','true','TRUE','True')
            client._quic.send_stream_data(stream_id, preface, end_stream=False)  # type: ignore
            # Manifest
            window_size = int(iprog.get("window_size", 65536))
            windows = iprog.get("windows", [])
            manifest = {
                "algo": "sha256-16",
                "window_size": window_size,
                "total_windows": len(windows),
                "hashes": [w.get("hash16", "") for w in windows],
            }
            client._quic.send_stream_data(stream_id, build_ctrl_json_frame("MFST", manifest), end_stream=False)  # type: ignore
            # Send windows with relative BREF
            from packetfs.filesystem.pvrt_container import build_container  # type: ignore
            frames = bytearray()
            for w in windows:
                idx = int(w.get("idx", 0))
                frames += build_ctrl_bin_win(idx)
                bref = w.get("bref") or []
                if bref:
                    if use_arith:
                        rel_chunks = []
                        for (o,l,f) in bref:
                            delta = int(o) - anchor
                            rel_chunks.append((int(delta) & ((1<<64)-1), int(l), int(f) | 0x01))
                        pvrt = build_container(proto=None, bref_chunks=rel_chunks)
                    else:
                        pvrt = build_container(proto=None, bref_chunks=[(int(o), int(l), int(f) & ~0x01) for (o,l,f) in bref])
                    frames += build_frames_from_data(pvrt, window_size=1024)
                frames += build_ctrl_bin_end(idx, bytes.fromhex(w.get("hash16","00"*16)) if w.get("hash16") else None)
            from app.services.pvrt_framing import build_ctrl_json_frame as _build_done
            frames += _build_done("DONE", {"sha": sha, "tw": len(windows), "ws": window_size})
            client._quic.send_stream_data(stream_id, bytes(frames), end_stream=True)  # type: ignore
            await client._network_changed()
        return True
    except Exception:
        return False
