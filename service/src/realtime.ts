import { DurableObject } from "cloudflare:workers";
import { json, nowIso } from "./util";
import type { EventRow } from "./domain";

export class RealtimeHub extends DurableObject<Env> {
  override async fetch(request: Request): Promise<Response> {
    if (request.headers.get("Upgrade") !== "websocket") return json({ ok: false, error: "WEBSOCKET_REQUIRED" }, 426);
    const url = new URL(request.url);
    const pair = new WebSocketPair();
    const sockets = Object.values(pair);
    const client = sockets[0], server = sockets[1];
    if (!client || !server) return json({ ok:false, error:"WEBSOCKET_PAIR_FAILED" }, 500);
    const device = url.searchParams.get("device_id") || "unknown";
    this.ctx.acceptWebSocket(server, [`device:${device.slice(0, 180)}`]);
    server.serializeAttachment({ device_id: device.slice(0, 180), connected_at: nowIso() });
    server.send(JSON.stringify({ type: "REALTIME_READY", at: nowIso() }));
    return new Response(null, { status: 101, webSocket: client });
  }

  async broadcast(event: Pick<EventRow, "event_id" | "event_type" | "entity_type" | "entity_id" | "business_date" | "authority_epoch" | "authority_seq" | "service_generation" | "new_version">): Promise<number> {
    const message = JSON.stringify({ type: "DELTA", event });
    let delivered = 0;
    for (const ws of this.ctx.getWebSockets()) {
      try { ws.send(message); delivered++; } catch { /* disconnected sockets are ignored */ }
    }
    return delivered;
  }

  async connectionCount(): Promise<number> { return this.ctx.getWebSockets().length; }

  override webSocketMessage(ws: WebSocket, message: string | ArrayBuffer): void {
    if (typeof message === "string" && message === "ping") ws.send("pong");
  }

  override webSocketClose(_ws: WebSocket, _code: number, _reason: string, _wasClean: boolean): void {
    // Current compatibility dates auto-complete the close handshake.
  }
}
