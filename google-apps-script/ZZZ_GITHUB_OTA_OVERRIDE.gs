// PP_GITHUB_RELEASE_OTA_STATIC_CANONICAL_V2
// Intentionally does NOT redefine ppUpdateCheck_.
// gas-deploy.yml materializes the canonical OTA manifest from
// ops/beta-ota-current.json directly into PICK_PACK_API.gs via
// tools/apply_github_ota_canonical.py before each production deployment.
//
// This avoids runtime calls from Apps Script to the GitHub Releases API,
// which can be rate-limited/blocked with HTTP 403 on shared GAS egress IPs.
// APK bytes remain served from the signed GitHub Release URL embedded in the
// canonical manifest. Manual update checking in the Android app is unchanged.
