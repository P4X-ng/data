/* Minimal PVRT container helpers (POX1) - BREF and RAW/PROTO */

export const MAGIC = new TextEncoder().encode("POX1");
export const SEC_RAW = 0x01;
export const SEC_PROTO = 0x02;
export const SEC_BREF = 0x03;

export interface BrefChunk { off: bigint; len: number; flags: number }

export function buildContainer(opts: {
  raw?: Uint8Array | null;
  proto?: Uint8Array | null;
  bref?: Array<BrefChunk> | null;
}): Uint8Array {
  const sections: Array<{ type: number; data: Uint8Array }> = [];
  if (opts.raw && opts.raw.length) sections.push({ type: SEC_RAW, data: opts.raw });
  if (opts.proto && opts.proto.length) sections.push({ type: SEC_PROTO, data: opts.proto });
  if (opts.bref && opts.bref.length) {
    // 2 bytes count, then per-chunk: off[8] len[4] flags[1]
    const cnt = Math.min(opts.bref.length, 0xffff);
    const items: Uint8Array[] = [];
    const head = new Uint8Array(2);
    new DataView(head.buffer).setUint16(0, cnt, false);
    items.push(head);
    for (let i = 0; i < cnt; i++) {
      const it = opts.bref[i];
      const b = new Uint8Array(8 + 4 + 1);
      const dv = new DataView(b.buffer);
      // big endian u64 (two's complement for negatives via modulo 2^64)
      const MOD64 = (1n << 64n) - 1n;
      const norm = (it.off & MOD64);
      const hi = Number((norm >> 32n) & 0xffffffffn);
      const lo = Number(norm & 0xffffffffn);
      dv.setUint32(0, hi >>> 0, false);
      dv.setUint32(4, lo >>> 0, false);
      dv.setUint32(8, it.len >>> 0, false);
      dv.setUint8(12, it.flags & 0xff);
      items.push(b);
    }
    const total = items.reduce((a, c) => a + c.length, 0);
    const brefBuf = new Uint8Array(total);
    let off = 0;
    for (const i of items) { brefBuf.set(i, off); off += i.length; }
    sections.push({ type: SEC_BREF, data: brefBuf });
  }
  // Emit
  const parts: Uint8Array[] = [];
  parts.push(MAGIC);
  parts.push(Uint8Array.of(sections.length & 0xff));
  for (const s of sections) {
    const header = new Uint8Array(1 + 4);
    const dv = new DataView(header.buffer);
    header[0] = s.type & 0xff;
    dv.setUint32(1, s.data.length >>> 0, false);
    parts.push(header, s.data);
  }
  const total = parts.reduce((a, c) => a + c.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const p of parts) { out.set(p, off); off += p.length; }
  return out;
}

export function parseContainer(buf: Uint8Array): Map<number, Uint8Array> {
  const dec = new TextDecoder();
  const out = new Map<number, Uint8Array>();
  if (buf.length < 5 || dec.decode(buf.subarray(0, 4)) !== "POX1") return out;
  let off = 4;
  const nsec = buf[off++] ?? 0;
  for (let i = 0; i < nsec; i++) {
    if (off + 5 > buf.length) break;
    const tp = buf[off++];
    const dv = new DataView(buf.buffer, buf.byteOffset + off, buf.length - off);
    const ln = dv.getUint32(0, false);
    off += 4;
    if (off + ln > buf.length) break;
    out.set(tp, buf.subarray(off, off + ln));
    off += ln;
  }
  return out;
}
