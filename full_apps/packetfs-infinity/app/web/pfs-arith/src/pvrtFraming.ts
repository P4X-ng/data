/* PVRT framing + preface (TS mirror of app/services/pvrt_framing.py) */

export const MAGIC_PREFACE = new TextEncoder().encode("PVRT");
export const MAGIC_FRAME = new TextEncoder().encode("PF");
export const VER = 1;

// Flags
export const FLAG_CTRL = 0x01; // control frame carrying JSON or small metadata
export const FLAG_DATA = 0x00; // data frame (PVRT ops / payload)

// Preface flags
export const PREFACE_FLAG_ANCHOR = 0x01;

export interface PrefaceParsed {
  version: number;
  flags: number;
  channels: number;
  channel_id: number;
  transfer_id: string;
  blob: string;
  object: string;
  psk: string;
  anchor: bigint;
}

function beSetU64(view: DataView, offset: number, value: bigint) {
  // Big endian u64
  view.setUint32(offset, Number((value >> 32n) & 0xffffffffn), false);
  view.setUint32(offset + 4, Number(value & 0xffffffffn), false);
}

function beGetU64(view: DataView, offset: number): bigint {
  const hi = BigInt(view.getUint32(offset, false));
  const lo = BigInt(view.getUint32(offset + 4, false));
  return (hi << 32n) | lo;
}

export function buildPreface(opts: {
  transferId: string;
  channels: number;
  channelId: number;
  blob: string; // fingerprint string
  objectSha256: string; // hex
  psk?: string;
  anchor?: bigint | number;
  flags?: number;
}): Uint8Array {
  const enc = new TextEncoder();
  const tid = enc.encode(opts.transferId);
  const blob = enc.encode(opts.blob);
  const obj = enc.encode(opts.objectSha256);
  const psk = enc.encode(opts.psk ?? "");
  const hasAnchor = opts.anchor !== undefined && opts.anchor !== null;
  const flags = (opts.flags ?? 0) | (hasAnchor ? PREFACE_FLAG_ANCHOR : 0);

  // Compute size
  const ancBytes = hasAnchor ? 8 : 0;
  const total =
    MAGIC_PREFACE.length +
    1 + // VER
    1 + // flags
    2 + // channels
    2 + // channel id
    1 + tid.length +
    1 + blob.length +
    1 + obj.length +
    1 + psk.length +
    (hasAnchor ? 1 + ancBytes : 0);

  const buf = new Uint8Array(total);
  let off = 0;
  buf.set(MAGIC_PREFACE, off); off += MAGIC_PREFACE.length;
  buf[off++] = VER & 0xff;
  buf[off++] = flags & 0xff;
  // channels/ch_id big endian
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  dv.setUint16(off, opts.channels & 0xffff, false); off += 2;
  dv.setUint16(off, opts.channelId & 0xffff, false); off += 2;
  // variable fields
  buf[off++] = tid.length & 0xff; buf.set(tid, off); off += tid.length;
  buf[off++] = blob.length & 0xff; buf.set(blob, off); off += blob.length;
  buf[off++] = obj.length & 0xff; buf.set(obj, off); off += obj.length;
  buf[off++] = psk.length & 0xff; buf.set(psk, off); off += psk.length;
  if (hasAnchor) {
    const anchor = BigInt(opts.anchor as any);
    buf[off++] = 8; // length of anchor field
    const dv2 = new DataView(buf.buffer, buf.byteOffset + off, 8);
    // anchor is unsigned in preface (same as python implementation)
    beSetU64(dv2, 0, anchor);
    off += 8;
  }
  return buf;
}

export function parsePreface(data: Uint8Array): PrefaceParsed {
  const dec = new TextDecoder();
  if (data.byteLength < 6) throw new Error("preface too short");
  if (dec.decode(data.subarray(0, 4)) !== "PVRT") throw new Error("bad preface magic");
  let off = 4;
  const dv = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const ver = data[off++];
  const flags = data[off++];
  const channels = dv.getUint16(off, false); off += 2;
  const channel_id = dv.getUint16(off, false); off += 2;
  function readField(): Uint8Array {
    if (off >= data.length) throw new Error("preface truncated");
    const ln = data[off++];
    if (off + ln > data.length) throw new Error("preface truncated field");
    const b = data.subarray(off, off + ln);
    off += ln;
    return b;
  }
  const transfer_id = new TextDecoder().decode(readField());
  const blob = new TextDecoder().decode(readField());
  const object = new TextDecoder().decode(readField());
  const psk = new TextDecoder().decode(readField());
  let anchor = 0n;
  if ((flags & PREFACE_FLAG_ANCHOR) !== 0 && off < data.length) {
    const ancLen = data[off++];
    if (ancLen === 8 && off + 8 <= data.length) {
      const dvAnc = new DataView(data.buffer, data.byteOffset + off, 8);
      anchor = beGetU64(dvAnc, 0);
      off += 8;
    }
  }
  return { version: ver, flags, channels, channel_id, transfer_id, blob, object, psk, anchor };
}

// Frame: MAGIC_FRAME[2] SEQ[8] LEN[4] FLAGS[1] PAYLOAD[len]
export interface ParsedFrame { seq: bigint; flags: number; payload: Uint8Array }

export function buildFramesFromData(data: Uint8Array, opts?: { startSeq?: bigint; windowSize?: number; flags?: number }): Uint8Array {
  const startSeq = opts?.startSeq ?? 0n;
  const windowSize = opts?.windowSize ?? 1024;
  const flags = opts?.flags ?? FLAG_DATA;
  let seq = startSeq;
  const chunks: Uint8Array[] = [];
  for (let i = 0; i < data.length; i += windowSize) {
    const chunk = data.subarray(i, Math.min(i + windowSize, data.length));
    const header = new Uint8Array(2 + 8 + 4 + 1);
    header.set(MAGIC_FRAME, 0);
    const dv = new DataView(header.buffer, header.byteOffset, header.byteLength);
    beSetU64(dv, 2, seq);
    dv.setUint32(10, chunk.length >>> 0, false);
    header[14] = flags & 0xff;
    chunks.push(header, chunk);
    seq += 1n;
  }
  const total = chunks.reduce((a, b) => a + b.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) { out.set(c, off); off += c.length; }
  return out;
}

export function parseFramesConcat(buf: Uint8Array): ParsedFrame[] {
  const dec = new TextDecoder();
  const res: ParsedFrame[] = [];
  let off = 0;
  while (off + 15 <= buf.length) {
    if (dec.decode(buf.subarray(off, off + 2)) !== "PF") throw new Error("bad frame magic");
    const dv = new DataView(buf.buffer, buf.byteOffset + off, buf.length - off);
    const seq = beGetU64(dv, 2);
    const ln = dv.getUint32(10, false);
    const flags = dv.getUint8(14);
    off += 15;
    if (off + ln > buf.length) throw new Error("truncated frame");
    const payload = buf.subarray(off, off + ln);
    off += ln;
    res.push({ seq, flags, payload });
  }
  return res;
}

export function buildCtrlJsonFrame(type: string, obj: Record<string, unknown>): Uint8Array {
  const body = new TextEncoder().encode(JSON.stringify({ ...obj, type }));
  return buildFramesFromData(body, { windowSize: body.length, flags: FLAG_CTRL });
}

// Binary ctrl types
export const CTRL_BIN_WIN = 0xa1;
export const CTRL_BIN_END = 0xa2; // + 16 bytes hash
export const CTRL_BIN_DONE = 0xa3; // + 32 byte sha256

export function buildCtrlBinWin(idx: number): Uint8Array {
  const b = new Uint8Array(1 + 4);
  const dv = new DataView(b.buffer);
  b[0] = CTRL_BIN_WIN;
  dv.setUint32(1, idx >>> 0, false);
  return buildFramesFromData(b, { windowSize: b.length, flags: FLAG_CTRL });
}

export function buildCtrlBinEnd(idx: number, hash16?: Uint8Array): Uint8Array {
  const h = hash16 && hash16.length ? hash16.slice(0, 16) : new Uint8Array(16);
  const b = new Uint8Array(1 + 4 + 16);
  const dv = new DataView(b.buffer);
  b[0] = CTRL_BIN_END;
  dv.setUint32(1, idx >>> 0, false);
  b.set(h, 5);
  return buildFramesFromData(b, { windowSize: b.length, flags: FLAG_CTRL });
}

export function buildCtrlBinDone(sha256: Uint8Array): Uint8Array {
  const b = new Uint8Array(1 + 32);
  b[0] = CTRL_BIN_DONE;
  b.set(sha256.slice(0, 32), 1);
  return buildFramesFromData(b, { windowSize: b.length, flags: FLAG_CTRL });
}

export function parseCtrlBin(payload: Uint8Array): ["WIN", number, null] | ["END", number, Uint8Array] | ["DONE", null, string] | null {
  if (!payload || payload.length < 1) return null;
  const t = payload[0];
  if (t === CTRL_BIN_WIN && payload.length === 1 + 4) {
    const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
    const idx = dv.getUint32(1, false);
    return ["WIN", idx, null];
  }
  if (t === CTRL_BIN_END && payload.length === 1 + 4 + 16) {
    const dv = new DataView(payload.buffer, payload.byteOffset, payload.byteLength);
    const idx = dv.getUint32(1, false);
    return ["END", idx, payload.subarray(5, 21)];
  }
  if (t === CTRL_BIN_DONE && payload.length === 1 + 32) {
    const sha = bytesToHex(payload.subarray(1, 33));
    return ["DONE", null, sha];
  }
  return null;
}

export function isCtrl(flags: number): boolean {
  return (flags & FLAG_CTRL) !== 0;
}

function bytesToHex(b: Uint8Array): string {
  return Array.from(b).map((x) => x.toString(16).padStart(2, "0")).join("");
}
