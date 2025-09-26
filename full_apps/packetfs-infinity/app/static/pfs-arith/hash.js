export async function sha256(bytes) {
    // Browser WebCrypto
    const g = globalThis;
    if (g.crypto && g.crypto.subtle) {
        const d = await g.crypto.subtle.digest('SHA-256', bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
        return new Uint8Array(d);
    }
    // Node fallback
    try {
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-ignore
        const mod = await import('crypto');
        const createHash = mod.createHash;
        const h = createHash('sha256');
        h.update(bytes);
        const out = h.digest();
        return out instanceof Uint8Array ? out : new Uint8Array(out);
    }
    catch {
        // Very minimal fallback (not crypto-secure): XOR rolling hash then pad
        let x = 0;
        for (let i = 0; i < bytes.length; i++)
            x = (x ^ bytes[i]) & 0xff;
        const out = new Uint8Array(32);
        out.fill(x);
        return out;
    }
}
export async function windowHashes(data, windowSize = 65536, digestBytes = 16) {
    const out = [];
    for (let i = 0; i < data.length; i += windowSize) {
        const d = data.subarray(i, Math.min(i + windowSize, data.length));
        const full = await sha256(d);
        out.push(full.subarray(0, digestBytes));
    }
    return out;
}
