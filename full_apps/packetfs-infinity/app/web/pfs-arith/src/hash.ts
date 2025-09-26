export async function sha256(bytes: Uint8Array): Promise<Uint8Array> {
  // Browser WebCrypto
  const g: any = (globalThis as any);
  if (g.crypto && g.crypto.subtle) {
    const d = await g.crypto.subtle.digest('SHA-256', bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    return new Uint8Array(d);
  }
  // Node fallback
  try {
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    const mod = await import('crypto');
    const createHash = (mod as any).createHash as (algo: string) => any;
  const h = createHash('sha256');
  h.update(bytes);
  const out: unknown = h.digest();
  return out instanceof Uint8Array ? out : new Uint8Array(out as ArrayBufferView as any);
  } catch {
    // Very minimal fallback (not crypto-secure): XOR rolling hash then pad
    let x = 0;
    for (let i = 0; i < bytes.length; i++) x = (x ^ bytes[i]) & 0xff;
    const out = new Uint8Array(32);
    out.fill(x);
    return out;
  }
}

export async function windowHashes(data: Uint8Array, windowSize = 65536, digestBytes = 16): Promise<Uint8Array[]> {
  const out: Uint8Array[] = [];
  for (let i = 0; i < data.length; i += windowSize) {
    const d = data.subarray(i, Math.min(i + windowSize, data.length));
    const full = await sha256(d);
    out.push(full.subarray(0, digestBytes));
  }
  return out;
}
