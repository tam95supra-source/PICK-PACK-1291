import type { ApiErrorBody, ErrorClass } from "./domain";

export function json(data: unknown, status = 200, extra: HeadersInit = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra },
  });
}

export function apiError(code: string, errorClass: ErrorClass, status: number, retryable = false, message?: string, conflict?: Record<string, unknown> | null): Response {
  const body: ApiErrorBody = { ok: false, error: { code, error_class: errorClass, retryable } };
  if (message) body.error.message = message;
  if (conflict !== undefined) body.error.conflict = conflict;
  return json(body, status);
}

export function nowIso(): string { return new Date().toISOString(); }

export function b64u(bytes: ArrayBuffer | Uint8Array): string {
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let s = "";
  for (const b of arr) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function b64uDecode(value: string): Uint8Array {
  let s = value.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const raw = atob(s);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function hmacB64u(keyBytes: Uint8Array, value: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64u(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value)));
}

export function constantTimeEqual(a: string, b: string): boolean {
  const aa = new TextEncoder().encode(a);
  const bb = new TextEncoder().encode(b);
  const n = Math.max(aa.length, bb.length);
  let diff = aa.length ^ bb.length;
  for (let i = 0; i < n; i++) diff |= (aa[i] ?? 0) ^ (bb[i] ?? 0);
  return diff === 0;
}

export function randomB64u(bytes = 32): string {
  const out = new Uint8Array(bytes);
  crypto.getRandomValues(out);
  return b64u(out);
}

export function validIsoDate(value: string): boolean { return /^\d{4}-\d{2}-\d{2}$/.test(value); }

export function fold(value: unknown): string {
  return String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().trim();
}

export function workChoice(value: unknown): "PICK" | "PACK" | "KHONG" {
  const f = fold(value);
  if (f === "PICK") return "PICK";
  if (f === "PACK") return "PACK";
  return "KHONG";
}

export function isAvailableLabel(value: unknown): boolean {
  const f = fold(value);
  return ["KHA DUNG", "NGUYEN VEN", "ACTIVE", "ONLINE", "HOAT DONG"].includes(f);
}

export function parseVisibleDate(value: string): string {
  const m = String(value).match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : "";
}

export function visibleToIsoTimestamp(value: string): string {
  const m = String(value).match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/);
  if (!m) return nowIso();
  const iso = `${m[3]}-${m[2]}-${m[1]}T${m[4] ?? "00"}:${m[5] ?? "00"}:${m[6] ?? "00"}+07:00`;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? nowIso() : d.toISOString();
}

export async function readJsonBody<T>(request: Request, maxBytes = 1_500_000): Promise<T> {
  const len = Number(request.headers.get("content-length") || "0");
  if (len > maxBytes) throw new Error("BODY_TOO_LARGE");
  const text = await request.text();
  if (text.length > maxBytes) throw new Error("BODY_TOO_LARGE");
  return JSON.parse(text) as T;
}
