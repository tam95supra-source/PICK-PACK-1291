# BETA51 RELEASE MANIFEST

Status: **Beta51 RELEASED / OTA E2E PASS**

Date: 2026-08-22

## Release identity

- versionName: `0.4.2-beta.51`
- versionCode: `57`
- package: `vn.pickpack1291.app.beta.publicbeta`
- canonical Android source: `ad533975be4f38009b02e1adb7ea552b6850a244`
- canonical Service source: `ff09c30511704ec68dbd123b00288e5d62292470`
- signer SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- APK SHA-256: `9714b96055a7025be4d2975021d751aeeb00dde36eb50be80ced3f930d209e06`
- APK size: `12995123` bytes

## Delivered Beta51 behavior

- `Phát lại user pick` and `Phát lại user pack` are separate compact controls aligned with their corresponding input rows.
- Removed the PDA suggestion hint that instructed users to select a suggestion to reveal full information.
- `Không dùng user hy1.outbound` is now `Không dùng`.
- `User Pick` is now `User Pick hy1.outbound`.
- User IDs use natural numeric ordering: 1, 2, 3, ... 10, 12, 13, ...
- User Pack selection is no longer filtered by the selected attendance shift; all valid table/user mappings can be considered across both shifts.
- Active User Pick/User Pack leases held by another session remain hidden and cannot be bypassed by replay.
- A User Pick/User Pack already used on the business date but currently free remains hidden in normal mode and becomes selectable only through its corresponding replay control.
- A PDA released earlier in the day is normally reusable without a replay action; a PDA actively leased elsewhere remains hidden.
- Current session resources remain preserved in the editor.
- Full selected PDA serial and status are emphasized after selection.
- Service validates replay server-side and keeps daily first-use history intact while allowing an explicitly requested replay of a currently free user.

## Service production

Service resource semantics were materialized and typechecked on source `ff09c30511704ec68dbd123b00288e5d62292470`.

Production deployment completed with:

- Service generation: `m2-prod-20260819-001`
- no D1 migration for this change
- no authority failback
- no Stable change
- ACTIVE lease exclusivity preserved
- daily replay requires explicit `duplicate_user`
- replay daily consumption uses `INSERT OR IGNORE`
- pack-pair validity no longer depends on attendance shift

## Signed candidate

- signed run: `32571479505` — PASS
- signed artifact ID: `9475448387`
- artifact name: `pick-pack-1291-public-beta-0.4.2-beta.51-signed-candidate`
- APK name: `pick-pack-1291-public-beta-0.4.2-beta.51.apk`
- exact APK SHA-256: `9714b96055a7025be4d2975021d751aeeb00dde36eb50be80ced3f930d209e06`
- exact size: `12995123`
- signer matched the locked production Beta signer.

The first Beta51 signing attempt failed only in a CI string-matching gate and did not produce a release candidate. The gate was corrected; the immutable candidate above passed build, Firebase configuration, package/version identity, signing and signer verification.

## GitHub prerelease

- tag: `v0.4.2-beta.51-publicbeta`
- release ID: `374918175`
- published at: `2026-08-22T11:57:06Z`
- release URL: `https://github.com/tam95supra-source/pick-pack-1291/releases/tag/v0.4.2-beta.51-publicbeta`
- release asset was downloaded again after publication and matched the signed candidate by SHA-256 and size.

## Google Drive backup

Exact immutable candidate bytes were backed up to the Beta folder:

- APK ID: `1EP-qszEe_K8aKszPEpc5LS7KMyJOd8jg`
- checksum ID: `1eNc6Dh5Yt7g148_E5Xcn2qln69_BKE5c`
- candidate manifest ID: `1pU2GZaaMPc6LEprGxzqD8ovHRW6ACHnV`

All three Drive objects were fetched back after upload. The APK read-back matched SHA-256 `9714b96055a7025be4d2975021d751aeeb00dde36eb50be80ced3f930d209e06` and size `12995123`; checksum and manifest matched their uploaded bytes.

The first workflow-based Drive OAuth upload path returned HTTP 403 because that token did not have the required Drive write scope. This was not bypassed or accepted as success. Recovery used the connected project Google Drive permission to upload the exact signed artifact, checksum and manifest, followed by raw read-back verification. There is no artifact-integrity gap.

## GAS OTA production

- GAS production version: `127`
- deploy run: `32571947765` — PASS
- canonical Beta OTA source: static `ops/beta-ota-current.json`
- runtime GitHub Releases API lookup: disabled
- from version: `0.4.2-beta.50`
- target: `0.4.2-beta.51` / VC57
- exact target SHA-256 and size verified through live update discovery/download
- target self-update check: false
- Stable isolation: PASS

## OTA end-to-end

Dedicated live OTA E2E run `32572011158` — **PASS**.

Verified from **Beta50 / VC56 → Beta51 / VC57**:

- live GAS discovery returns Beta51
- downloaded OTA bytes match signed candidate SHA-256 and size
- package is `vn.pickpack1291.app.beta.publicbeta`
- versionCode is 57
- versionName is `0.4.2-beta.51`
- APK signer matches locked signer SHA-256
- Beta51 self-update is false
- Stable remains isolated and untouched
- Beta49 request skips directly to Beta51

## Safety / branch state at release closure

- `main`: `438da20c54194daa517e2e116514e3f94d4d3675` — unchanged by Beta51 release work.
- PR #38: intended to remain open/draft/unmerged; Service changes are not merged to `main` without OWNER approval.
- PR #52: intended to remain open/draft/unmerged; stabilization/release changes are not merged to `main` without OWNER approval.
- Stable `0.1.0-stable` / VC1: untouched by Beta51 release flow.
- Beta49 / VC55: ABANDONED / denylisted; never reuse VC55.
- obsolete broad Beta50 canonical verifier was retired after Beta51 release because it hard-coded Beta50/VC56 and produced false red signals on later stabilization commits.

## Rollback order

1. Beta50 / VC56 is the immediate prior public Beta release.
2. Beta48 / VC54 remains the golden rollback baseline.
3. Beta49 / VC55 must never be used as a rollback or release target.

## Physical-device boundary

Automated build/sign/release/backup/GAS/OTA acceptance is complete. A real-PDA physical installation/business-flow observation requires an authorized physical device session; no physical result is fabricated by CI. This is not an unresolved automated release gate.
