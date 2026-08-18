# BUILD / RELEASE PLAYBOOK — PICK PACK 1291

Status: **CHỐT / authoritative operating procedure**  
Updated: 2026-08-18 12:42 +07:00

Purpose: minimize wall-clock time from source change to verified OTA **without weakening correctness, channel isolation, signer identity or business gates**.

## 1. Fixed architecture

Operational:

`Android App ↔ Google Apps Script ↔ Google Sheets`

OTA:

`Android -> GAS update_check -> Google Drive channel folder`

- Beta reads only `BẢN THỬ NGHIỆM`.
- Stable reads only `BẢN ỔN ĐỊNH`.
- GitHub Releases are not steady-state OTA authority.
- Preserve the fixed Android signing identity.
- Do not introduce another backend/signing/storage authority for convenience.

## 2. Permanent workflow set

Only these workflows are intended to remain permanent:

1. `App Fast Check`
2. `Release Preflight - Beta and Stable`
3. `Deploy Current GAS`
4. `Verify Google Apps Script Credentials`
5. `Verify Beta OTA`

Do **not** create observer/status/finalizer/OTA workflows per release. Do not write workflow status receipts to `main`.

Permanent trigger files may be updated by automation when browser `workflow_dispatch` is not available. A trigger update is not a release artifact and must not contain secrets.

## 3. Tier A — App Fast Check

### Scope detection

`App Fast Check` first detects what actually changed.

- App/Gradle change -> static guards + Beta Debug + Stable Debug.
- GAS-only change -> static guards + GAS syntax only; **skip Android SDK/Gradle build**.
- Documentation/handover-only changes do not trigger Android Fast Check.
- Workflow self-change may validate both paths.

This prevents a docs/GAS-only edit from paying the Android build cost.

### Required app gates

- architecture/static invariants
- exact owner launcher hash
- five-tab shell/order
- Admin namespace owner lock
- no artificial tab transition code
- no banned developer-facing UI copy
- no unauthorized backend endpoints
- Beta Debug assemble
- Stable Debug assemble

### Required GAS gates

- route/static invariants
- JavaScript syntax check
- no automatic live deploy

Fast Check must not:

- call live GAS/Drive for every edit
- deploy GAS
- sign APK
- publish OTA
- commit source/status/receipt files

Concurrency cancels an older Fast Check when a newer source commit arrives.

## 4. GAS deployment — explicit only

If a release contains a GAS change:

`Fast Check PASS -> Deploy Current GAS -> live post-deploy gates PASS -> Release Preflight`

If the release is Android-only, **skip GAS deployment entirely**.

Deploy Current GAS must preserve the approved Apps Script project/deployment and verify:

- live health / Sheet read
- `SINGLE_ACTIVE_DEVICE_V1`
- account-email reset route
- Beta/Stable Drive OTA isolation

Source edits under `google-apps-script/**` never deploy live automatically.

## 5. Tier B — Release Preflight

Run only when an OTA/release is actually intended.

### Parallel execution

Release Preflight has two independent jobs running **in parallel**:

**Live gates**
- live GAS health
- Beta/Stable OTA channel isolation

**Android release job**
- release invariants
- source-derived version metadata
- exact SDK fast path
- Beta Release + Stable Release assemble
- package/version validation
- upload authoritative unsigned Beta artifact
- optional fixed-signer validation when all signing secrets are ready

A final pass job succeeds only when both parallel branches pass.

### Build exactly once

The unsigned Beta APK produced by successful Release Preflight is the **authoritative release candidate for that commit**.

After Preflight:

- do not rebuild the APK before signing
- do not run another release assemble merely to publish
- download/reuse the exact artifact from the successful Preflight run
- artifact includes release metadata tying it to commit/version

This removes duplicate release builds from the OTA path.

## 6. Android SDK / Gradle fast path

Both Android pipelines:

1. Check whether the hosted runner already has exact Android platform/build-tools 36.0.0.
2. Use the preinstalled SDK immediately when exact requirements are present.
3. Only otherwise download the pinned command-line tools archive, verify its SHA-256 and install exact tools.

Gradle policy:

- `org.gradle.parallel=true`
- `org.gradle.caching=true`
- GitHub `gradle/actions/setup-gradle` cache reuse
- use `gradle ...`, not `./gradlew`; this repo does not rely on a checked-in wrapper
- release/debug commands explicitly use `--build-cache --parallel`

Do not enable configuration-cache or other aggressive flags until a controlled Beta+Stable compatibility test proves them safe.

## 7. Signing — current bottleneck and target state

Fixed signer SHA-256:

`d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`

Never generate a replacement signer.

### Target one-click state

The long-term fastest path requires these four GitHub Secrets to be confirmed/configured:

- `ANDROID_SIGNING_KEY_B64`
- `ANDROID_SIGNING_STORE_PASSWORD`
- `ANDROID_SIGNING_KEY_PASSWORD`
- `ANDROID_SIGNING_ALIAS`

When all four are ready, Release Preflight can sign the **same validated artifact** and verify the fixed signer in-run.

### Current state until secrets are configured

The four signing secrets are not yet confirmed complete. Therefore:

1. Download the exact unsigned artifact from the successful Preflight run.
2. Use only the official encrypted signing recovery material already stored in the approved project Drive tree.
3. Decrypt/sign in temporary assistant-controlled runtime; never print or commit material.
4. Verify fixed signer SHA before upload.
5. Delete decrypted material immediately.

Do not build a temporary Apps Script signing bridge and do not create a temporary signing workflow for each release.

Signing recovery is the only remaining material source until owner-approved one-time secret configuration is completed.

## 8. OTA publish — Beta fast path

After Preflight PASS and signing:

1. Compute signed APK SHA-256.
2. Upload checksum and APK directly to `BẢN THỬ NGHIỆM` through the approved Google Drive connector/path.
3. Do not rebuild.
4. Update permanent `ops/beta-ota-verify-trigger.txt` with:
   - previous Beta version
   - target Beta version
   - expected signed APK SHA-256
5. Permanent `Verify Beta OTA` performs the E2E gates.

`Verify Beta OTA` must check:

- previous Beta discovers target Beta
- GAS reports `source=GOOGLE_DRIVE`, `channel=BETA`
- live downloaded bytes match expected SHA-256
- package is `vn.pickpack1291.app.beta.publicbeta`
- target version matches
- signer matches fixed certificate
- target Beta does not update to itself
- Stable channel does not expose the Beta target

Do not call the release complete before this workflow passes.

No one-shot OTA verifier or status observer is needed.

## 9. Stable release

Stable uses the same safety principles but is never promoted merely because builds pass.

Required before Stable publish:

- owner-approved Beta soak/business acceptance
- explicit owner instruction to promote Stable
- Stable-specific Drive folder only
- fixed signer and SHA verification
- Stable OTA E2E
- Beta channel remains isolated

## 10. Critical-path rule

For an Android-only Beta release:

`source -> Fast Check -> Release Preflight -> reuse artifact -> sign -> Drive upload -> Verify Beta OTA -> RELEASED`

For Android + GAS:

`source -> Fast Check -> Deploy Current GAS -> Release Preflight -> reuse artifact -> sign -> Drive upload -> Verify Beta OTA -> RELEASED`

The following are **after-release housekeeping**, never blockers before the owner can receive the OTA:

- handover update
- documentation update
- cleanup notes
- historical receipts
- release summary prose

Temporary signing plaintext must still be deleted immediately after signing; that security cleanup is not deferred.

## 11. Version policy

- Read `versionCode`/`versionName` from `app/build.gradle.kts`.
- CI must not hardcode an old Beta version.
- Published behavior is immutable under the same version identity.
- New releasable behavior requires a new versionCode/versionName.
- APK metadata must match source metadata before publish.

## 12. Recurring failure catalogue — mandatory prevention

### Fragile Kotlin patch anchors

Observed: one-line/compressed replacements broke on whitespace/braces and produced cascaded compiler errors.

Prevent:
- replace coherent multiline functions/components
- assert unique marker count before mutation
- fix the first/root compiler error, not cascades

### Multiline source embedded in workflow YAML

Observed: indentation/parser failures.

Prevent:
- complex transformations live in standalone scripts or direct source edits
- workflow YAML orchestrates; it does not carry giant patch bodies

### New workflow dispatched immediately

Observed: GitHub 422 before workflow registration.

Prevent:
- use permanent workflows
- do not create per-release workflow dispatch machinery

### Observer/status commits racing build commits

Observed: `main` advanced and caused rebase/push conflicts.

Prevent:
- no observer/status workflows writing `main`
- read Actions state directly

### CI self-editing workflow files

Observed: workflow permission failure.

Prevent:
- workflow definitions are edited explicitly through GitHub/connector, never by CI itself

### Temporary `ops/*` conflicts

Observed: competing jobs changed receipts/markers.

Prevent:
- only small permanent trigger files are allowed
- no generated status JSON is required for normal release flow

### Stale hardcoded versions

Observed: old Beta workflow targeted beta.3 after source advanced.

Prevent:
- dynamic source metadata everywhere

### Full release/live probes on small edits

Observed: one/two-line changes paid full release cost.

Prevent:
- Fast Check for normal edits
- Preflight only when release intended

### SDK bootstrap every run

Observed: unnecessary tool download/install.

Prevent:
- exact preinstalled SDK first; pinned fallback only

### Wrong external signing/backend assumption

Observed: troubleshooting wandered toward an unrelated service no longer in project architecture.

Prevent:
- read AGENTS/guardrails/handover first
- stay inside approved architecture/recovery

### OAuth scope mismatch for Drive

Observed: Apps Script OAuth credentials did not have Drive upload scope.

Prevent:
- do not assume GAS deployment OAuth can upload APKs
- current publish uses approved Drive connector

### Missing `gradlew`

Observed in S09: a temporary job assumed `./gradlew` and failed before compiling.

Prevent:
- permanent workflows use `gradle/actions/setup-gradle` + `gradle`
- never create a job that assumes a wrapper exists

### Release housekeeping on critical path

Observed in S09: probes/status/finalizer/docs work extended elapsed time after the useful release gates.

Prevent:
- release first through the permanent gate
- handover/docs after OTA PASS
- no status receipts required

## 13. Owner workstation rule

The owner is never asked to run local CLI. Git/Gradle/signing/verification CLI work is performed by CI or assistant-controlled tooling. Owner-facing setup remains browser/UI based.

## 14. Cleanup rule

- No per-release one-shot workflows.
- No status/observer receipts committed to `main`.
- Keep only permanent workflows listed in section 2.
- Decrypted signing material is ephemeral and deleted immediately.
- Release artifacts may remain for their configured short retention to support exact artifact reuse/debugging.
