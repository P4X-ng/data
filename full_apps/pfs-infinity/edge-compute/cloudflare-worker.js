// PacketFS Edge Compute - Cloudflare Worker (streaming + Range)
// Streams cached bytes at the POP using Range and computes minimal results.

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === 'POST' && url.pathname === '/compute') {
      try {
        const program = await request.json();
        const dataUrl = program.data_url;
        const instrs = program.instructions || [];
        const results = [];
        const timing = [];
        let totalBytes = 0;

        // Helper: bitwise crc32c (slow but streaming)
        function crc32c_chunk(crc, chunk) {
          let c = crc >>> 0;
          for (let i = 0; i < chunk.length; i++) {
            c ^= chunk[i];
            for (let j = 0; j < 8; j++) {
              c = (c >>> 1) ^ (0x82F63B78 & (-(c & 1)));
            }
          }
          return c >>> 0;
        }

        for (const inst of instrs) {
          const op = inst.op;
          const imm = inst.imm;
          const offset = inst.offset;
          const length = inst.length;

          const headers = new Headers();
          if (offset !== undefined && length !== undefined) {
            headers.set('Range', `bytes=${offset}-${offset + length - 1}`);
          }

          const cf = { cacheEverything: true, cacheTtl: 3600 };
          const t0 = Date.now();
          const resp = await fetch(dataUrl, { headers, cf });
          if (!(resp.ok || resp.status === 206)) {
            return new Response(JSON.stringify({ error: `fetch failed ${resp.status}` }), { status: 502 });
          }

          const cacheStatus = resp.headers.get('CF-Cache-Status') || null;
          const reader = resp.body.getReader();
          let bytesProcessed = 0;

          // State for streaming ops
          let count = 0;
          let crc = 0xFFFFFFFF >>> 0;
          let fnv = 0xcbf29ce484222325n;
          const preview = new Uint8Array(32);
          let previewLen = 0;
          const doXor = op === 'xor';
          const doAdd = op === 'add';

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            const chunk = value;
            bytesProcessed += chunk.length;

            if (op === 'counteq') {
              const needle = (imm >>> 0) & 0xFF;
              for (let i = 0; i < chunk.length; i++) if (chunk[i] === needle) count++;
            } else if (op === 'crc32c') {
              crc = crc32c_chunk(crc, chunk);
            } else if (op === 'fnv64') {
              for (let i = 0; i < chunk.length; i++) {
                fnv ^= BigInt(chunk[i]);
                fnv = (fnv * 0x100000001b3n) & 0xFFFFFFFFFFFFFFFFn;
              }
            } else if (doXor || doAdd) {
              const k = (imm >>> 0) & 0xFF;
              for (let i = 0; i < chunk.length; i++) {
                const v = doXor ? (chunk[i] ^ k) : ((chunk[i] + k) & 0xFF);
                if (previewLen < 32) preview[previewLen++] = v;
              }
              // Note: omit streaming SHA-256 here; add wasm/js incremental hash if needed
            } else {
              return new Response(JSON.stringify({ error: `unsupported op ${op}` }), { status: 400 });
            }
          }

          totalBytes += bytesProcessed;
          const elapsed = Date.now() - t0;
          if (op === 'counteq') {
            results.push({ op, value: count });
          } else if (op === 'crc32c') {
            results.push({ op, value: (crc ^ 0xFFFFFFFF) >>> 0 });
          } else if (op === 'fnv64') {
            results.push({ op, value: fnv.toString() });
          } else if (doXor || doAdd) {
            const hex = Array.from(preview.subarray(0, previewLen)).map(b => b.toString(16).padStart(2, '0')).join('');
            results.push({ op, length: bytesProcessed, preview: hex });
          }

          timing.push({ op, elapsed_ms: elapsed, bytes_processed: bytesProcessed, cache_status: cacheStatus, range: headers.get('Range') || null });
        }

        return new Response(JSON.stringify({ success: true, results, timing, bytes_processed: totalBytes, edge_location: request.cf?.colo || 'unknown' }), { headers: { 'Content-Type': 'application/json' } });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message || String(e) }), { status: 500 });
      }
    }

    if (url.pathname === '/health') {
      return new Response(JSON.stringify({ status: 'healthy', edge_location: request.cf?.colo || 'unknown', ops: ['counteq','crc32c','fnv64','xor','add'] }), { headers: { 'Content-Type': 'application/json' } });
    }

    return new Response('ok', { status: 200 });
  }
}
