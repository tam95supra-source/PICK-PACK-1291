# PICK PACK 1291 — Beta50 Release Manifest

Status: **RELEASED / OTA E2E PASS**  
Recorded: 2026-08-22 (Asia/Ho_Chi_Minh)

## Authority and lineage

- Golden / rollback: `0.4.2-beta.48` / versionCode `54`
- Abandoned / denylisted: `0.4.2-beta.49` / versionCode `55`
- Released Beta: `0.4.2-beta.50` / versionCode `56`
- Canonical Android source SHA: `39efa0a6bf1f7d1b3d93d104e3a2395a3ddb2440`
- Package: `vn.pickpack1291.app.beta.publicbeta`
- Signer SHA-256: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- Stable: `0.1.0-stable` / VC1 — **UNTOUCHED**

## OWNER five-request delivery

1. Added **Quản lý biên bản** in Nghiệp vụ with document icon; currently reports that construction is pending.
2. Removed **Người dùng đang kết nối** from the Sync UI/transport flow.
3. Removed the headline wording **Còn xx mục / còn xx mục chờ gửi**; pending work is presented as sync state instead.
4. Split Sync into user-facing detail sections:
   - THÔNG TIN TRÊN PDA
   - THÔNG TIN TRÊN SERVICE
   - THÔNG TIN TRÊN GOOGLE SHEET
   - THÔNG TIN ĐỒNG BỘ KHÁC
5. Moved **THÔNG TIN ỨNG DỤNG** into Cài đặt.

## Canonicalization and verification

- Beta48 S10–S54 materialized exactly once, then committed as normal source.
- Android build no longer reaches `generateS10Operations` / Sxx transform chain through `preBuild`.
- Final canonical verification run: `32566368576` — PASS.
- Verification includes the five OWNER contracts, Kotlin compile, Beta-only assemble, and clean-diff/non-mutating build.
- Unsigned verification artifact: `9474202908`.

## Signed candidate

- Signed run: `32567143831` — PASS.
- Signed artifact: `9474405685`.
- APK: `pick-pack-1291-public-beta-0.4.2-beta.50.apk`
- APK SHA-256: `712350b17d2ed1a54069cf3bf30cb1be492d6df131b2ad1ce5393278501bc93c`
- APK size: `12995123` bytes.
- Locked production signer verified before upload.
- Firebase client BuildConfig required fields were asserted non-empty without logging secret/config values.

## GitHub release

- Tag: `v0.4.2-beta.50-publicbeta`
- Release ID: `374897111`
- Published at: `2026-08-22T10:18:31Z`
- URL: `https://github.com/tam95supra-source/pick-pack-1291/releases/tag/v0.4.2-beta.50-publicbeta`
- Release APK was downloaded again and SHA/size matched the signed candidate exactly.

## Google Drive backup / DR

Beta folder: `1WMXI-8-Z1mbY2v11noYFHe_eoMNiNZXg`

- APK file ID: `1nbu_OUa9R47EwbOe4xC-KB81DGEIxxWx`
- Checksum file ID: `110VICbcJfYXgstQweteMimJRWhDXL_I8`
- Metadata file ID: `1FZ2sePlxmzn-s-0xDYNiWgzO2B0DKD9P`
- APK was downloaded back through the connected Drive and re-hashed: SHA-256 and size match the signed candidate exactly.
- The legacy workflow OAuth path returned HTTP 403; backup was completed through the authorized Google Drive connector rather than waiving the backup gate.

## GAS / OTA

- Live GAS version: `126`.
- Production GAS deploy run: `32567397044` — deploy PASS, live verification PASS.
- OTA metadata mode: `STATIC_CANONICAL`.
- Runtime GitHub Releases API in GAS: `DISABLED`.
- Manual OTA check: enabled as designed; automatic app check remains disabled.
- Dedicated required path E2E run: `32567417232` — PASS.
- Exact tested path: `0.4.2-beta.48 / VC54` → `0.4.2-beta.50 / VC56`.
- E2E verifies live discovery, exact GitHub APK download, SHA/size, package, version, locked signer, target self-update false, and Stable isolation.
- Beta49 remains ABANDONED and is not part of the OTA path.

## Release isolation / Git safety

- `main` was not changed by this stabilization/release work.
- PR #38 remains open/draft/unmerged and is not a merge source.
- PR #52 remains draft/unmerged.
- Stable was not assembled/published/promoted by the Beta50 release flow.

## Rollback

Rollback baseline remains published Beta48:

- version: `0.4.2-beta.48` / VC54
- package: `vn.pickpack1291.app.beta.publicbeta`
- signer: same locked signer
- APK SHA-256: `cfca4a83b3a69c554afabecae83ff150e9f0b66639360ea013e24bf4b08d996f`
- size: `12995067` bytes
- tag: `v0.4.2-beta.48-publicbeta`

Do not delete or rewrite Beta48 release/backup evidence. A rollback metadata change must preserve the same package/signer and must not resurrect Beta49/VC55.

## Field gate boundary

Automated release and OTA acceptance are PASS. Physical PDA installation/business-flow acceptance requires an actual authorized device session; it is not simulated or marked PASS by CI.
