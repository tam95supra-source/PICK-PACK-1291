# BUILD / RELEASE PLAYBOOK — PICK PACK 1291

Status: **CHỐT / authoritative operating procedure**  
Effective from: 2026-08-18

Purpose: make normal code validation fast, make Beta/Stable release validation deterministic, and prevent recurring CI/release failures without weakening correctness.

## 1. Release architecture

Operational architecture remains:

`Android App ↔ Google Apps Script ↔ Google Sheets`

Release/update architecture remains:

`Android -> GAS update_check -> Google Drive channel folder`

- Beta OTA reads only `BẢN THỬ NGHIỆM`.
- Stable OTA reads only `BẢN ỔN ĐỊNH`.
- GitHub Releases are not steady-state OTA authority.
- Preserve the fixed Android signing identity for in-place upgrades.
- Never introduce a new backend/signing/storage authority just to make a build easier.

## 2. Two-tier CI model

### Tier A — App Fast Check

Runs on ordinary app/source changes.

Purpose:

- fail quickly on source/UX/architecture regressions
- validate both channel variants without running external live probes
- provide routine feedback in minutes, not a full release cycle

Required gates:

- architecture/static invariants
- launcher artwork hash
- five-tab shell and tab order
- no artificial tab transition implementation
- no banned developer-facing user copy
- no unauthorized backend endpoints
- Beta Debug assemble
- Stable Debug assemble

The fast pipeline must **not**:

- call live GAS/Drive just because a small UI/source edit was pushed
- sign a production APK
- publish OTA
- create GitHub Releases
- commit source, receipts, observers or status files back to `main`

Use workflow concurrency with stale fast checks cancelled when a newer commit arrives.

### Tier B — Release Preflight

Runs only when explicitly requested before release, via browser `workflow_dispatch` or the permanent preflight trigger file used by automation.

Required gates:

- all architecture/UX/static invariants
- source-derived version metadata
- live GAS health
- live BETA and STABLE Drive-channel separation
- Beta Release assemble
- Stable Release assemble
- APK package/version metadata validation
- unsigned Beta candidate artifact
- fixed signing identity validation when the four signing secrets are available

Release Preflight is validation only. It does not upload an OTA APK to Drive and does not publish a GitHub Release.

## 3. OTA publish sequence

A Beta or Stable OTA publish is a separate deliberate action after Release Preflight passes.

Sequence:

1. Confirm target channel and source version/code.
2. Use the already-validated release artifact or rebuild from the exact validated commit.
3. Sign with the official existing signing identity only.
4. Verify signer certificate SHA-256 against the fixed expected identity.
5. Compute APK SHA-256.
6. Put checksum and APK in the correct Google Drive channel folder.
7. Ensure OTA download permission is available through the approved Drive/GAS flow.
8. Call live `update_check` from the previous version and confirm it returns the new version.
9. Download the actual OTA bytes and confirm SHA-256 matches.
10. Confirm the new version does not offer an update to itself.
11. Confirm the other release channel does not see this build.

Do not call a build “released” until all applicable OTA E2E gates pass.

Stable additionally requires owner-approved Beta soak/business testing. A successful build alone is not permission to promote Stable.

## 4. Android SDK fast path

Hosted runners often already contain an Android SDK.

Both permanent pipelines must first check for the **exact required** platform/build-tools version. If present, use it directly.

Only if the exact SDK is absent:

- download the pinned Android command-line tools archive
- verify its known SHA-256
- install the exact required platform/build-tools

This avoids repeatedly downloading/installing the SDK while preserving deterministic tool versions.

## 5. Gradle policy

Current project already enables:

- `org.gradle.parallel=true`
- `org.gradle.caching=true`

GitHub uses `gradle/actions/setup-gradle`, so dependency/build cache reuse remains enabled.

Do not add build-speed flags that weaken correctness or skip required channel validation. Configuration-cache or toolchain changes may be added only after a controlled Beta+Stable compile test.

## 6. Version policy

Never hardcode a release version inside CI logic when the source already defines it.

- `versionCode` and `versionName` are read dynamically from `app/build.gradle.kts`.
- Once an APK version is published to OTA, do not change source behavior under the same version identity.
- New releasable behavior gets a new versionCode/versionName before validation.
- CI must compare packaged APK metadata to source metadata.

## 7. Signing policy

Fixed signer certificate identity must never change accidentally.

Expected signer SHA-256:

`d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`

Signing secrets/material must never be printed, committed or written into public handovers.

Preferred long-term one-click release path uses these four GitHub Secrets once they are confirmed/configured correctly:

- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

Until that configuration is confirmed, use only the existing official signing recovery process. Do not create a replacement key and do not route signing through an unrelated external service.

## 8. Recurring failure catalogue and prevention

### A. Fragile one-line Kotlin patching

Observed failure:

- patches targeted compressed one-line Kotlin
- whitespace/brace differences caused exact-anchor failure
- malformed long expressions caused one parser error to cascade into many fake compiler errors

Prevention:

- write/replace complete multiline functions or components
- require unique marker count before mutation
- fail the patch before Gradle if marker count is not exactly expected
- inspect the first/root compiler error, not every cascade error

### B. Multiline source embedded directly in workflow YAML

Observed failure:

- long Kotlin/Python blocks embedded inside `run: |` broke YAML indentation/parsing

Prevention:

- keep complex transformations in standalone repository scripts
- workflow YAML should invoke the script, not contain the source transformation itself

### C. Dispatching a newly created workflow immediately

Observed failure:

- GitHub returned 422 because the new workflow had not yet been registered for `workflow_dispatch`

Prevention:

- permanent workflows are preferred
- if a temporary workflow is unavoidable, commit the workflow first and trigger it only from a later commit/event

### D. Observer/status workflows writing to `main`

Observed failure:

- observer receipts advanced `main` while the build job was preparing a source commit
- caused rebase/push races

Prevention:

- permanent CI does not write status/receipt files to `main`
- read status through GitHub Actions APIs/UI, job summaries and artifacts
- build jobs do not commit verified source as part of normal CI

### E. CI commit touching `.github/workflows`

Observed failure:

- `GITHUB_TOKEN` could not push a commit that changed workflow files due workflow permission restrictions

Prevention:

- workflows are edited explicitly through GitHub/browser/connector
- CI jobs never self-modify workflow definitions

### F. `ops/*` conflicts during source commit

Observed failure:

- build and observer jobs both changed temporary `ops/*` files, causing rebase conflicts

Prevention:

- permanent pipelines perform validation only and never commit generated status files
- temporary operational files are not part of a production release commit

### G. Stale hardcoded version metadata

Observed failure:

- an old Beta pipeline still targeted beta.3 while source had advanced

Prevention:

- read versions dynamically from source
- verify APK badging against those values
- never duplicate version constants in normal workflow code

### H. Full release + live probes on every small edit

Observed problem:

- even one/two-line changes incurred full Beta+Stable release builds, network probes and release-level setup

Prevention:

- ordinary changes use Tier A fast check
- full live/release validation runs only in Tier B before a release

### I. Android SDK bootstrapped on every run

Observed problem:

- command-line tools and SDK platform/build-tools were repeatedly downloaded/installed

Prevention:

- exact preinstalled-SDK fast path first
- verified pinned bootstrap only as fallback

### J. Wrong external signing/backend assumption

Observed failure:

- a release investigation incorrectly explored an unrelated external service even though the project architecture no longer used it

Prevention:

- read `AGENTS.md`, architecture guardrails and cumulative handover before release troubleshooting
- signing/storage stays within approved project mechanisms
- an inherited or historical service is not authority unless the owner explicitly re-approves it

### K. OAuth scope mismatch for Drive upload

Observed failure:

- the CI Google OAuth token used for Apps Script did not have the required Drive upload scope

Prevention:

- do not assume Apps Script deployment credentials can mutate Drive
- use the approved Drive release path/connector
- only add a browser-authorized Drive scope if the owner later explicitly chooses full automated Drive upload

## 9. Source-change discipline

For a normal implementation change:

1. Make the smallest coherent source change.
2. Run static guards.
3. Run fast Beta+Stable debug build.
4. Fix the first root failure.
5. Do not create a release merely because fast CI passed.

Before OTA:

1. Bump source version identity.
2. Run Release Preflight.
3. Sign with fixed identity.
4. Publish only to requested channel.
5. Run OTA E2E.
6. Clean temporary release material.

## 10. Owner workstation rule

The owner is not asked to run local CLI commands. Git/Gradle/Android signing/verification work must be moved to GitHub Actions or other approved automation. Owner-facing steps use browser/UI only.

## 11. Cleanup rule

Temporary one-shot workflows, trigger markers, observer receipts and decrypted signing material must be removed after their purpose is complete.

Permanent workflows are:

- fast source validation
- release preflight
- approved GAS deployment/validation workflows that remain necessary

Do not accumulate a new one-shot workflow for every ordinary edit.
