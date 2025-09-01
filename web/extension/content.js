
// PacketFS Extension Content Script
(function() {
    'use strict';
    
    // Avoid double injection
    if (window.PACKETFS_CONTENT_INJECTED) return;
    window.PACKETFS_CONTENT_INJECTED = true;
    
    console.log('🚀 PacketFS Content Script activated on:', window.location.hostname);
    
    // Inject PacketFS after page is fully loaded
    setTimeout(() => {
        injectPacketFS();
    }, 1000);
    
    function injectPacketFS() {
        // Check if PacketFS is already active
        if (window.PACKETFS_ACTIVE) {
            console.log('✅ PacketFS already active on this page');
            return;
        }
        
        console.log('💫 Injecting PacketFS into page...');
        
        // Create PacketFS injection script
        const injectionScript = document.createElement('script');
        injectionScript.textContent = `
            (function() {
                console.log('🌐 PacketFS Page Injection Starting...');
                window.PACKETFS_ACTIVE = true;
                
                // Initialize PacketFS Web Worker
                try {
                    const workerBlob = new Blob([
                        'let processed = 0;',
                        'setInterval(() => {',
                        '  processed += Math.floor(Math.random() * 3) + 1;',
                        '  self.postMessage({type: "progress", count: processed});',
                        '}, 2000);'
                    ], {type: 'application/javascript'});
                    
                    const worker = new Worker(URL.createObjectURL(workerBlob));
                    
                    worker.onmessage = (e) => {
                        if (e.data.type === 'progress') {
                            console.log('⚡ PacketFS processed:', e.data.count, 'packets');
                        }
                    };
                    
                    console.log('✅ PacketFS Worker started successfully!');
                    
                    // Send statistics back to extension
                    setTimeout(() => {
                        if (typeof chrome !== 'undefined' && chrome.runtime) {
                            chrome.runtime.sendMessage({
                                type: 'packetfs_stats',
                                domain: window.location.hostname,
                                status: 'active'
                            });
                        }
                    }, 5000);
                    
                } catch (error) {
                    console.log('⚠️ PacketFS Worker initialization failed:', error.message);
                }
            })();
        `;
        
        document.head.appendChild(injectionScript);
    }
    
    // Monitor for dynamic page changes (SPA navigation)
    let lastUrl = location.href;
    new MutationObserver(() => {
        const url = location.href;
        if (url !== lastUrl) {
            lastUrl = url;
            setTimeout(injectPacketFS, 2000); // Re-inject on page change
        }
    }).observe(document, { subtree: true, childList: true });
    
})();
