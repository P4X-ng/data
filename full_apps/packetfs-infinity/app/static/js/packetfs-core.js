/**
 * PacketFS Core - Client-side blob generation and IPROG creation
 * 
 * This library provides the core PacketFS functionality in JavaScript:
 * - Deterministic blob generation from seed
 * - File compression to IPROG format with BREF chunks
 * - Minimal data transfer by sharing blob state with server
 */

class PacketFSBlob {
    constructor(name, size, seed) {
        this.name = name;
        this.size = size;
        this.seed = seed;
        this.data = null;
        this.paletteSize = 256 * 1024; // 256 KB palette region
        this.initialized = false;
    }

    /**
     * Initialize the blob with deterministic data
     * Uses xorshift for deterministic pseudo-random generation
     */
    async initialize() {
        if (this.initialized) return;
        
        console.log(`Initializing blob: ${this.name} (${this.size} bytes, seed=${this.seed})`);
        this.data = new Uint8Array(this.size);
        
        // Header (64 bytes)
        const header = new TextEncoder().encode(`POB1:${this.name}:${this.size}:${this.seed}`);
        for (let i = 0; i < Math.min(header.length, 64); i++) {
            this.data[i] = header[i];
        }
        
        // Palette region (256 KB after header)
        const paletteStart = 64;
        const paletteEnd = Math.min(paletteStart + this.paletteSize, this.size);
        
        // Generate palette patterns
        this.generatePalette(paletteStart, paletteEnd);
        
        // Fill rest with xorshift pseudo-random data
        let state = this.seed;
        for (let i = paletteEnd; i < this.size; i++) {
            state ^= state << 13;
            state ^= state >>> 17;
            state ^= state << 5;
            state = (state >>> 0); // Ensure 32-bit unsigned
            this.data[i] = state & 0xFF;
        }
        
        this.initialized = true;
        console.log('Blob initialized successfully');
    }

    /**
     * Generate deterministic palette patterns
     */
    generatePalette(start, end) {
        const tileSize = 256;
        const numTiles = Math.floor((end - start) / tileSize);
        
        for (let tile = 0; tile < numTiles; tile++) {
            const tileStart = start + (tile * tileSize);
            const family = tile % 4; // 0=const, 1=ramp, 2=gray, 3=lfsr
            
            switch (family) {
                case 0: // Constant patterns
                    const constVal = (tile * 17) & 0xFF;
                    for (let i = 0; i < tileSize; i++) {
                        this.data[tileStart + i] = constVal;
                    }
                    break;
                
                case 1: // Ramp patterns
                    const rampStep = ((tile + 1) * 3) & 0xFF;
                    for (let i = 0; i < tileSize; i++) {
                        this.data[tileStart + i] = (i * rampStep) & 0xFF;
                    }
                    break;
                
                case 2: // Gray patterns
                    for (let i = 0; i < tileSize; i++) {
                        this.data[tileStart + i] = (i ^ (i >> 1)) & 0xFF;
                    }
                    break;
                
                case 3: // LFSR patterns
                    let lfsr = tile + 1;
                    for (let i = 0; i < tileSize; i++) {
                        lfsr = ((lfsr >> 1) ^ (-(lfsr & 1) & 0xB8)) & 0xFF;
                        this.data[tileStart + i] = lfsr;
                    }
                    break;
            }
        }
    }

    /**
     * Find matching chunk in blob (exact or with transform)
     * Returns: {offset, length, flags} or null
     */
    findChunk(data, maxTransforms = true) {
        if (!this.initialized) return null;
        
        const minMatch = 16; // Minimum match length
        const maxSearch = Math.min(this.size, 1024 * 1024); // Search first 1MB
        
        // Try exact match first
        for (let offset = 0; offset < maxSearch - data.length; offset++) {
            let match = true;
            for (let i = 0; i < Math.min(data.length, minMatch); i++) {
                if (this.data[offset + i] !== data[i]) {
                    match = false;
                    break;
                }
            }
            if (match) {
                // Verify full match
                let fullMatch = true;
                for (let i = 0; i < data.length; i++) {
                    if (this.data[offset + i] !== data[i]) {
                        fullMatch = false;
                        break;
                    }
                }
                if (fullMatch) {
                    return {offset, length: data.length, flags: 0}; // Identity transform
                }
            }
        }
        
        // Try XOR transforms if enabled
        if (maxTransforms) {
            for (let xorVal = 1; xorVal < 256; xorVal++) {
                for (let offset = 0; offset < maxSearch - data.length; offset++) {
                    let match = true;
                    for (let i = 0; i < Math.min(data.length, minMatch); i++) {
                        if ((this.data[offset + i] ^ xorVal) !== data[i]) {
                            match = false;
                            break;
                        }
                    }
                    if (match) {
                        // Verify full match with XOR
                        let fullMatch = true;
                        for (let i = 0; i < data.length; i++) {
                            if ((this.data[offset + i] ^ xorVal) !== data[i]) {
                                fullMatch = false;
                                break;
                            }
                        }
                        if (fullMatch) {
                            return {offset, length: data.length, flags: (1 << 8) | xorVal}; // XOR transform
                        }
                    }
                }
            }
        }
        
        return null; // No match found
    }
}

class PacketFSCompressor {
    constructor(blob) {
        this.blob = blob;
        this.windowSize = 65536; // 64KB windows
    }

    /**
     * Compress file data to IPROG format
     * Returns: IPROG object with BREF chunks
     */
    async compress(fileData, fileName) {
        if (!this.blob.initialized) {
            await this.blob.initialize();
        }

        const uint8Data = new Uint8Array(fileData);
        const sha256 = await this.computeSHA256(uint8Data);
        
        const windows = [];
        const numWindows = Math.ceil(uint8Data.length / this.windowSize);
        
        console.log(`Compressing ${fileName}: ${uint8Data.length} bytes in ${numWindows} windows`);
        
        for (let w = 0; w < numWindows; w++) {
            const start = w * this.windowSize;
            const end = Math.min(start + this.windowSize, uint8Data.length);
            const windowData = uint8Data.slice(start, end);
            
            // Compute window hash
            const hash16 = await this.computeSHA256(windowData, 16);
            
            // Generate BREF chunks for this window
            const brefChunks = this.generateBREF(windowData);
            
            windows.push({
                idx: w,
                hash16: this.bytesToHex(hash16),
                bref: brefChunks,
                raw_size: windowData.length,
                compressed_size: this.calculateBREFSize(brefChunks)
            });
        }
        
        // Calculate compression ratio
        const totalRawSize = uint8Data.length;
        const totalCompressedSize = windows.reduce((sum, w) => sum + w.compressed_size, 0);
        const compressionRatio = totalRawSize / totalCompressedSize;
        
        const iprog = {
            version: "1.0",
            sha256: this.bytesToHex(sha256),
            size: uint8Data.length,
            window_size: this.windowSize,
            windows: windows,
            blob: {
                name: this.blob.name,
                size: this.blob.size,
                seed: this.blob.seed
            },
            metadata: {
                filename: fileName,
                compressed_at: new Date().toISOString(),
                compression_ratio: compressionRatio.toFixed(2),
                total_raw_size: totalRawSize,
                total_compressed_size: totalCompressedSize
            }
        };
        
        console.log(`Compression complete: ${compressionRatio.toFixed(2)}x reduction`);
        return iprog;
    }

    /**
     * Generate BREF chunks for window data
     */
    generateBREF(windowData) {
        const chunks = [];
        const tileSize = 256; // Process in 256-byte tiles
        
        for (let i = 0; i < windowData.length; i += tileSize) {
            const tileEnd = Math.min(i + tileSize, windowData.length);
            const tile = windowData.slice(i, tileEnd);
            
            // Try to find matching chunk in blob
            const match = this.blob.findChunk(tile);
            
            if (match) {
                chunks.push([match.offset, match.length, match.flags]);
            } else {
                // No match - will need to send as raw (handled by server)
                // For now, record as offset 0 with special flag
                chunks.push([0, tile.length, 0x8000]); // Flag 0x8000 indicates raw needed
            }
        }
        
        // Coalesce adjacent chunks when possible
        const coalesced = [];
        for (const chunk of chunks) {
            if (coalesced.length > 0) {
                const last = coalesced[coalesced.length - 1];
                // Check if chunks are adjacent and have same transform
                if (last[0] + last[1] === chunk[0] && last[2] === chunk[2]) {
                    last[1] += chunk[1]; // Extend length
                    continue;
                }
            }
            coalesced.push([...chunk]);
        }
        
        return coalesced;
    }

    /**
     * Calculate size of BREF chunks (for compression ratio)
     */
    calculateBREFSize(brefChunks) {
        // Each BREF chunk: offset(8) + length(4) + flags(2) = 14 bytes
        // In practice, with varint encoding it's smaller
        return brefChunks.length * 14;
    }

    /**
     * Compute SHA256 hash
     */
    async computeSHA256(data, truncateBytes = 32) {
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = new Uint8Array(hashBuffer);
        return hashArray.slice(0, truncateBytes);
    }

    /**
     * Convert bytes to hex string
     */
    bytesToHex(bytes) {
        return Array.from(bytes)
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
    }
}

/**
 * Main PacketFS client class
 */
class PacketFSClient {
    constructor(blobName = 'pfs_vblob', blobSize = 1073741824, blobSeed = 42) {
        this.blob = new PacketFSBlob(blobName, blobSize, blobSeed);
        this.compressor = new PacketFSCompressor(this.blob);
        this.initialized = false;
    }

    /**
     * Initialize the client (creates blob)
     */
    async initialize() {
        if (this.initialized) return;
        await this.blob.initialize();
        this.initialized = true;
    }

    /**
     * Compress a file to IPROG format
     */
    async compressFile(file) {
        const arrayBuffer = await file.arrayBuffer();
        const iprog = await this.compressor.compress(arrayBuffer, file.name);
        return iprog;
    }

    /**
     * Send IPROG to server via WebSocket
     */
    async sendIPROG(iprog, serverUrl) {
        // Build WebSocket URL
        const wsUrl = serverUrl.replace('https://', 'wss://').replace('http://', 'ws://');
        const endpoint = `${wsUrl}/ws/pfs-arith`;
        
        return new Promise((resolve, reject) => {
            const ws = new WebSocket(endpoint);
            
            ws.onopen = () => {
                console.log('WebSocket connected, sending IPROG...');
                
                // Send IPROG as JSON
                ws.send(JSON.stringify({
                    type: 'IPROG',
                    transfer_id: crypto.randomUUID(),
                    iprog: iprog
                }));
            };
            
            ws.onmessage = (event) => {
                console.log('Received:', event.data);
                const response = JSON.parse(event.data);
                
                if (response.status === 'success') {
                    resolve(response);
                } else {
                    reject(new Error(response.error || 'Transfer failed'));
                }
                
                ws.close();
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                reject(error);
            };
            
            ws.onclose = () => {
                console.log('WebSocket closed');
            };
        });
    }
}

// Export for use in browser
window.PacketFSClient = PacketFSClient;
window.PacketFSBlob = PacketFSBlob;
window.PacketFSCompressor = PacketFSCompressor;

console.log('PacketFS Core library loaded');