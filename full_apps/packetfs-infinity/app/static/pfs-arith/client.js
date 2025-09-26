import { buildPreface, buildCtrlJsonFrame, buildFramesFromData, buildCtrlBinWin, buildCtrlBinEnd } from './pvrtFraming.js';
import { buildContainer } from './pvrtContainer.js';
export class PfsArithClient {
    constructor(wsFactory) {
        this.wsFactory = wsFactory;
    }
    // Single-WS arithmetic send (uses binary WIN/END controls + relative BREF)
    async sendIprog(url, iprog, transferId) {
        const ws = this.wsFactory(url);
        const t0 = Date.now();
        let bytesSent = 0;
        const blob = iprog.blob;
        const fp = `${blob.name}:${blob.size}:${blob.seed}`;
        const anchor = BigInt(Math.floor((blob.size || 0) / 2));
        const preface = buildPreface({
            transferId,
            channels: 1,
            channelId: 0,
            blob: fp,
            objectSha256: iprog.sha256,
            psk: undefined,
            anchor
        });
        await ws.send(preface);
        bytesSent += preface.length;
        // Manifest
        const windowSize = iprog.window_size || 65536;
        const hashes = iprog.windows.map(w => w.hash16 ? hexToBytes(w.hash16) : new Uint8Array(16));
        const manifest = { algo: 'sha256-16', window_size: windowSize, total_windows: iprog.windows.length, hashes: hashes.map(h => bytesToHex(h)) };
        const mf = buildCtrlJsonFrame('MFST', manifest);
        await ws.send(mf);
        bytesSent += mf.length;
        // NEED (optional)
        const needMsg = await ws.recvJson(2500).catch(() => ({ needed: iprog.windows.map(w => w.idx) }));
        const needed = Array.isArray(needMsg?.needed) ? needMsg.needed.map((x) => Number(x)) : iprog.windows.map(w => w.idx);
        // Send frames for needed windows (binary controls)
        const frames = [];
        for (const w of iprog.windows) {
            if (!needed.includes(w.idx))
                continue;
            frames.push(buildCtrlBinWin(w.idx));
            let payload = null;
            if (w.pvrt) {
                payload = base64ToBytes(w.pvrt);
            }
            else if (w.bref && w.bref.length) {
                const rel = w.bref.map(([off, len, fl]) => ({ off: BigInt(off) - anchor, len, flags: (fl | 0x01) }));
                payload = buildContainer({ proto: null, raw: null, bref: rel });
            }
            else {
                payload = new Uint8Array(0);
            }
            if (payload && payload.length)
                frames.push(buildFramesFromData(payload, { windowSize: 1024 }));
            frames.push(buildCtrlBinEnd(w.idx, hashes[w.idx] || new Uint8Array(16)));
        }
        // DONE (binary or JSON; we send JSON for compatibility and keep binary helper available)
        frames.push(buildCtrlJsonFrame('DONE', { sha: iprog.sha256, tw: iprog.windows.length, ws: windowSize }));
        const bundle = concat(frames);
        await ws.send(bundle);
        bytesSent += bundle.length;
        // Ack
        const ack = await ws.recvText(10000).catch(() => '');
        const ok = typeof ack === 'string' && (ack.toLowerCase().startsWith('done') || ack.toLowerCase().startsWith('ok'));
        const elapsedS = Math.max((Date.now() - t0) / 1000, 0.000001);
        return { ok, bytesSent, elapsedS };
    }
    // Multi-WS arithmetic send (default 4 channels). Channel 0 sends MFST/NEED and DONE; others send WIN/PVRT/END only.
    async sendIprogMulti(url, iprog, transferId, channels = 4) {
        if (channels <= 1)
            return this.sendIprog(url, iprog, transferId);
        const t0 = Date.now();
        const blob = iprog.blob;
        const fp = `${blob.name}:${blob.size}:${blob.seed}`;
        const anchor = BigInt(Math.floor((blob.size || 0) / 2));
        const windowSize = iprog.window_size || 65536;
        const hashes = iprog.windows.map(w => w.hash16 ? hexToBytes(w.hash16) : new Uint8Array(16));
        const wses = new Array(channels).fill(0).map(() => this.wsFactory(url));
        let bytesSent = 0;
        // Prefaces
        await Promise.all(wses.map((ws, i) => {
            const preface = buildPreface({
                transferId,
                channels,
                channelId: i,
                blob: fp,
                objectSha256: iprog.sha256,
                psk: undefined,
                anchor
            });
            bytesSent += preface.length;
            return ws.send(preface);
        }));
        // Channel 0 sends MFST and gets NEED
        const mf = buildCtrlJsonFrame('MFST', { algo: 'sha256-16', window_size: windowSize, total_windows: iprog.windows.length, hashes: hashes.map(h => bytesToHex(h)) });
        await wses[0].send(mf);
        bytesSent += mf.length;
        const needMsg = await wses[0].recvJson(2500).catch(() => ({ needed: iprog.windows.map(w => w.idx) }));
        const needed = Array.isArray(needMsg?.needed) ? needMsg.needed.map((x) => Number(x)) : iprog.windows.map(w => w.idx);
        // Distribute needed window indices round-robin across channels
        const buckets = Array.from({ length: channels }, () => []);
        needed.forEach((widx, i) => { buckets[i % channels].push(widx); });
        function framesForBucket(bucket) {
            const out = [];
            for (const idx of bucket) {
                out.push(buildCtrlBinWin(idx));
                const w = iprog.windows[idx];
                let payload = null;
                if (w && w.pvrt) {
                    payload = base64ToBytes(w.pvrt);
                }
                else if (w && w.bref && w.bref.length) {
                    const rel = w.bref.map(([off, len, fl]) => ({ off: BigInt(off) - anchor, len, flags: (fl | 0x01) }));
                    payload = buildContainer({ proto: null, raw: null, bref: rel });
                }
                else {
                    payload = new Uint8Array(0);
                }
                if (payload && payload.length)
                    out.push(buildFramesFromData(payload, { windowSize: 1024 }));
                out.push(buildCtrlBinEnd(idx, hashes[idx] || new Uint8Array(16)));
            }
            return concat(out);
        }
        // Send across channels; ch0 appends DONE
        await Promise.all(wses.map(async (ws, i) => {
            const frames = framesForBucket(buckets[i]);
            if (frames.length) {
                await ws.send(frames);
                bytesSent += frames.length;
            }
            if (i === 0) {
                const done = buildCtrlJsonFrame('DONE', { sha: iprog.sha256, tw: iprog.windows.length, ws: windowSize });
                await ws.send(done);
                bytesSent += done.length;
            }
        }));
        // Acks: ch0 expects 'done' or 'ok'; others expect 'ok'
        const acks = await Promise.all(wses.map(async (ws, i) => {
            const t = await ws.recvText(15000).catch(() => '');
            const ok = typeof t === 'string' && (i === 0 ? (t.toLowerCase().startsWith('done') || t.toLowerCase().startsWith('ok')) : t.toLowerCase().startsWith('ok'));
            return ok;
        }));
        const ok = acks.every(Boolean);
        const elapsedS = Math.max((Date.now() - t0) / 1000, 0.000001);
        return { ok, bytesSent, elapsedS };
    }
}
// Lightweight WebSocket abstraction for browser/node
// WebSocketLike is defined in wsAdapters.ts
// Utils
function concat(chunks) {
    const total = chunks.reduce((a, c) => a + c.length, 0);
    const out = new Uint8Array(total);
    let off = 0;
    for (const c of chunks) {
        out.set(c, off);
        off += c.length;
    }
    return out;
}
function hexToBytes(hex) {
    const clean = (hex || '').replace(/[^0-9a-f]/gi, '');
    const out = new Uint8Array(clean.length / 2);
    for (let i = 0; i < out.length; i++)
        out[i] = parseInt(clean.substr(i * 2, 2), 16) & 0xff;
    return out;
}
function bytesToHex(b) {
    return Array.from(b).map(x => x.toString(16).padStart(2, '0')).join('');
}
function base64ToBytes(b64) {
    if (typeof atob === 'function') {
        const bin = atob(b64);
        const out = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++)
            out[i] = bin.charCodeAt(i);
        return out;
    }
    // Node
    const g = globalThis;
    if (g.Buffer && typeof g.Buffer.from === 'function') {
        const buf = g.Buffer.from(b64, 'base64');
        return new Uint8Array(buf.buffer, buf.byteOffset, buf.byteLength);
    }
    // Fallback: decode via URL API
    const text = decodeURIComponent(Array.prototype.map
        .call(b64.replace(/\s+/g, ''), (c) => `%${('00' + c.charCodeAt(0).toString(16)).slice(-2)}`)
        .join(''));
    const out = new Uint8Array(text.length);
    for (let i = 0; i < text.length; i++)
        out[i] = text.charCodeAt(i) & 0xff;
    return out;
}
