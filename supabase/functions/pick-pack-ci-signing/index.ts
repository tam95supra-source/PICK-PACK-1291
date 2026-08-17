import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const GITHUB_ISSUER = "https://token.actions.githubusercontent.com";
const GITHUB_JWKS = `${GITHUB_ISSUER}/.well-known/jwks`;
const EXPECTED_AUDIENCE = "pick-pack-1291-signing";
const EXPECTED_REPOSITORY = "tam95supra-source/pick-pack-1291";
const EXPECTED_REPOSITORY_ID = "1336671490";
const EXPECTED_OWNER_ACTOR_ID = "314647579";
const EXPECTED_REF = "refs/heads/main";
const EXPECTED_WORKFLOW_REF = `${EXPECTED_REPOSITORY}/.github/workflows/beta-preview.yml@${EXPECTED_REF}`;

const admin = createClient(SUPABASE_URL, SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

let jwksCache: { expiresAt: number; keys: JsonWebKey[] } | null = null;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, max-age=0",
      "pragma": "no-cache",
    },
  });
}

function decodeBase64Url(input: string): Uint8Array {
  let value = input.replace(/-/g, "+").replace(/_/g, "/");
  while (value.length % 4) value += "=";
  const raw = atob(value);
  return Uint8Array.from(raw, (ch) => ch.charCodeAt(0));
}

function decodeJsonSegment<T>(input: string): T {
  return JSON.parse(new TextDecoder().decode(decodeBase64Url(input))) as T;
}

async function githubKeys(): Promise<JsonWebKey[]> {
  const now = Date.now();
  if (jwksCache && jwksCache.expiresAt > now) return jwksCache.keys;
  const response = await fetch(GITHUB_JWKS, {
    headers: { accept: "application/json", "user-agent": "pick-pack-1291-ci-signing" },
  });
  if (!response.ok) throw new Error(`OIDC_JWKS_HTTP_${response.status}`);
  const body = await response.json() as { keys?: JsonWebKey[] };
  if (!Array.isArray(body.keys) || body.keys.length === 0) throw new Error("OIDC_JWKS_EMPTY");
  jwksCache = { expiresAt: now + 5 * 60_000, keys: body.keys };
  return body.keys;
}

function audienceMatches(value: unknown): boolean {
  if (typeof value === "string") return value === EXPECTED_AUDIENCE;
  return Array.isArray(value) && value.some((item) => item === EXPECTED_AUDIENCE);
}

async function verifyGithubOidc(token: string): Promise<Record<string, unknown>> {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("OIDC_FORMAT");

  const header = decodeJsonSegment<Record<string, unknown>>(parts[0]);
  const claims = decodeJsonSegment<Record<string, unknown>>(parts[1]);
  if (header.alg !== "RS256" || header.typ !== "JWT" || typeof header.kid !== "string") {
    throw new Error("OIDC_HEADER");
  }

  const keys = await githubKeys();
  const jwk = keys.find((key) => key.kid === header.kid && key.kty === "RSA");
  if (!jwk) throw new Error("OIDC_KID");

  const publicKey = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const validSignature = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    publicKey,
    decodeBase64Url(parts[2]),
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
  );
  if (!validSignature) throw new Error("OIDC_SIGNATURE");

  const now = Math.floor(Date.now() / 1000);
  const exp = Number(claims.exp ?? 0);
  const nbf = Number(claims.nbf ?? 0);
  const iat = Number(claims.iat ?? 0);
  if (claims.iss !== GITHUB_ISSUER || !audienceMatches(claims.aud)) throw new Error("OIDC_TRUST");
  if (!Number.isFinite(exp) || exp <= now || !Number.isFinite(iat) || iat > now + 60 || iat < now - 900) {
    throw new Error("OIDC_TIME");
  }
  if (Number.isFinite(nbf) && nbf > now + 30) throw new Error("OIDC_NBF");

  if (
    claims.repository !== EXPECTED_REPOSITORY ||
    String(claims.repository_id ?? "") !== EXPECTED_REPOSITORY_ID ||
    String(claims.actor_id ?? "") !== EXPECTED_OWNER_ACTOR_ID ||
    claims.ref !== EXPECTED_REF ||
    claims.workflow_ref !== EXPECTED_WORKFLOW_REF ||
    claims.repository_visibility !== "public" ||
    claims.runner_environment !== "github-hosted"
  ) {
    throw new Error("OIDC_SCOPE");
  }

  const eventName = String(claims.event_name ?? "");
  if (eventName !== "push" && eventName !== "workflow_dispatch") throw new Error("OIDC_EVENT");
  return claims;
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ ok: false, error: "METHOD_NOT_ALLOWED" }, 405);
  const auth = req.headers.get("authorization") ?? "";
  if (!auth.startsWith("Bearer ")) return json({ ok: false, error: "OIDC_REQUIRED" }, 401);

  try {
    const claims = await verifyGithubOidc(auth.slice(7).trim());
    const { data, error } = await admin.rpc("pp_ci_signing_bundle");
    if (error || !data) throw new Error("SIGNING_BUNDLE_UNAVAILABLE");

    // Do not log or persist the returned signing material. The GitHub runner keeps
    // it only in RUNNER_TEMP and deletes it in an always() cleanup step.
    return json({
      ok: true,
      repository: claims.repository,
      workflow_ref: claims.workflow_ref,
      ...data,
    });
  } catch (error) {
    const code = error instanceof Error ? error.message : "OIDC_REJECTED";
    console.error(code.slice(0, 120));
    return json({ ok: false, error: code }, code.startsWith("OIDC_") ? 401 : 503);
  }
});
