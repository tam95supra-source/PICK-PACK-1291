# Beta 0.1.0 Preview

Status: UI/UX installable preview.

## Included

- Approved UI baseline: Sample 3 (light / soft teal / easy to read).
- Android 10+ (`minSdk 29`), portrait-first, PDA-oriented touch targets.
- Login preview screen, dashboard, Enter Shift form, Resources, Lists, Settings.
- Exact copyright footer approved by project owner.
- User-provided master artwork used as app icon without redesign.
- Local crash package creation, daily log creation, and manual diagnostic report generation.
- Preview sync state machine: `ACTIVE -> DRAINING -> SUSPENDED` to demonstrate lifecycle behavior.
- Beta package is separated from future stable package.

## Intentionally not enabled in this preview

- Google Apps Script authoritative API.
- Real authentication against account database.
- Google Sheets writes / real sync / resource locking.
- OTA self-update.
- Automatic upload of diagnostic logs to Drive.
- Permanent Beta signing certificate.

These features remain blocked on the backend deployment/signing bootstrap and must not be simulated with direct Google Sheets credentials inside the public APK/source.

## Signing note

This preview is built with Android debug signing on the GitHub runner and is intended only for install/UI review. A persistent Beta keystore stored via GitHub Actions Secrets is required before the first functional OTA-compatible Beta release.
