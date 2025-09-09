from dataclasses import dataclass
from typing import Optional

# Minimal protocol wrappers; real implementation will use C extension for speed
try:
    from packetfs import _bitpack
except Exception:  # pragma: no cover
    _bitpack = None

SYNC_MARK = 0xF0  # 1111 0000 (SYNC)
SYNC_ACK  = 0xF1  # 1111 0001 (SYNC-ACK)


def crc16_ccitt(data: bytes, poly: int = 0x1021, init: int = 0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


@dataclass
class SyncConfig:
    window_pow2: int = 16  # 2^16 refs per window by default
    window_crc16: bool = True

class ProtocolEncoder:
    def __init__(self, sync: SyncConfig | None = None):
        self.sync = sync or SyncConfig()
        self.window_mask = (1 << self.sync.window_pow2) - 1
        self.ref_count = 0
        self._tier = -1
        self._win_crc_accum = bytearray()
        self._window_id = 0

    def pack_refs(self, out: bytearray, tier: int, refs: bytes, ref_bits: int) -> int:
        if _bitpack is None:
            raise RuntimeError("C extension _bitpack not available")
        # Accumulate for CRC per window if enabled
        if self.sync.window_crc16:
            self._win_crc_accum += refs
        bits = _bitpack.pack_refs(out, tier, refs, ref_bits)
        # Update ref counter as number of references packed (bytes width)
        width = ref_bits // 8
        self.ref_count = (self.ref_count + (len(refs) // width)) & 0xFFFFFFFF
        return bits

    def maybe_sync(self) -> Optional[bytes]:
        if ((self.ref_count & self.window_mask) == 0) and self.ref_count != 0:
            # Emit SYNC unit: [SYNC_MARK][window_id(2)][crc16(2 optional)]
            pkt = bytearray()
            pkt.append(SYNC_MARK)
            pkt += (self._window_id & 0xFFFF).to_bytes(2, 'big')
            if self.sync.window_crc16:
                crc = crc16_ccitt(bytes(self._win_crc_accum))
                pkt += crc.to_bytes(2, 'big')
                self._win_crc_accum.clear()
            self._window_id = (self._window_id + 1) & 0xFFFF
            return bytes(pkt)
        return None

class ProtocolDecoder:
    def __init__(self, sync: SyncConfig | None = None):
        self.sync = sync or SyncConfig()

    def scan_for_sync(self, payload: bytes) -> Optional[tuple[int, int]]:
        # Naive scan for MVP: look for SYNC_MARK and pull window_id, crc16 (optional)
        try:
            i = payload.index(bytes([SYNC_MARK]))
        except ValueError:
            return None
        # Determine required length based on CRC configuration
        required = 5 if self.sync.window_crc16 else 3
        if len(payload) < i + required:
            return None
        win = int.from_bytes(payload[i+1:i+3], 'big')
        if self.sync.window_crc16:
            crc = int.from_bytes(payload[i+3:i+5], 'big')
        else:
            crc = 0
        return (win, crc)

