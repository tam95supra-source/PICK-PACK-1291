import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const WORKER_SECRET = Deno.env.get("PP_PROJECTION_WORKER_SECRET") ?? "";
const SHEET_WEBHOOK_URL = Deno.env.get("PP_SHEET_WEBHOOK_URL") ?? "";
const SHEET_WEBHOOK_SECRET = Deno.env.get("PP_SHEET_WEBHOOK_SECRET") ?? "";

const BATCH_SIZE = 100;
const ALLOWED_SHEETS = new Set(["RA - VÀO TRONG CA", "CÔNG NHẬT"]);

type ProjectionRow = {
  event_id: string;
  server_seq: number | null;
  sheet_name: string;
  row_data: Record<string, unknown>;
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function configured(): boolean {
  return Boolean(
    SUPABASE_URL &&
      SERVICE_ROLE_KEY &&
      WORKER_SECRET &&
      SHEET_WEBHOOK_URL &&
      SHEET_WEBHOOK_SECRET,
  );
}

function restHeaders(extra: Record<string, string> = {}): HeadersInit {
  return {
    apikey: SERVICE_ROLE_KEY,
    authorization: `Bearer ${SERVICE_ROLE_KEY}`,
    "content-type": "application/json",
    ...extra,
  };
}

function truncateError(value: unknown): string {
  const message = value instanceof Error ? value.message : String(value ?? "UNKNOWN");
  return message.replace(/[\r\n\t]+/g, " ").slice(0, 500);
}

async function loadPending(): Promise<ProjectionRow[]> {
  const url = new URL(`${SUPABASE_URL}/rest/v1/pp_sheet_projection_queue`);
  url.searchParams.set("select", "event_id,server_seq,sheet_name,row_data");
  url.searchParams.set("sheet_ack_at", "is.null");
  url.searchParams.set("order", "server_seq.asc,created_at.asc");
  url.searchParams.set("limit", String(BATCH_SIZE));

  const response = await fetch(url, { headers: restHeaders() });
  if (!response.ok) {
    throw new Error(`QUEUE_READ_HTTP_${response.status}`);
  }

  const rows = (await response.json()) as ProjectionRow[];
  for (const row of rows) {
    if (!row.event_id || !ALLOWED_SHEETS.has(row.sheet_name) || !row.row_data) {
      throw new Error(`QUEUE_CONTRACT_INVALID:${row.event_id || "missing-event-id"}`);
    }
  }
  return rows;
}

async function patchRows(eventIds: string[], patch: Record<string, unknown>): Promise<void> {
  if (eventIds.length === 0) return;
  const quoted = eventIds.map((id) => `"${id.replaceAll('"', "")}"`).join(",");
  const url = new URL(`${SUPABASE_URL}/rest/v1/pp_sheet_projection_queue`);
  url.searchParams.set("event_id", `in.(${quoted})`);

  const response = await fetch(url, {
    method: "PATCH",
    headers: restHeaders({ Prefer: "return=minimal" }),
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    throw new Error(`QUEUE_PATCH_HTTP_${response.status}`);
  }
}

async function sendToSheet(rows: ProjectionRow[]): Promise<string[]> {
  const response = await fetch(SHEET_WEBHOOK_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      mode: "pp_projection",
      secret: SHEET_WEBHOOK_SECRET,
      events: rows,
    }),
  });

  const text = await response.text();
  let body: Record<string, unknown> = {};
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`SHEET_BAD_JSON_HTTP_${response.status}`);
  }

  if (!response.ok || body.ok !== true || !Array.isArray(body.ack_event_ids)) {
    const code = typeof body.error === "string" ? body.error : `HTTP_${response.status}`;
    throw new Error(`SHEET_REJECTED:${code}`);
  }

  const sent = new Set(rows.map((row) => row.event_id));
  const ackIds = (body.ack_event_ids as unknown[])
    .filter((id): id is string => typeof id === "string" && sent.has(id));

  if (ackIds.length !== rows.length) {
    throw new Error(`SHEET_PARTIAL_ACK:${ackIds.length}/${rows.length}`);
  }
  return ackIds;
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ ok: false, error: "METHOD_NOT_ALLOWED" }, 405);
  if (!configured()) return json({ ok: false, error: "PROJECTION_NOT_CONFIGURED" }, 503);
  if (req.headers.get("x-pp-worker-secret") !== WORKER_SECRET) {
    return json({ ok: false, error: "UNAUTHORIZED" }, 403);
  }

  let pending: ProjectionRow[] = [];
  try {
    pending = await loadPending();
    if (pending.length === 0) {
      return json({ ok: true, exported: 0, pending_batch: 0 });
    }

    const ackIds = await sendToSheet(pending);
    await patchRows(ackIds, {
      sheet_ack_at: new Date().toISOString(),
      last_error: null,
    });

    return json({
      ok: true,
      exported: ackIds.length,
      first_server_seq: pending[0]?.server_seq ?? null,
      last_server_seq: pending[pending.length - 1]?.server_seq ?? null,
    });
  } catch (error) {
    const safeError = truncateError(error);
    const ids = pending.map((row) => row.event_id);
    try {
      await patchRows(ids, { last_error: safeError });
    } catch {
      // Preserve the primary error; diagnostics must never turn a failed export into a false success.
    }
    return json({ ok: false, error: safeError, attempted: ids.length }, 502);
  }
});
