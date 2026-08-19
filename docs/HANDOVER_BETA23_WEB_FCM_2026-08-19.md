# HANDOVER — BETA23 / WEB PRODUCTION / FCM — 2026-08-19

Status: **IMMUTABLE RELEASE CHECKPOINT**

This handover supersedes Beta22 as the current Android Beta release baseline. Older handovers remain historical evidence only. This file does **not** authorize failback, Stable publication, or PR merge.

## 1. Current architecture — unchanged OWNER lock

`Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`

- Cloudflare Worker Service + D1 are the normal operational primary.
- Durable Objects/WebSocket provide realtime invalidation.
- Google Sheets is operational replica / compatibility / fallback / DR.
- GAS is discovery / compatibility / fallback bridge and Android OTA `update_check`.
- Android SQLite/cache is local projection/offline state.
- Firebase is used only for Android FCM wake/invalidation, not as an auth/database/storage authority.

No new authority/backend is introduced by this release.

## 2. Current published Android Beta baseline

Current published Beta is:

- versionName: `0.4.2-beta.23`
- versionCode: `29`
- package: `vn.pickpack1291.app.beta.publicbeta`
- APK: `pick-pack-1291-public-beta-0.4.2-beta.23.apk`
- APK size: `12810579` bytes
- APK SHA-256: `ea561b034a78147cc3df35f6bc2ddef3f8850b812c3c872b58bf65153b4ca5c4`
- signer SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- Beta Drive file id: `1C3Odx5NbnBiyvIplFpDZq6r5O-ealtzV`
- checksum file: `SHA256SUMS-beta23.txt`
- checksum Drive file id: `1QW08lHELDz4AoCdBVnIXR7IDxStcXJWB`

Build/sign evidence:

- `ops/session2-beta23-build-candidate-result.txt`
- build `PASS`
- signing `PASS`
- signer digest matched the locked OWNER signer
- GitHub artifact id `9364146648`

Drive/OTA evidence:

- uploaded Drive APK was downloaded back through the connected Drive account and re-hashed byte-for-byte; SHA and size matched the signed release candidate.
- GAS `update_check` selected Beta23 over Beta22.
- GAS OTA logic set the selected APK to `ANYONE_WITH_LINK / VIEW` when necessary.
- live OTA verifier returned `beta_discovery=PASS`, public partial download HTTP `206`, `beta_download=PASS`.
- Stable discovery returned `EMPTY`.
- evidence file: `ops/session2-beta23-ota-live-verify-result.txt`.

Stable remains **UNPUBLISHED / EMPTY / UNTOUCHED**.

## 3. Firebase / FCM configuration

Approved Firebase client project for Beta23:

- Firebase project id: `pick-pack-1291-fcm-20260819`
- Android package: `vn.pickpack1291.app.beta.publicbeta`
- `app/google-services.json` contains the approved Android client metadata.

Production Worker sender credential:

- Cloudflare secret name: `FCM_SERVICE_ACCOUNT_JSON`
- secret value is not stored in GitHub and must never be copied into chat/docs/source.
- sanitized Cloudflare API check confirmed exactly one `secret_text` binding with this name.
- evidence: `ops/session2-fcm-secret-diagnostic-result.txt`.

Service implementation:

- `service/src/push.ts` accepts `FCM_SERVICE_ACCOUNT_JSON` and derives project/client/private-key fields in memory.
- legacy split FCM env fields remain compatibility-only fallback in source.
- canonical day mutations are staged deterministically from the durable event log into `push_outbox` as `DAY_CHANGED` so the wake signal is not dependent on a fragile post-commit side effect.
- master import already enqueues `MASTER_CHANGED`.
- FCM remains invalidation-only; Android pulls authoritative Service/D1 state after wake.

Important acceptance boundary:

- Cloudflare secret presence, source support and production deploy are proven.
- **A real Beta23 physical PDA obtaining a token and receiving an actual FCM wake has not been proven by this release workflow. Do not fabricate this acceptance evidence.**

## 4. Production Web / Service completion

Production Web/Admin was deployed through the guarded V9 flow after fixing the prior deploy-gate defects.

Final guarded production deploy evidence:

- source and credentials: `PASS`
- D1 resolution: `PASS`
- Service authority gate: `PASS`
- Google fallback gate: `PASS`
- D1 safety gate: `PASS`
- Cloudflare deploy: `PASS`
- live Web/API verification: `PASS`
- fallback ledger recheck: `PASS`
- verdict: `PASS`
- evidence: `ops/session2-product-deploy-v9-result.txt`

Production Web includes the full dashboard/admin presentation, realtime `DAY_CHANGED` / `MASTER_CHANGED`, import UI/backend integration and SUPERADMIN full-history route. The prior history `307` was an authentication redirect, not a missing page; live protected APIs correctly return `401` without auth.

## 5. Gate defects corrected during this release

The following were workflow/diagnostic defects, not production data failures:

1. `system_meta` uses `key/value`; old diagnostics queried nonexistent `meta_key/meta_value`.
2. Cloudflare D1 migration state already had `0001`–`0004` applied; old gate ordering queried new schema before migration verification.
3. Google fallback sheet column is `ingest_status`; an old gate looked for `status`.
4. Runtime Wrangler config placed under `/tmp` caused relative `src/entry_product.ts` resolution to fail. Runtime config is now created inside `service/`.
5. GitHub Google OAuth refresh token does not have Drive scope; OTA publication therefore uses the connected Google Drive path instead of pretending the old OAuth can upload.
6. Android release build uses Gradle `9.4.1` + Android SDK 36/build-tools 36.0.0; this repository does not rely on a Gradle wrapper for the release candidate workflow.

None of these fixes authorize production data rewriting or failback.

## 6. Last explicit authority/fallback evidence

The last explicit numbered checkpoint before this handover recorded:

- Service: `SERVICE_PRIMARY`, epoch `6`, seq `4`, scope `PRODUCTION`, generation `m2-prod-20260819-001`.
- GAS: `GOOGLE_FALLBACK`, epoch `7`, seq `4`, same generation.
- D1 replication: `HEALTHY`, pending `0`.
- D1 epoch-7 fallback inbox: `0` rows.
- Google hidden fallback ledger: epoch 7 seq `1..4`, contiguous and `PENDING`.

The later V9 deploy revalidated Service/GAS/D1/fallback gates and confirmed the fallback set remained unchanged after deployment, but failback must still use a newly fetched numbered checkpoint immediately before any authority transition.

No `7→8` failback has been executed or authorized by this handover.

## 7. Current acceptance / remaining Definition of Done

Completed:

- Beta23 build/sign/package/version verification.
- Beta23 Drive roundtrip integrity verification.
- Beta23 GAS OTA discovery and public download verification.
- Stable-empty verification.
- Web production guarded deployment and live verification.
- FCM client configuration in Beta23.
- FCM production secret binding presence.
- production Service source support for one-secret Firebase service-account credential.
- durable `DAY_CHANGED` staging from canonical event log.

Still not allowed to infer as complete:

- real physical Beta23 PDA FCM wake delivery.
- full real-PDA Beta23 business acceptance across required enter/exit/labor/resource cases.
- exact Web + Beta23 concurrent/realtime acceptance on real clients.
- controlled failback/reconciliation.
- final DR both directions and final integrity closure.

## 8. Safety locks

- PR #38 remains **draft / open / unmerged**.
- Do not merge without explicit OWNER approval after full Definition of Done.
- Do not publish Stable without explicit OWNER command.
- Do not change Android signer.
- Do not overwrite/delete production Google Sheet data.
- Preserve historical fallback rows/checksums and rollback backup.
- Do not expose Firebase service-account JSON, signing secrets, auth tokens, verifier/password material, OAuth credentials or bridge secrets.
- Do not ask OWNER to use local CLI.

## 9. Immediate continuation order

1. Treat Beta23, not Beta22, as the current Beta release baseline.
2. Run real physical Beta23 PDA smoke, including actual FCM wake evidence and genuinely missing business acceptance rows.
3. Run exact Web + Beta23 concurrent/realtime acceptance.
4. Fetch a fresh numbered Service/GAS/D1/Google fallback checkpoint.
5. Only if every failback precondition matches, execute the controlled failback sequence under the existing OWNER rules.
6. Complete DR/final integrity closure.
7. Merge PR only after explicit OWNER approval.
