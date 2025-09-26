// Cloudflare Worker: PacketFS vCPU #2
// Deploy with: wrangler publish
// This worker executes packet-based computation

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Health check
    if (url.pathname === '/health') {
      return new Response(JSON.stringify({
        status: 'healthy',
        vcpu_id: 'cf-edge-001',
        region: request.cf?.colo || 'unknown',
        packets_executed: env.PACKETS_EXECUTED || 0
      }), {
        headers: { 'content-type': 'application/json' }
      });
    }

    // Main compute endpoint
    if (url.pathname === '/compute' && request.method === 'POST') {
      try {
        const { data_url, instructions, window } = await request.json();
        
        // Start timing
        const start = Date.now();
        
        // Fetch the data (with Range support for window)
        const headers = {};
        if (window) {
          const rangeEnd = window.offset + window.length - 1;
          headers['Range'] = `bytes=${window.offset}-${rangeEnd}`;
        }
        
        const dataResponse = await fetch(data_url, { headers });
        
        // Check cache status (this is key!)
        const cacheStatus = dataResponse.headers.get('cf-cache-status');
        const isHit = cacheStatus === 'HIT';
        
        // Get the actual bytes
        const buffer = await dataResponse.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        
        // Execute instructions (packet-based ops)
        const results = [];
        for (const inst of instructions) {
          const result = executeInstruction(bytes, inst);
          results.push(result);
        }
        
        // Calculate metrics
        const elapsed = Date.now() - start;
        const bytesProcessed = instructions.reduce((sum, i) => sum + (i.length || 0), 0);
        const throughputMBps = (bytesProcessed / 1048576) / (elapsed / 1000);
        
        // THIS IS THE MAGIC: we're a vCPU!
        return new Response(JSON.stringify({
          vcpu_id: 'cf-edge-001',
          region: request.cf?.colo || 'unknown',
          results,
          metrics: {
            elapsed_ms: elapsed,
            bytes_processed: bytesProcessed,
            throughput_mbps: throughputMBps.toFixed(2),
            cache_hit: isHit,
            cf_cache_status: cacheStatus
          },
          // Packet flow metadata
          packet_flow: {
            sender: request.headers.get('x-sender-vcpu') || 'unknown',
            receiver: 'cf-edge-001',
            network_is_cpu: true
          }
        }), {
          headers: { 
            'content-type': 'application/json',
            'x-vcpu-id': 'cf-edge-001',
            'x-packet-executed': 'true'
          }
        });
        
      } catch (error) {
        return new Response(JSON.stringify({
          error: error.message,
          vcpu_id: 'cf-edge-001'
        }), {
          status: 500,
          headers: { 'content-type': 'application/json' }
        });
      }
    }
    
    // Default response
    return new Response('PacketFS vCPU (Cloudflare Worker) - POST to /compute', {
      headers: { 'content-type': 'text/plain' }
    });
  }
};

// Execute a single instruction (packet operation)
function executeInstruction(bytes, inst) {
  const { op, offset = 0, length = bytes.length, imm = 0 } = inst;
  const slice = bytes.slice(offset, offset + length);
  
  switch (op) {
    case 'counteq': {
      // Count bytes equal to immediate
      let count = 0;
      for (let i = 0; i < slice.length; i++) {
        if (slice[i] === imm) count++;
      }
      return { op, count, bytes_scanned: slice.length };
    }
    
    case 'xor': {
      // XOR with immediate
      const result = new Uint8Array(slice.length);
      for (let i = 0; i < slice.length; i++) {
        result[i] = slice[i] ^ imm;
      }
      return { op, checksum: checksumBytes(result), bytes_processed: slice.length };
    }
    
    case 'add': {
      // Add immediate (mod 256)
      const result = new Uint8Array(slice.length);
      for (let i = 0; i < slice.length; i++) {
        result[i] = (slice[i] + imm) & 0xFF;
      }
      return { op, checksum: checksumBytes(result), bytes_processed: slice.length };
    }
    
    case 'fnv': {
      // FNV-1a hash
      let hash = 0x811c9dc5;
      for (let i = 0; i < slice.length; i++) {
        hash ^= slice[i];
        hash = Math.imul(hash, 0x01000193);
      }
      return { op, hash: hash >>> 0, bytes_hashed: slice.length };
    }
    
    case 'crc32': {
      // Simple CRC32 (not table-based for simplicity)
      let crc = 0xFFFFFFFF;
      for (let i = 0; i < slice.length; i++) {
        crc ^= slice[i];
        for (let j = 0; j < 8; j++) {
          crc = (crc >>> 1) ^ (0xEDB88320 & -(crc & 1));
        }
      }
      return { op, crc: (crc ^ 0xFFFFFFFF) >>> 0, bytes_processed: slice.length };
    }
    
    default:
      return { op, error: `Unknown operation: ${op}` };
  }
}

// Simple checksum for verification
function checksumBytes(bytes) {
  let sum = 0;
  for (let i = 0; i < bytes.length; i++) {
    sum = (sum + bytes[i]) & 0xFFFFFFFF;
  }
  return sum;
}