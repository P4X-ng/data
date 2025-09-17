# Minimal placeholder for PVRT arithmetic ops per window
# For now, we just return the raw window bytes as the "ops" payload.
# Replace with real PacketFS encoder output.

OP_LIT = 0x01
OP_END = 0xFF

# Container magic and sections for carrying both RAW and PROTO ops
MAGIC = b'POX1'
SEC_RAW = 0x01
SEC_PROTO = 0x02
SEC_BREF = 0x03

# Encode ops for a window:
# - try to generate a PROTO section using PacketFS ProtocolEncoder (_bitpack)
# - always include a RAW section for debug/compat decode
# Container: MAGIC | NSEC(1) | [TYPE(1) LEN(4) DATA...] * NSEC

def encode_window_ops(window_bytes: bytes, bref_chunks: list[tuple[int,int,int]] | None = None) -> bytes:
    sections = []
    # RAW section
    sections.append((SEC_RAW, window_bytes))
    # PROTO section (best effort)
    try:
        from packetfs.protocol import ProtocolEncoder, SyncConfig  # type: ignore
        enc = ProtocolEncoder(SyncConfig())
        out = bytearray()
        # Pack 8-bit refs directly from window bytes
        enc.pack_refs(out, 0, window_bytes, 8)
        # Final sync if due
        sync = enc.maybe_sync()
        if sync:
            out.extend(sync)
        sections.append((SEC_PROTO, bytes(out)))
    except Exception:
        pass
    # BREF section (offset,len,flags)
    if bref_chunks:
        b = bytearray()
        cnt = len(bref_chunks) & 0xFFFF
        b += cnt.to_bytes(2, 'big')
        for off, ln, fl in bref_chunks:
            b += int(off).to_bytes(8, 'big')
            b += int(ln).to_bytes(4, 'big')
            b += int(fl & 0xFF).to_bytes(1, 'big')
        sections.append((SEC_BREF, bytes(b)))
    # Build container
    buf = bytearray()
    buf += MAGIC
    buf.append(len(sections) & 0xFF)
    for t, data in sections:
        buf.append(t & 0xFF)
        buf += len(data).to_bytes(4, 'big')
        buf += data
    return bytes(buf)

# Decode the ops container; prefer RAW section for debug assembly
# Fallback: support legacy LIT/END program

def extract_sections(ops: bytes) -> dict[int, bytes]:
    sections: dict[int, bytes] = {}
    try:
        if len(ops) >= 5 and ops[:4] == MAGIC:
            i = 4
            nsec = ops[i]
            i += 1
            for _ in range(nsec):
                if i + 5 > len(ops):
                    break
                tp = ops[i]
                ln = int.from_bytes(ops[i+1:i+5], 'big')
                i += 5
                if i + ln > len(ops):
                    break
                data = ops[i:i+ln]
                i += ln
                sections[tp] = data
    except Exception:
        pass
    return sections

# Execute PROTO window against a preshared blob (placeholder)
# Returns reconstructed bytes if supported, else None.
# TODO: integrate real reconstructor here once exposed (native or Python layer).

def execute_proto_window(proto: bytes, blob_meta: dict) -> bytes | None:
    try:
        # If BREF is present, reconstruct by reading from blob
        secs = extract_sections(proto)
        bref = secs.get(SEC_BREF)
        if bref and blob_meta.get("name"):
            # Parse BREF
            if len(bref) < 2:
                return None
            cnt = int.from_bytes(bref[0:2], 'big')
            i = 2
            chunks = []
            for _ in range(cnt):
                if i + 13 > len(bref):
                    break
                off = int.from_bytes(bref[i:i+8], 'big'); i += 8
                ln = int.from_bytes(bref[i:i+4], 'big'); i += 4
                fl = bref[i]; i += 1
                chunks.append((off, ln, fl))
            # Read from VirtualBlob
            from packetfs.filesystem.virtual_blob import VirtualBlob  # type: ignore
            vb = VirtualBlob(name=str(blob_meta["name"]), size_bytes=int(blob_meta.get("size", 0) or 0), seed=int(blob_meta.get("seed", 0) or 0))
            vb.create_or_attach(create=False)
            out = bytearray()
            for off, ln, fl in chunks:
                if ln <= 0:
                    continue
                out += vb.read(off, ln)
            vb.close()
            return bytes(out)
    except Exception:
        return None
    return None


def decode_window_ops(ops: bytes) -> bytes:
    try:
        if len(ops) >= 5 and ops[:4] == MAGIC:
            i = 4
            nsec = ops[i]
            i += 1
            raw = None
            for _ in range(nsec):
                if i + 5 > len(ops):
                    break
                tp = ops[i]
                ln = int.from_bytes(ops[i+1:i+5], 'big')
                i += 5
                if i + ln > len(ops):
                    break
                data = ops[i:i+ln]
                i += ln
                if tp == SEC_RAW:
                    raw = data
            if raw is not None:
                return bytes(raw)
            # No RAW, return empty
            return b''
    except Exception:
        pass
    # Legacy LIT/END decode fallback
    out = bytearray()
    i = 0
    n = len(ops)
    while i < n:
        op = ops[i]
        i += 1
        if op == OP_LIT:
            if i + 4 > n:
                break
            ln = int.from_bytes(ops[i:i+4], 'big')
            i += 4
            if i + ln > n:
                break
            out += ops[i:i+ln]
            i += ln
        elif op == OP_END:
            break
        else:
            break
    return bytes(out)
