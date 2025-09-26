# @packetfs/pfs-arith

A tiny TypeScript library for PacketFS "Native Arithmetic Mode" over WebSockets, matching the server in `app/routes/websockets.py`.

- Preface and PVRT framing identical to Python implementation
- BREF-only PVRT windows with relative deltas from an agreed anchor (default: blob size / 2)
- Simple client to send an IPROG plan over ws://.../ws/pfs-arith

## Install

This package is local to the repo. To build:

```bash
npm -w full_apps/packetfs-infinity/app/web/pfs-arith install
npm -w full_apps/packetfs-infinity/app/web/pfs-arith run build
```

## Usage (Node)

```ts
import { PfsArithClient } from './dist/index.js';
import fs from 'node:fs/promises';

const iprog = JSON.parse(await fs.readFile('path/to/file.iprog.json', 'utf8'));
const client = new PfsArithClient((url) => createNodeWS(url));
const res = await client.sendIprog('ws://host:8811/ws/pfs-arith', iprog, 'transfer123');
console.log(res);
```

Where `createNodeWS` is a small adapter that wraps `ws` module and implements the WebSocketLike interface:

```ts
import WebSocket from 'ws';

function createNodeWS(url: string) {
  const sock = new WebSocket(url);
  return {
    async send(data: Uint8Array) { await new Promise<void>((resolve, reject) => { sock.send(data, (err) => err ? reject(err) : resolve()); }); },
    async recvJson(timeoutMs?: number) { return JSON.parse(await this.recvText(timeoutMs)); },
    async recvText(timeoutMs?: number) { return new Promise<string>((resolve, reject) => { const t = setTimeout(() => reject(new Error('timeout')), timeoutMs ?? 0); sock.once('message', (d) => { clearTimeout(t); resolve(typeof d === 'string' ? d : Buffer.from(d as any).toString('utf8')); }); }); },
  };
}
```

## Browser

In a browser, pass a factory that wraps `WebSocket` and encodes/decodes appropriately. The server supports both JSON control and binary CTRL frames.

## Notes

- Relative BREF chunks set flag bit0=1 and encode signed 64-bit deltas in two's complement inside the 8-byte off field.
- Hashes: windows use SHA-256 truncated to 16 bytes (`sha256-16`).
- The server may respond with a NEED list; send only those windows.
