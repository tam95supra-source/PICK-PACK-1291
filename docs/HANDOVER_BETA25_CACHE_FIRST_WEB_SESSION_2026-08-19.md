# HANDOVER — BETA25 CACHE-FIRST + WEB SESSION ISOLATION — 2026-08-19

Status: **ACTIVE RELEASE CHECKPOINT / IMMUTABLE**

This checkpoint supersedes Beta23/Beta24 as the current Android Beta release authority. Older handovers remain historical evidence only.

## 1. Owner-locked architecture

Normal architecture remains:

`Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`

with Google Sheets as operational replica/compatibility/fallback/DR, GAS as discovery/compatibility/fallback/OTA bridge, Android SQLite as the PDA local projection, Durable Object WebSocket invalidation in foreground, and FCM wake/invalidation only for Android background/closed state.

No Firebase DB/Auth/Storage business authority was introduced.

## 2. User defects addressed in this release

### A. PDA showed “Google Drive” and felt extremely slow

Fresh runtime evidence showed Cloudflare Service itself was healthy. The reason PDAs routed to Google was authority fencing: Service remained `SERVICE_PRIMARY` epoch 6 while GAS discovery remained `GOOGLE_FALLBACK` epoch 7. Android correctly obeyed GAS discovery instead of bypassing the fence.

Beta25 does **not** lie about this state. The UI now labels it `Google dự phòng`, not as if Google were the Cloudflare Service. It also removes network dependency from hot operational screens by reading SQLite first.

No 7→8 failback was performed merely to hide this status.

### B. Shared PDA history did not hydrate correctly in fallback

Root cause: legacy GAS fallback `sync_status` intentionally emits blank `retention_floor` for old Beta17 SQLite recovery compatibility, while the newer client required nonblank `retention_floor` before starting `OperationalSyncEngine.reconcile`. The client therefore received `day_revisions` but could fail to hydrate canonical day snapshots into SQLite.

Beta25 compatibility fix:

- use `retention_floor` when present;
- otherwise use GAS `server_retention_floor`;
- preserve exact canonical business-window semantics;
- do not change old GAS response shape required by historical clients.

Shared History renders from the local canonical day snapshot and asks foreground sync for a non-blocking revision reconcile. When the canonical snapshot changes, the atomic SQLite save re-renders the relevant screen.

### C. Employee appeared quickly but session/labor/resource state still waited on network

Beta25 hot operational screens are local-cache-first:

- employee/session context: SQLite/master projection first;
- labor context: SQLite session + labor overlay first;
- resource editor: SQLite session/resource occupancy first;
- network/revision sync runs after render and updates atomically;
- remote employee/master lookup remains cache-miss recovery only.

The PDA store retains the exact seven canonical business sessions N..N-6. N/N-1 are the hot operational subset, while the full N..N-6 window remains available under the existing permission rules.

### D. ACK-to-snapshot UI regression gap

A second issue was found after Beta24: once a local outbox event changed from `LOCAL_PENDING` to `CONFIRMED`, the optimistic overlay stopped applying before the next canonical day snapshot arrived. The screen could briefly regress to stale state.

S27/Beta25 adds `projectionMutations()`:

- unsent/retry rows remain send candidates;
- newly `CONFIRMED` rows continue to participate in the local projection only while their ack timestamp is newer than the saved canonical day snapshot;
- confirmed rows are never resent by this projection method;
- once the newer day snapshot is saved, the temporary confirmed overlay naturally disappears.

This closes the visible ACK-to-next-snapshot gap without weakening idempotency or authority rules.

### E. Sync screen lacked useful project state

Beta25 Sync screen now exposes operationally useful details from local/runtime state, including:

- network and validated Internet state;
- measured latency when available;
- authority mode and actual route/provider;
- upload/download direction/rate state;
- pending mutations and review/rejected items;
- local cache date count;
- hot N/N-1 dates;
- full N..N-6 business window and day revisions;
- master revision and staff count;
- Service URL presence/generation/epoch/seq;
- foreground realtime mode;
- FCM client registration state;
- last runtime error.

Opening Sync remains local-first and does not add a constant polling loop.

### F. Web login form remained over the logged-in app

Root cause: `.login-wrap{display:grid}` overrode the browser `hidden` presentation. Production CSS now explicitly has:

`.login-wrap[hidden], .admin-app[hidden], .notice[hidden] { display:none!important; }`

Live production diagnostic verifies this rule and the current Web application source.

### G. Web and PDA logins kicked each other out

Root cause: backend stored one `auth_sessions` row per login.

Migration `0005_web_session_isolation.sql` introduced a separate Web session slot without deleting or replacing the PDA session table.

Current behavior:

- one active PDA slot per login remains in `auth_sessions`;
- one active Web slot per login is in `auth_web_sessions`;
- Web login sends `client_source='WEB'`;
- a PDA login does not invalidate the Web slot;
- a Web login does not invalidate the PDA slot;
- a second Web login for the same account replaces the previous Web session;
- Web logout deletes only the current Web session; PDA logout deletes only the current PDA session.

This implements the owner requirement that Web and App/PDA are separate device classes, while Web remains active until another Web login for that account replaces it.

## 3. Production Web / Service evidence

Production Web v10 deploy applied the Web session migration and Web fixes.

Evidence:

- `ops/session2-product-deploy-v10-web-session-result.txt`: source/D1/migration/deploy phases PASS; the old bundled live-check script exited later because of its own verification assumptions.
- `ops/session2-web-v10-live-diagnostic-result.txt`: health HTTP 200, app HTTP 200, Web `client_source=WEB` source PASS, CSS hidden rule PASS, unauthenticated sync correctly 401, capabilities HTTP 200, verdict PASS.
- `ops/session2-post-v10-safety-diagnostic-result.txt`: migration 0005 PASS, PDA session preserved, D1 safety PASS.
- `ops/session2-beta25-live-verify-result.txt`: current Web live PASS after Beta25 publication.

## 4. Current Beta release

Published Beta:

- versionName: `0.4.2-beta.25`
- versionCode: `31`
- package: `vn.pickpack1291.app.beta.publicbeta`
- APK: `pick-pack-1291-public-beta-0.4.2-beta.25.apk`
- size: `12810579` bytes
- SHA-256: `5ba70c6ed1c377c41a72f5f1bfe71b8accad6231a147c044614e66a585690aed`
- signer SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- signed candidate artifact id: `9367409356`
- Beta Drive APK id: `1YvFDNEZpNlCC3EcCm3uMR1WkY7YEzn0q`
- checksum file: `SHA256SUMS-beta25.txt`
- Beta Drive checksum id: `18uwHX3A3BwjBWd-j3_v4iNeX4iJeMptL`

Evidence:

- `ops/session2-beta25-build-candidate-result.txt`: config/build/sign PASS, signer/package/version verified.
- downloaded candidate artifact was re-hashed locally before Drive upload and exactly matched the recorded SHA/size/checksum.
- `ops/session2-beta25-release-record.txt`: exact connected-Drive publication record.
- `ops/session2-beta25-live-verify-result.txt`: GAS discovers Beta25, full public APK download re-hashes correctly, Stable OTA remains EMPTY, verdict PASS.

The attempted OAuth workflow publish stopped in `SAFETY` before upload because that GitHub Google OAuth refresh token does not carry Drive scope. It did not create a duplicate or partial Beta25 file. Publication therefore used the already-connected Google Drive account and the exact signed candidate artifact. This is recorded explicitly rather than presenting the failed OAuth path as successful.

Stable is still **EMPTY / UNPUBLISHED / UNTOUCHED**.

## 5. Fresh authority / D1 checkpoint

`ops/session2-beta25-live-verify-result.txt` currently records:

- Service: `SERVICE_PRIMARY | epoch 6 | seq 4 | PRODUCTION | m2-prod-20260819-001`
- GAS discovery: `GOOGLE_FALLBACK | epoch 7 | seq 5 | m2-prod-20260819-001`
- Beta OTA: `0.4.2-beta.25`
- Beta public download: PASS
- Stable OTA: EMPTY
- Web live: PASS

Fresh read-only D1 diagnostic `ops/session2-d1-gate-diagnostic-result.txt` at 2026-08-19T13:40:21Z records:

- D1 production resolved;
- Service authority `SERVICE_PRIMARY|6|4|PRODUCTION|m2-prod-20260819-001`;
- epoch-7 D1 fallback inbox count `0`;
- replication `HEALTHY|0|0|`;
- no active reconciliation metadata row;
- diagnostic complete.

Important: GAS authority sequence increased to 5 while D1 epoch-7 inbox remains 0. This means a new fallback-authority event exists on the Google side but has not been ingested/failback-applied to D1. Do **not** flush/reconcile/failback merely because Beta25 is published. Re-read the Google fallback ledger and all failback preconditions first when owner later authorizes that stage.

## 6. Realtime behavior boundary

In normal `SERVICE_PRIMARY` mode:

- foreground: Durable Object WebSocket invalidation (`DAY_CHANGED`, `MASTER_CHANGED`) → revision/delta pull;
- background/closed Android: FCM invalidation → WorkManager authoritative catch-up;
- other PDAs converge through the same canonical Service state.

While GAS discovery remains `GOOGLE_FALLBACK`, Android must continue to obey the authority fence. Beta25 fixes cache hydration and local-first UX under fallback, but it does not pretend fallback has Service-primary WebSocket realtime. Cross-PDA freshness in fallback occurs when the revision sync trigger runs (start/login/reconnect/manual/background work), not by bypassing the authority fence.

The intended realtime multi-PDA path becomes active again only after a safe controlled return to Service authority.

## 7. Physical acceptance still required

CI and connected-service evidence cannot substitute for real PDA behavior. The following still require owner/physical verification on Beta25:

- scan employee/session shows immediately from cache after first hydration;
- enter/exit stays visually coherent through LOCAL_PENDING → CONFIRMED → new canonical snapshot;
- labor start/finish is immediate from local projection;
- shared History appears from local canonical cache on both PDAs after sync;
- resource occupancy/edit flow remains correct;
- Web and PDA stay logged in concurrently for the same account;
- logging into a second Web invalidates only the first Web, not the PDA;
- physical FCM background/closed wake delivery;
- Service-primary cross-PDA WebSocket realtime after any later authorized failback.

Do not fabricate any of these physical acceptance rows.

## 8. Safety locks

- PR #38 remains draft/open/unmerged.
- No merge without explicit OWNER approval.
- No Stable publish without explicit OWNER command.
- Android signer is fixed and unchanged.
- No destructive production Google Sheet overwrite/delete/reset.
- Preserve fallback ledger/checksum integrity and rollback backups.
- No secrets in source/chat/docs.
- Do not ask OWNER to run local CLI.
- No controlled 7→8 failback until real-client acceptance and a fresh failback precondition checkpoint are both satisfied.

## 9. Immediate continuation

1. Owner installs/receives Beta25 by normal Beta OTA and performs the listed real-PDA checks.
2. Capture only genuine physical acceptance evidence and any fresh logs.
3. If defects remain, fix forward in a new Beta without touching Stable.
4. If Beta25 real-client acceptance passes, re-read Service/GAS/D1/Google fallback ledger and replication state.
5. Only under the existing owner-controlled failback rules may reconciliation/failback be considered.
6. PR remains draft until full Definition of Done and explicit OWNER approval.
