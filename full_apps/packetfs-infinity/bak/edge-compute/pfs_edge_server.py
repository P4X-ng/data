#!/usr/bin/env python3
"""
PacketFS Edge Server - Add to ANY web server!
Compute on your data without sending it to clients!
"""

from flask import Flask, request, jsonify, Response, send_file
import hashlib
import zlib
import struct
import io
import os
import time
from functools import wraps
from typing import Iterator, Optional

try:
    import requests
except Exception:  # keep server import-safe; requests is required for http(s) streaming
    requests = None

app = Flask(__name__)

# Cache for frequently accessed data
data_cache = {}

def pcpu_counteq(data: bytes, imm: int) -> int:
    """Count occurrences of byte value"""
    return sum(1 for b in data if b == imm)

def pcpu_xor(data: bytes, imm: int) -> bytes:
    """XOR each byte with immediate"""
    return bytes(b ^ imm for b in data)

def pcpu_add(data: bytes, imm: int) -> bytes:
    """Add immediate to each byte (mod 256)"""
    return bytes((b + imm) & 0xFF for b in data)

def pcpu_crc32c(data: bytes, imm=None) -> int:
    """CRC32C checksum"""
    crc = 0xFFFFFFFF
    for byte in data:
        crc = crc ^ byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x82F63B78
            else:
                crc = crc >> 1
    return crc ^ 0xFFFFFFFF

def pcpu_fnv64(data: bytes, imm=None) -> int:
    """FNV-1a 64-bit hash"""
    hash_val = 0xcbf29ce484222325
    prime = 0x100000001b3
    for byte in data:
        hash_val ^= byte
        hash_val = (hash_val * prime) & 0xFFFFFFFFFFFFFFFF
    return hash_val

# Map of supported operations (buffered path)
PCPU_OPS = {
    'counteq': pcpu_counteq,
    'xor': pcpu_xor,
    'add': pcpu_add,
    'crc32c': pcpu_crc32c,
    'fnv64': pcpu_fnv64,
    'sha256': lambda data, _=None: hashlib.sha256(data).hexdigest(),
    'md5': lambda data, _=None: hashlib.md5(data).hexdigest(),
    'compress': lambda data, _=None: zlib.compress(data),
}

CHUNK_SIZE = 1024 * 1024  # 1 MiB
ALIGN_BYTES = 1024 * 1024  # 1 MiB alignment for range planning

def stream_source(data_url: str, offset: Optional[int], length: Optional[int], chunk_size: int = CHUNK_SIZE, align: Optional[int] = None, meta: Optional[dict] = None) -> Iterator[bytes]:
    """Yield only the requested window bytes but fetch aligned ranges for cache friendliness.

    - If align is provided, upstream fetch is aligned to floor(offset/align)..ceil(end/align)-1.
    - meta, if provided, will be populated with resp headers and fetch window info.
    """
    if meta is None:
        meta = {}

    # Normalize window
    if offset is None and length is None:
        # Whole object
        window_start = 0
        window_len = None
    elif offset is not None and length is None:
        window_start = offset
        window_len = None
    elif offset is None and length is not None:
        window_start = 0
        window_len = length
    else:
        window_start = int(offset)
        window_len = int(length)

    # Determine upstream fetch range (aligned)
    fetch_start = window_start
    fetch_len = window_len
    if align is not None and window_len is not None:
        fetch_start = (window_start // align) * align
        fetch_end_inclusive = (((window_start + window_len + align - 1) // align) * align) - 1
        fetch_len = (fetch_end_inclusive - fetch_start + 1)
    elif align is not None and window_len is None:
        # Unknown end; just align start
        fetch_start = (window_start // align) * align

    # Helper to crop a chunk [global_pos, global_pos+len(chunk)) to window [window_start, window_end)
    window_end = None if window_len is None else (window_start + window_len)

    def yield_cropped(file_iter: Iterator[bytes]) -> Iterator[bytes]:
        nonlocal fetch_start
        global_pos = fetch_start
        for buf in file_iter:
            if window_len is None:
                # Whole tail from window_start
                if global_pos < window_start:
                    # Need to skip left part
                    left_skip = window_start - global_pos
                    if left_skip < len(buf):
                        yield buf[left_skip:]
                else:
                    yield buf
            else:
                # Intersect [global_pos, global_pos+len(buf)) with [window_start, window_end)
                if global_pos >= window_end:
                    break
                left = max(global_pos, window_start)
                right = min(global_pos + len(buf), window_end)
                if right > left:
                    s = left - global_pos
                    e = right - global_pos
                    yield buf[s:e]
            global_pos += len(buf)

    # HTTP/HTTPS source
    if data_url.startswith('http://') or data_url.startswith('https://'):
        if requests is None:
            raise RuntimeError("requests is required for http(s) streaming; please install requests")
        headers = {}
        if window_len is None:
            # Use Range only if offset>0, else allow 200
            if fetch_start and fetch_start > 0:
                headers['Range'] = f"bytes={fetch_start}-"
        else:
            headers['Range'] = f"bytes={fetch_start}-{fetch_start + fetch_len - 1}"
        resp = requests.get(data_url, stream=True, headers=headers, timeout=30)
        resp.raise_for_status()
        # expose cache headers
        rh = resp.headers
        meta['resp_headers'] = {
            'CF-Cache-Status': rh.get('CF-Cache-Status'),
            'X-Cache': rh.get('X-Cache'),
            'Age': rh.get('Age'),
            'Accept-Ranges': rh.get('Accept-Ranges'),
            'Content-Length': rh.get('Content-Length'),
            'ETag': rh.get('ETag')
        }
        meta['fetch_range'] = headers.get('Range')
        meta['window'] = {'offset': window_start, 'length': window_len}

        def http_iter():
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if not chunk:
                    break
                yield chunk

        yield from yield_cropped(http_iter())

    # file:// source
    elif data_url.startswith('file://'):
        path = data_url[7:]
        fsize = None
        try:
            st = os.stat(path)
            fsize = st.st_size
        except Exception:
            pass
        with open(path, 'rb') as f:
            if fetch_start:
                f.seek(fetch_start)
            remaining = None if fetch_len is None else fetch_len
            def file_iter():
                nonlocal remaining
                while True:
                    if remaining is not None and remaining <= 0:
                        break
                    to_read = chunk_size if remaining is None else min(chunk_size, remaining)
                    buf = f.read(to_read)
                    if not buf:
                        break
                    if remaining is not None:
                        remaining -= len(buf)
                    yield buf
            meta['resp_headers'] = {
                'Accept-Ranges': 'bytes',
                'Content-Length': str(fsize) if fsize is not None else None
            }
            meta['fetch_range'] = None if fetch_len is None and (not fetch_start) else f"bytes={fetch_start}-{'' if fetch_len is None else fetch_start + fetch_len - 1}"
            meta['window'] = {'offset': window_start, 'length': window_len}
            yield from yield_cropped(file_iter())

    # local relative path
    else:
        path = data_url
        if os.path.exists(path):
            fsize = None
            try:
                st = os.stat(path)
                fsize = st.st_size
            except Exception:
                pass
            with open(path, 'rb') as f:
                if fetch_start:
                    f.seek(fetch_start)
                remaining = None if fetch_len is None else fetch_len
                def file_iter():
                    nonlocal remaining
                    while True:
                        if remaining is not None and remaining <= 0:
                            break
                        to_read = chunk_size if remaining is None else min(chunk_size, remaining)
                        buf = f.read(to_read)
                        if not buf:
                            break
                        if remaining is not None:
                            remaining -= len(buf)
                        yield buf
                meta['resp_headers'] = {
                    'Accept-Ranges': 'bytes',
                    'Content-Length': str(fsize) if fsize is not None else None
                }
                meta['fetch_range'] = None if fetch_len is None and (not fetch_start) else f"bytes={fetch_start}-{'' if fetch_len is None else fetch_start + fetch_len - 1}"
                meta['window'] = {'offset': window_start, 'length': window_len}
                yield from yield_cropped(file_iter())
        else:
            raise ValueError(f"Unsupported URL or path: {data_url}")


def stream_compute(data_url: str, op: str, imm: Optional[int], offset: Optional[int], length: Optional[int]) -> dict:
    """Compute result for a single instruction by streaming the source once for the specified window."""
    start = time.time()
    bytes_processed = 0
    meta = {}

    if op == 'counteq':
        if imm is None:
            raise ValueError("counteq requires imm")
        target = bytes([imm & 0xFF])
        total = 0
        for chunk in stream_source(data_url, offset, length, align=ALIGN_BYTES, meta=meta):
            total += chunk.count(target)
            bytes_processed += len(chunk)
        return {
            'op': op,
            'value': total,
            'elapsed_ms': (time.time() - start) * 1000.0,
            'bytes_processed': bytes_processed,
            'cache': meta.get('resp_headers'),
            'fetch_range': meta.get('fetch_range'),
            'window': meta.get('window')
        }

    elif op == 'sha256':
        h = hashlib.sha256()
        for chunk in stream_source(data_url, offset, length, align=ALIGN_BYTES, meta=meta):
            h.update(chunk)
            bytes_processed += len(chunk)
        return {
            'op': op,
            'value': h.hexdigest(),
            'elapsed_ms': (time.time() - start) * 1000.0,
            'bytes_processed': bytes_processed,
            'cache': meta.get('resp_headers'),
            'fetch_range': meta.get('fetch_range'),
            'window': meta.get('window')
        }

    elif op == 'fnv64':
        hash_val = 0xcbf29ce484222325
        prime = 0x100000001b3
        for chunk in stream_source(data_url, offset, length, align=ALIGN_BYTES, meta=meta):
            for b in chunk:
                hash_val ^= b
                hash_val = (hash_val * prime) & 0xFFFFFFFFFFFFFFFF
            bytes_processed += len(chunk)
        return {
            'op': op,
            'value': hash_val,
            'elapsed_ms': (time.time() - start) * 1000.0,
            'bytes_processed': bytes_processed,
            'cache': meta.get('resp_headers'),
            'fetch_range': meta.get('fetch_range'),
            'window': meta.get('window')
        }

    elif op == 'crc32c':
        # bitwise, streaming (slow but correct)
        crc = 0xFFFFFFFF
        for chunk in stream_source(data_url, offset, length, align=ALIGN_BYTES, meta=meta):
            for byte in chunk:
                crc ^= byte
                for _ in range(8):
                    if crc & 1:
                        crc = (crc >> 1) ^ 0x82F63B78
                    else:
                        crc >>= 1
            bytes_processed += len(chunk)
        crc ^= 0xFFFFFFFF
        return {
            'op': op,
            'value': crc,
            'elapsed_ms': (time.time() - start) * 1000.0,
            'bytes_processed': bytes_processed,
            'cache': meta.get('resp_headers'),
            'fetch_range': meta.get('fetch_range'),
            'window': meta.get('window')
        }

    elif op in ('xor', 'add'):
        # For arithmetic transforms, don't return transformed bytes; return length and a hash preview of the transformed window
        if imm is None:
            raise ValueError(f"{op} requires imm")
        h = hashlib.sha256()
        first_preview = bytearray()
        total_len = 0
        for chunk in stream_source(data_url, offset, length, align=ALIGN_BYTES, meta=meta):
            if op == 'xor':
                transformed = bytes((b ^ (imm & 0xFF)) for b in chunk)
            else:
                transformed = bytes(((b + (imm & 0xFF)) & 0xFF) for b in chunk)
            if len(first_preview) < 32:
                need = 32 - len(first_preview)
                first_preview.extend(transformed[:need])
            h.update(transformed)
            total_len += len(chunk)
            bytes_processed += len(chunk)
        return {
            'op': op,
            'length': total_len,
            'sha256': h.hexdigest(),
            'preview': first_preview.hex(),
            'elapsed_ms': (time.time() - start) * 1000.0,
            'bytes_processed': bytes_processed,
            'cache': meta.get('resp_headers'),
            'fetch_range': meta.get('fetch_range'),
            'window': meta.get('window')
        }

    elif op == 'compress':
        co = zlib.compressobj(level=6)
        first_preview = bytearray()
        total_out = 0
        for chunk in stream_source(data_url, offset, length, align=ALIGN_BYTES, meta=meta):
            out = co.compress(chunk)
            if out:
                if len(first_preview) < 32:
                    need = 32 - len(first_preview)
                    first_preview.extend(out[:need])
                total_out += len(out)
            bytes_processed += len(chunk)
        tail = co.flush()
        if tail:
            if len(first_preview) < 32:
                need = 32 - len(first_preview)
                first_preview.extend(tail[:need])
            total_out += len(tail)
        return {
            'op': op,
            'length': total_out,
            'preview': first_preview.hex(),
            'elapsed_ms': (time.time() - start) * 1000.0,
            'bytes_processed': bytes_processed,
            'cache': meta.get('resp_headers'),
            'fetch_range': meta.get('fetch_range'),
            'window': meta.get('window')
        }

    else:
        raise ValueError(f"Unsupported op for streaming: {op}")

def compute_aware_response(f):
    """Decorator to add compute capabilities to any endpoint"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for PacketFS compute headers
        if 'X-PacketFS-Op' in request.headers:
            op = request.headers.get('X-PacketFS-Op')
            imm = int(request.headers.get('X-PacketFS-Imm', 0))
            
            # Get the data that would normally be sent
            response = f(*args, **kwargs)
            if isinstance(response, Response):
                data = response.get_data()
            else:
                data = response
            
            if isinstance(data, str):
                data = data.encode()
            
            # Apply operation
            if op in PCPU_OPS:
                result = PCPU_OPS[op](data, imm)
                
                # Return result in header instead of data
                return Response(
                    b'',  # Empty body - no data transfer!
                    headers={
                        'X-PacketFS-Result': str(result) if isinstance(result, (int, str)) else 'computed',
                        'X-PacketFS-Data-Size': str(len(data)),
                        'X-PacketFS-Op': op
                    }
                )
        
        # Normal response if no compute requested
        return f(*args, **kwargs)
    
    return decorated_function

@app.route('/compute', methods=['POST'])
def compute_endpoint():
    """Dedicated compute endpoint (streaming, range-aware)."""
    try:
        program = request.json
        data_url = program['data_url']
        instructions = program['instructions']

        results = []
        total_bytes = 0
        timing = []

        for inst in instructions:
            op = inst['op']
            imm = inst.get('imm')
            offset = inst.get('offset')
            length = inst.get('length')

            res = stream_compute(data_url, op, imm, offset, length)
            results.append({k: v for k, v in res.items() if k in ('op','value','length','preview','sha256')})
            total_bytes += res.get('bytes_processed', 0)
            timing.append({
                'op': res['op'],
                'elapsed_ms': res['elapsed_ms'],
'bytes_processed': res['bytes_processed'],
                'offset': offset,
                'length': length,
                'cache_headers': res.get('cache'),
                'fetch_range': res.get('fetch_range'),
                'window': res.get('window')
            })

        return jsonify({
            'success': True,
            'data_size': total_bytes,
            'results': results,
            'timing': timing,
            'edge_location': 'local-server',
            'cache_status': 'STREAM'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/data/<path:filename>')
@compute_aware_response
def serve_file(filename):
    """Serve files with compute awareness"""
    # This could serve any file - logs, datasets, etc.
    file_path = os.path.join('/tmp', filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        # Demo data
        return b"This is demo data for file: " + filename.encode()

@app.route('/api/logs')
@compute_aware_response
def serve_logs():
    """Example API endpoint with compute support"""
    # Normally would return large log data
    logs = b"ERROR: Something went wrong\n" * 1000
    logs += b"INFO: Normal operation\n" * 5000
    logs += b"WARNING: Check this\n" * 500
    
    return logs

@app.route('/health')
def health():
    """Health check with capabilities"""
    return jsonify({
        'status': 'healthy',
        'capabilities': list(PCPU_OPS.keys()),
        'edge_compute': True,
        'version': '1.0.0'
    })

# Nginx configuration to add edge compute
NGINX_CONFIG = """
# Add to nginx.conf to support PacketFS edge compute

location /compute {
    proxy_pass http://localhost:5000/compute;
    proxy_set_header X-Real-IP $remote_addr;
}

location /data/ {
    # Check for compute headers
    if ($http_x_packetfs_op) {
        proxy_pass http://localhost:5000$request_uri;
        break;
    }
    
    # Normal file serving
    root /var/www;
}

# Add Lua support for edge compute (with OpenResty)
location /smart/ {
    content_by_lua_block {
        local op = ngx.var.http_x_packetfs_op
        if op then
            -- Read file
            local file = io.open(ngx.var.document_root .. ngx.var.uri)
            local data = file:read("*all")
            file:close()
            
            -- Compute based on operation
            if op == "counteq" then
                local imm = tonumber(ngx.var.http_x_packetfs_imm) or 0
                local count = 0
                for i = 1, #data do
                    if string.byte(data, i) == imm then
                        count = count + 1
                    end
                end
                ngx.header["X-PacketFS-Result"] = tostring(count)
                ngx.header["X-PacketFS-Data-Size"] = tostring(#data)
                ngx.exit(204)  -- No content
            end
        else
            -- Normal serving
            ngx.exec("@fallback")
        end
    }
}
"""

# Apache .htaccess configuration
APACHE_CONFIG = """
# Add to .htaccess for PacketFS edge compute support

RewriteEngine On

# Check for PacketFS compute headers
RewriteCond %{HTTP:X-PacketFS-Op} !^$
RewriteRule ^(.*)$ /compute.php?file=$1 [L]

# compute.php would handle the edge computation
"""

# Cloudflare Worker deployment script
DEPLOY_SCRIPT = """#!/bin/bash
# Deploy PacketFS edge compute to Cloudflare

wrangler init pfs-edge
cd pfs-edge
cp ../cloudflare-worker.js src/index.js

# Configure wrangler.toml
cat > wrangler.toml << EOF
name = "pfs-edge"
type = "javascript"
account_id = "YOUR_ACCOUNT_ID"
workers_dev = true
route = "example.com/*"
zone_id = "YOUR_ZONE_ID"
EOF

# Deploy
wrangler publish

echo "Edge compute deployed to Cloudflare!"
"""

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'nginx':
        print(NGINX_CONFIG)
    elif len(sys.argv) > 1 and sys.argv[1] == 'apache':
        print(APACHE_CONFIG)
    elif len(sys.argv) > 1 and sys.argv[1] == 'deploy':
        print(DEPLOY_SCRIPT)
    else:
        print("🚀 PacketFS Edge Server starting...")
        print("📊 Compute operations available:", list(PCPU_OPS.keys()))
        print("🌐 Listening on http://localhost:5000")
        print("\nTry:")
        print("  curl -H 'X-PacketFS-Op: counteq' -H 'X-PacketFS-Imm: 69' http://localhost:5000/api/logs")
        print("  (Returns count instead of downloading logs!)")
        app.run(debug=True, port=5000)