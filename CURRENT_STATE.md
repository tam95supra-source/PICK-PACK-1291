# PICK PACK 1291 — CURRENT STATE

Fresh checkpoint: 2026-08-22 Asia/Ho_Chi_Minh.

- LIVE/GOLDEN rollback: `0.4.2-beta.48` / versionCode `54`.
- Golden source SHA: `7355d10730b60ca7d9d230d7990e007de68edc4e`.
- ABANDONED/DENYLIST: `0.4.2-beta.49` / versionCode `55`; never reuse or publish.
- TARGET candidate: `0.4.2-beta.50` / versionCode `56`.
- Stabilization branch: `stabilization/beta48-golden-reset-beta50-20260822`, created directly from the golden source SHA.
- Stable: `0.1.0-stable` / versionCode `1`, untouched.
- `main`: `438da20c54194daa517e2e116514e3f94d4d3675`, unprotected at fresh-read.
- PR #38: draft/open, head `34b58d945474a5a4ddc819dd521ea757e221af7f`; must not be merged as-is.
- Stabilization PR #52: draft/open; not approved for merge.
- Beta48 candidate workflow run `32553440328`: materialize/build/package/sign/upload artifact PASS; only post-artifact receipt persistence failed.
- Beta48 signed artifact ID: `9470768572`; APK SHA-256 lock remains `cfca4a83b3a69c554afabecae83ff150e9f0b66639360ea013e24bf4b08d996f`.

Current execution order: canonicalize materialized Beta48 Android source once, remove build-time patch reachability, implement latest OWNER 5 requests directly, regression-test, build/sign/verify Beta50 only, then update Beta OTA when release gates pass. Production data/Stable remain untouched.
