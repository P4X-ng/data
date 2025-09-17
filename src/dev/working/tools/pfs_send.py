import argparse
import os
import sys
import struct
from packetfs.rawio import send_frames
from packetfs.seed_pool import SeedPool
from packetfs.protocol import ProtocolEncoder, SyncConfig

# For MVP, generate dummy refs for tiers and pack them via the C extension
try:
    from packetfs import _bitpack
except Exception:
    _bitpack = None


def gen_payload(enc: ProtocolEncoder):
    # Minimal demo: set tier L1 and emit 64 sequential 1-byte refs, then maybe a SYNC unit
    out = bytearray(1500)
    refs = bytes(range(64))
    if _bitpack is None:
        raise SystemExit("C extension not built. Run: pip install -e .")
    bits = enc.pack_refs(out, 0, refs, 8)
    extra = enc.maybe_sync()
    nbytes = (bits + 7) // 8
    payload = bytearray(out[:nbytes])
    if extra:
        # Append control bytes; in a real encoder, these would be bit-packed
        payload += extra
    return bytes(payload)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", required=True)
    ap.add_argument("--seeds", default="seeds.txt")
    args = ap.parse_args()

    if not os.path.exists(args.seeds):
        print(f"Warning: {args.seeds} not found; proceeding with demo.")
    else:
        SeedPool.from_file(args.seeds)

    enc = ProtocolEncoder(SyncConfig(window_pow2=16, window_crc16=True))
    payloads = (gen_payload(enc) for _ in range(100))
    send_frames(args.iface, payloads)
    print("Sent 100 demo frames.")


if __name__ == "__main__":
    main()
