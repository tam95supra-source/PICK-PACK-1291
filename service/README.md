# Pick Pack 1291 Service — M1 staging shadow

Cloudflare Worker + D1 + Durable Object implementation for the OWNER-approved M1 Service foundation.

This directory is **not a production cutover**. See `../docs/SERVICE_MIGRATION_M1.md` and `../ARCHITECTURE_GUARDRAILS.md`.

Key files:

- `wrangler.jsonc` — staging Worker/D1/DO configuration template; D1 ID is injected by CI and never hard-coded.
- `migrations/0001_m1_foundation.sql` — production-grade M1 schema.
- `schemas/` — canonical event/API/Google manifest contracts.
- `src/core.ts` — business core mutation rules.
- `src/bootstrap.ts` — exact real-Sheet bootstrap/reconciliation.
- `src/replication.ts` — transactional outbox consumer to Google staging.
- `src/realtime.ts` — Durable Object realtime hub.
- `scripts/m1-bootstrap.mjs` / `scripts/m1-test.mjs` — CI acceptance drivers.

Deployment is performed only through `.github/workflows/service-m1-staging.yml`; do not ask the OWNER to run Wrangler/Node locally.
