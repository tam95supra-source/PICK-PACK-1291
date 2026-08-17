from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADLE = ROOT / "app/build.gradle.kts"
WORKFLOW = ROOT / ".github/workflows/beta-preview.yml"
CERT_SHA256 = "d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}: {old[:100]!r}")
    return text.replace(old, new, 1)


gradle = GRADLE.read_text(encoding="utf-8")
gradle = replace_once(gradle, 'versionCode = 3', 'versionCode = 4', 'beta versionCode')
gradle = replace_once(gradle, 'versionName = "0.3.0-beta.1"', 'versionName = "0.3.0-beta.2"', 'beta versionName')
GRADLE.write_text(gradle, encoding="utf-8")

wf = WORKFLOW.read_text(encoding="utf-8")n
wf = replace_once(
    wf,
    "permissions:\n  contents: write\n",
    "permissions:\n  contents: write\n  id-token: write\n",
    "OIDC permission",
)

sdk_anchor = '''      - name: Normalize Kotlin lexical whitespace
'''
signing_step = '''      - name: Fetch fixed Android signing key via GitHub OIDC
        shell: bash
        env:
          SIGNING_BROKER_URL: https://oedasgcdjppjwidhlqdr.supabase.co/functions/v1/pick-pack-ci-signing
        run: |
          set -euo pipefail
          test -n "${ACTIONS_ID_TOKEN_REQUEST_URL:-}"
          test -n "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}"
          OIDC_JSON="$RUNNER_TEMP/oidc.json"
          BUNDLE="$RUNNER_TEMP/signing-bundle.json"
          curl -fsS --retry 3 --retry-all-errors --retry-delay 1 \
            -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=pick-pack-1291-signing" > "$OIDC_JSON"
          OIDC_TOKEN="$(jq -er '.value' "$OIDC_JSON")"
          curl -fsS --retry 3 --retry-all-errors --retry-delay 1 \
            -X POST "$SIGNING_BROKER_URL" \
            -H "Authorization: Bearer $OIDC_TOKEN" > "$BUNDLE"
          jq -e '.ok == true and .repository == "tam95supra-source/pick-pack-1291" and .alias == "pickpack1291"' "$BUNDLE" >/dev/null
          jq -er '.keystore_b64' "$BUNDLE" | base64 -d > "$RUNNER_TEMP/pick-pack-1291-release.jks"
          jq -er '.store_password' "$BUNDLE" > "$RUNNER_TEMP/store.pass"
          jq -er '.key_password' "$BUNDLE" > "$RUNNER_TEMP/key.pass"
          jq -er '.alias' "$BUNDLE" > "$RUNNER_TEMP/key.alias"
          chmod 600 "$RUNNER_TEMP/pick-pack-1291-release.jks" "$RUNNER_TEMP/store.pass" "$RUNNER_TEMP/key.pass" "$RUNNER_TEMP/key.alias"
          rm -f "$OIDC_JSON" "$BUNDLE"

'''
wf = replace_once(wf, sdk_anchor, signing_step + sdk_anchor, "signing step")

wf = replace_once(
    wf,
    '        run: gradle --no-daemon :app:assembleBetaDebug :app:assembleStableDebug\n',
    '        run: gradle --no-daemon :app:assembleBetaRelease :app:assembleStableRelease\n',
    'release assemble',
)

old_prepare = '''      - name: Prepare named APKs
        shell: bash
        run: |
          set -euo pipefail
          mkdir -p dist/beta dist/stable
          cp app/build/outputs/apk/beta/debug/app-beta-debug.apk dist/beta/pick-pack-1291-public-beta-v0.3.0-beta.1.apk
          cp app/build/outputs/apk/stable/debug/app-stable-debug.apk dist/stable/pick-pack-1291-stable-channel-v0.1.0.apk
          (cd dist/beta && sha256sum pick-pack-1291-public-beta-v0.3.0-beta.1.apk > SHA256SUMS.txt)
          (cd dist/stable && sha256sum pick-pack-1291-stable-channel-v0.1.0.apk > SHA256SUMS.txt)
'''
new_prepare = '''      - name: Sign fixed-identity Beta and Stable APKs
        shell: bash
        run: |
          set -euo pipefail
          mkdir -p dist/beta dist/stable
          KS="$RUNNER_TEMP/pick-pack-1291-release.jks"
          STORE_PASS="$RUNNER_TEMP/store.pass"
          KEY_PASS="$RUNNER_TEMP/key.pass"
          ALIAS="$(cat "$RUNNER_TEMP/key.alias")"
          BETA_UNSIGNED=app/build/outputs/apk/beta/release/app-beta-release-unsigned.apk
          STABLE_UNSIGNED=app/build/outputs/apk/stable/release/app-stable-release-unsigned.apk
          test -s "$BETA_UNSIGNED"
          test -s "$STABLE_UNSIGNED"
          "$ANDROID_SDK_ROOT/build-tools/36.0.0/apksigner" sign \
            --ks "$KS" --ks-key-alias "$ALIAS" \
            --ks-pass "file:$STORE_PASS" --key-pass "file:$KEY_PASS" \
            --out dist/beta/pick-pack-1291-public-beta-v0.3.0-beta.2.apk "$BETA_UNSIGNED"
          "$ANDROID_SDK_ROOT/build-tools/36.0.0/apksigner" sign \
            --ks "$KS" --ks-key-alias "$ALIAS" \
            --ks-pass "file:$STORE_PASS" --key-pass "file:$KEY_PASS" \
            --out dist/stable/pick-pack-1291-stable-channel-v0.1.0.apk "$STABLE_UNSIGNED"
          (cd dist/beta && sha256sum pick-pack-1291-public-beta-v0.3.0-beta.2.apk > SHA256SUMS.txt)
          (cd dist/stable && sha256sum pick-pack-1291-stable-channel-v0.1.0.apk > SHA256SUMS.txt)
'''
wf = replace_once(wf, old_prepare, new_prepare, "fixed signing prepare")

wf = wf.replace('pick-pack-1291-public-beta-v0.3.0-beta.1', 'pick-pack-1291-public-beta-v0.3.0-beta.2')
wf = replace_once(wf, "versionCode='3'", "versionCode='4'", "verify beta versionCode")
wf = wf.replace("versionName='0.3.0-beta.1'", "versionName='0.3.0-beta.2'")
wf = wf.replace('TAG: v0.3.0-beta.1-publicbeta', 'TAG: v0.3.0-beta.2-publicbeta')
wf = wf.replace('Pick Pack 1291 Full Public Beta 0.3.0-beta.1', 'Pick Pack 1291 Full Public Beta 0.3.0-beta.2')

beta_verify_anchor = '''          "$ANDROID_SDK_ROOT/build-tools/36.0.0/apksigner" verify --verbose --print-certs "$APK"
          BADGING=$("$ANDROID_SDK_ROOT/build-tools/36.0.0/aapt" dump badging "$APK")
'''
beta_verify_new = f'''          "$ANDROID_SDK_ROOT/build-tools/36.0.0/apksigner" verify --verbose --print-certs "$APK" | tee /tmp/beta-cert.txt
          grep -qi 'Signer #1 certificate SHA-256 digest: {CERT_SHA256}' /tmp/beta-cert.txt
          BADGING=$("$ANDROID_SDK_ROOT/build-tools/36.0.0/aapt" dump badging "$APK")
'''
wf = replace_once(wf, beta_verify_anchor, beta_verify_new, "pin beta certificate")

stable_verify_anchor = '''          "$ANDROID_SDK_ROOT/build-tools/36.0.0/apksigner" verify --verbose --print-certs "$APK"
          BADGING=$("$ANDROID_SDK_ROOT/build-tools/36.0.0/aapt" dump badging "$APK")
'''
stable_verify_new = f'''          "$ANDROID_SDK_ROOT/build-tools/36.0.0/apksigner" verify --verbose --print-certs "$APK" | tee /tmp/stable-cert.txt
          grep -qi 'Signer #1 certificate SHA-256 digest: {CERT_SHA256}' /tmp/stable-cert.txt
          BADGING=$("$ANDROID_SDK_ROOT/build-tools/36.0.0/aapt" dump badging "$APK")
'''
wf = replace_once(wf, stable_verify_anchor, stable_verify_new, "pin stable certificate")

old_notes = "NOTES='Full-function Public Beta. Enables QUÉT QR NHÂN SỰ/VÀO/RA, CÔNG NHẬT start-finish, atomic TÀI NGUYÊN changes, DANH SÁCH, BÁO CÁO, đổi mật khẩu, diagnostic ACK and ADMIN/SUPERADMIN account management. Beta and Stable now share an automatic foreground OTA checker: when a newer channel release exists the app shows the update prompt automatically, downloads through Android DownloadManager, verifies SHA-256 and opens the Android package installer. [OTA signing note] Long-lived in-place updates still require a fixed signing key stored outside this public repository; the current CI debug identity is pilot-only.'"
new_notes = "NOTES='S02 full-function Public Beta. Adds adaptive foreground realtime sync using authoritative server_seq with ACTIVE/DRAINING/SUSPENDED lifecycle, keeps QUÉT QR NHÂN SỰ/VÀO/RA, CÔNG NHẬT, atomic TÀI NGUYÊN, DANH SÁCH, BÁO CÁO and role controls, and switches CI to a fixed Android release signing identity delivered only to the trusted main-branch release workflow through GitHub OIDC. OTA still verifies APK SHA-256 before opening Android package installer. Google Sheet projection writer is isolated and fail-closed until its dedicated Apps Script deployment is commissioned.'"
wf = replace_once(wf, old_notes, new_notes, "beta2 release notes")

cleanup_anchor = '''      - name: Publish Full Public Beta prerelease
'''
# Cleanup must run after publishing, so append a final always() step after the existing publish block.
cleanup = '''
      - name: Cleanup signing material
        if: always()
        shell: bash
        run: |
          rm -f "$RUNNER_TEMP/pick-pack-1291-release.jks" \
                "$RUNNER_TEMP/store.pass" "$RUNNER_TEMP/key.pass" "$RUNNER_TEMP/key.alias" \
                "$RUNNER_TEMP/oidc.json" "$RUNNER_TEMP/signing-bundle.json"
'''
if '      - name: Cleanup signing material\n' in wf:
    raise SystemExit('cleanup already present')
wf = wf.rstrip() + "\n" + cleanup

WORKFLOW.write_text(wf, encoding="utf-8")
print("fixed signing + beta2 patch staged")
