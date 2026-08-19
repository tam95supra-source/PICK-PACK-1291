import WebSocket from 'ws';
// The production Worker uses Cloudflare WebSocketPair/Hibernation. This shim only makes the
// GitHub Actions Node client deterministic across Node 22 runner image revisions.
globalThis.WebSocket = WebSocket;
await import('./m2-chaos.mjs');
