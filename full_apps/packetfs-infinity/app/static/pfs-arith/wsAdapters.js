// Minimal WebSocket adapters for browser and node
export function browserWS(url) {
    const ws = new WebSocket(url);
    return {
        async send(data) {
            await new Promise((resolve, reject) => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(data);
                    resolve();
                }
                else {
                    ws.addEventListener('open', () => { ws.send(data); resolve(); }, { once: true });
                    ws.addEventListener('error', () => reject(new Error('ws error')), { once: true });
                }
            });
        },
        async recvJson(timeoutMs) {
            const txt = await this.recvText(timeoutMs);
            try {
                return JSON.parse(txt);
            }
            catch {
                return null;
            }
        },
        async recvText(timeoutMs) {
            return new Promise((resolve, reject) => {
                const to = timeoutMs ? setTimeout(() => reject(new Error('timeout')), timeoutMs) : null;
                ws.addEventListener('message', (ev) => {
                    if (to)
                        clearTimeout(to);
                    if (typeof ev.data === 'string')
                        return resolve(ev.data);
                    if (ev.data instanceof Blob) {
                        const fr = new FileReader();
                        fr.onload = () => resolve(String(fr.result || ''));
                        fr.onerror = () => reject(new Error('blob read error'));
                        fr.readAsText(ev.data);
                    }
                    else if (ev.data instanceof ArrayBuffer) {
                        const dec = new TextDecoder();
                        resolve(dec.decode(new Uint8Array(ev.data)));
                    }
                    else {
                        resolve('');
                    }
                }, { once: true });
                ws.addEventListener('error', () => {
                    if (to)
                        clearTimeout(to);
                    reject(new Error('ws error'));
                }, { once: true });
            });
        },
    };
}
