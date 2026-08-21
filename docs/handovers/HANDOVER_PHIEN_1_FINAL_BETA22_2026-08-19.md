# HANDOVER PHIÊN 1 FINAL — PICK PACK 1291 — BETA22

**Snapshot:** 2026-08-19 15:49 +07:00 (Asia/Bangkok)  
**Status:** PHIÊN 1 CLOSED / SAFE TO CONTINUE PHIÊN 2  
**Repository:** `tam95supra-source/pick-pack-1291`  
**Branch:** `agent/service-migration-m2`  
**PR:** #38 — keep DRAFT / UNMERGED  

> This handover supersedes stale current-state wording from older Beta19/Beta20 handovers. Historical snapshots remain immutable historical evidence only.

## 1. Current release baseline

- Beta: `0.4.2-beta.22`
- versionCode: `28`
- package: `vn.pickpack1291.app.beta.publicbeta`
- verified OTA APK SHA-256: `da2c1c837102e9e557013971ece9dac961caa6312b579db9c63184acc8daed3b`
- verified OTA size: `9790372` bytes
- Stable: UNPUBLISHED / UNTOUCHED
- Android signer: OWNER-locked / unchanged

Beta19/Beta20 release workflows/evidence are historical only. Obsolete hardcoded Beta19/Beta20 publisher workflows were retired to historical no-op paths so they cannot republish an obsolete APK by accident.

## 2. Owner-approved architecture

Current production architecture is:

`Android / Web-PWA ↔ Cloudflare Worker Service ↔ D1`

with Durable Objects/WebSocket realtime; Google Sheets retained as operational replica/compatibility/fallback/DR; GAS retained as discovery/compatibility/fallback/OTA bridge; Android SQLite/cache retained as local projection/offline state; GitHub retained as source/CI/release.

`AGENTS.md` architecture was reconciled to the Service-first guardrails during Phiên 1. Do not regress to the historical GAS-only architecture.

## 3. Phiên 1 work completed

Phiên 1 completed the baseline/test/performance reconciliation required before later recovery work:

1. Corrected Beta22 as current baseline in current project guidance and PR #38.
2. Added a new immutable Beta22 supersession handover while preserving S12/S13 as historical snapshots.
3. Reconciled `AGENTS.md` to Service-first architecture.
4. Reconciled Release Preflight so Worker/D1 is the production authority gate and GAS is compatibility/OTA only.
5. Retired obsolete Beta19/Beta20 publisher workflows as historical no-op paths.
6. Corrected Chaos test contract without weakening runtime authorization/business rules.
7. Corrected App Fast Check PR-history handling and added GAS syntax validation.
8. Optimized GAS `service_discovery` hot path from repeated Script Properties reads to one coherent `getProperties()` snapshot per request; no long-lived authority cache was introduced.
9. Deployed the optimized GAS source through the official deployment workflow.
10. Hardened GAS deployment postverification against transient platform responses.
11. Removed workflow-storm behavior that was repeatedly hitting production GAS/Service from ordinary PR commits.
12. Updated PR #38 description to current Beta22/Service-first state and remaining DoD.

## 4. Performance finding and fix

The high user-visible network number was not evidence of a wrong Cloudflare Worker endpoint.

Observed during Phiên 1:

- Worker health remained stable and healthy.
- Before GAS discovery optimization, a live postcheck obtained only `4/8` valid `service_discovery` samples and observed a severe tail timeout of roughly 15.9 seconds.
- After collapsing Script Properties reads into one coherent snapshot, the next live postcheck obtained `8/8` valid discovery samples.
- A real Beta22 manual log had shown roughly 2729 ms while reporting Cloudflare service, and another roughly 2221 ms while reporting Google fallback. These app values are end-to-end status/sync timings, not a pure ICMP/network ping to the Worker.

A second root cause was CI amplification: PR #38 already contained old live-trigger files, and `pull_request.paths` matched the whole PR diff on later commits. This repeatedly launched production-hitting workflows even when a new commit was unrelated.

Phiên 1 changed the live workflows so ordinary PR commits no longer trigger them:

- GAS deploy: explicit trigger/manual only
- Session1 Live Postcheck: manual only
- Release Preflight: explicit trigger/manual only
- Session1 Failback Observer: only when the failback trigger itself changes

This workflow-storm cleanup is part of the performance fix and must be preserved.

## 5. Last verified live state after optimization

Last successful post-optimization live verification recorded:

### Service / D1

- environment: production
- generation: `m2-prod-20260819-001`
- mode: `SERVICE_PRIMARY`
- authority epoch: `6`
- authority seq: `3`
- scope: `PRODUCTION`
- replication: `HEALTHY`
- replication pending: `0`
- D1 reconciling: `0`
- epoch-7 fallback inbox in D1: `0`
- latest migration includes `0004_session1_foundation.sql`
- realtime protocol: `INVALIDATION_V1`
- PWA `DAY_CHANGED` / recovery-route checks passed

### GAS / Google fallback

- mode: `GOOGLE_FALLBACK`
- fallback authority epoch: `7`
- authority seq: `3`
- generation matched Service
- `service_discovery`: `8/8` valid samples in the post-optimization live check
- hidden fallback ledger: exactly 3 epoch-7 PENDING rows, sequence 1–3
- all three current pending rows were generated by Beta22

### Deployment verification

The final GAS deployment run observed during Phiên 1 completed successfully, including source validation, deployment update, discovery/reset/OTA postverification. The deployment created version 72 at that checkpoint.

No 7→8 failback occurred during Phiên 1.

## 6. Fresh CI evidence obtained in Phiên 1

Fresh corrected source/test evidence obtained after reconciliation included:

- Service M2 Chaos Matrix: PASS
- Service M2 Chaos Matrix V2: PASS
- Service M2 Precutover: PASS
- Session1 Apply Gate: PASS
- Session1 Deploy Observer: PASS
- Session1 Service E2E: PASS
- Session1 Live Postcheck after GAS optimization: PASS
- Release Preflight after Service-first reconciliation: PASS at its deliberate checkpoint
- App Fast Check: PASS at the corrected checkpoint before final trigger-only documentation cleanup

The final trigger-only/documentation commits can cause ordinary source CI to queue again because those source CI workflows still run on PR changes. Do not mistake a queued/cancelled duplicate run caused by a newer docs-only commit for a regression. Re-fetch the latest HEAD and inspect the exact changed files before interpreting it.

## 7. Beta22 acceptance evidence — NOT FULLY CLOSED

Current evidence proves:

- Beta22 source/OTA/package metadata is current and valid.
- A real Beta22 Android device produced runtime logs.
- A real Beta22 device produced fallback business events.
- Exactly three current Beta22 epoch-7 pending fallback events exist.
- Those three events are `enter` operations.

This does NOT prove every formal physical/business acceptance row. Do not infer or fabricate PASS for missing cases.

Still to be completed in Phiên 2:

- reconstruct exact real-PDA Beta22 acceptance and execute only genuinely missing business rows, including EXIT/labor/resource cases where evidence is absent;
- reconstruct exact Web + Beta22 concurrent/realtime acceptance and execute only genuinely missing rows.

## 8. Phiên 2 work order

Phiên 2 may start immediately from this handover. Recommended order:

1. Read this file first, then `docs/HANDOVER_CURRENT.md`, `ARCHITECTURE_GUARDRAILS.md`, `AGENTS.md`, PR #38, current `app/build.gradle.kts`, and current relevant workflow sources.
2. Re-fetch PR #38 HEAD; do not rely on the SHA written in an older snapshot.
3. Reconstruct exact Beta22 PDA and Web-concurrent evidence; test only missing rows.
4. After acceptance is genuinely closed, perform a fresh read-only Service/GAS/D1/Google fallback checkpoint.
5. Only if every precondition exactly matches, execute controlled failback/reconciliation from Service epoch 6 / GAS fallback epoch 7 toward the planned fresh Service epoch 8.
6. Complete DR both directions only in the approved safe recovery/staging paths.
7. Complete final replication/integrity verification.
8. Create production-complete handover.
9. Keep PR #38 draft/unmerged until full DoD and explicit OWNER approval.

## 9. Failback stop rules for Phiên 2

Do NOT execute failback merely because a trigger/workflow exists. Immediately before failback, freshly verify all of the following:

- PR #38 current head and draft/unmerged state;
- Beta22 remains current or a newer Beta is explicitly published and documented;
- Service is exactly in the expected pre-failback production state;
- GAS is exactly in the expected fallback state;
- fallback event count/sequence/generation are exactly expected or explicitly explained;
- replication is healthy;
- D1 reconciling is off;
- D1 fallback inbox is consistent;
- no concurrent mutating deploy/recovery workflow is active;
- Stable remains forbidden;
- signer unchanged;
- production Sheet must not be overwritten/deleted.

Any mismatch means abort the risky transition and report the difference instead of forcing state.

## 10. Permanent safety locks

- Never publish Stable without explicit OWNER command.
- Never merge PR #38 without explicit OWNER approval after full DoD.
- Never change Android signer.
- Never overwrite/delete/reset production Google Sheet data as a shortcut.
- Preserve mandatory pre-Service rollback backup.
- Preserve historical fallback rows/checksums; do not retroactively rewrite legacy rows merely to sanitize them.
- Never expose secrets, passwords, verifier values, tokens, OAuth credentials, signing material or sensitive legacy fallback payloads.
- Never ask OWNER to use local CLI/terminal; use assistant-controlled tooling/CI/browser flows.
- Do not introduce a new backend/datastore/queue/auth authority without a new OWNER instruction.

## 11. Phiên 1 close decision

**Phiên 1 is complete and may be closed.**

The project as a whole is NOT complete. Remaining Beta22 formal acceptance, controlled failback/reconciliation, DR, final integrity verification and production-complete handover belong to Phiên 2 and later closure work.
