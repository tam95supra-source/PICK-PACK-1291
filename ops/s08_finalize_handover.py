from pathlib import Path

p=Path('docs/HANDOVER_CURRENT.md')
s=p.read_text(encoding='utf-8')

old="""Last updated: **2026-08-18 09:58 +07:00 (Asia/Bangkok)**  
Latest implementation checkpoint: **S07 — persistent tab shell, global copy rules, CI/release optimization**"""
new="""Last updated: **2026-08-18 11:08 +07:00 (Asia/Bangkok)**  
Latest implementation checkpoint: **S08 — approved visual system implemented and Beta 0.4.2-beta.8 released by Drive OTA**"""
if old not in s: raise SystemExit('header marker missing')
s=s.replace(old,new,1)

old="""### Current visual implementation caveat

The owner-approved multi-screen mockup family is the **visual target/spec**. S07 implemented the global shell/navigation/copy behavior and equal work-card structure, but future visual work must continue to align every inner screen pixel/layout component with `docs/UI_UX_SYSTEM.md`; do not falsely assume every mockup detail is already implemented just because the behavioral shell is complete.
"""
new="""### S08 visual implementation — RELEASED IN BETA8

S08 applied the owner-approved visual system to the working Android UI and released it in Beta `0.4.2-beta.8`:

- authenticated identity/status header follows the approved structure
- equal 2x2 Nghiệp vụ cards use semantic Android vector icons
- bottom navigation uses stable vector icons and persistent in-place switching
- shared cards/inputs/buttons/sections use the approved rounded enterprise component language
- Settings keeps 7 equal theme swatches on one horizontal row
- Login was aligned to the same visual family
- inner workflows inherit the same shared surface/control system

This is the implemented Beta baseline. Real-PDA acceptance may still identify spacing/fit defects that require targeted fixes, but future work must refine this approved system rather than redesigning it without owner instruction.
"""
if old not in s: raise SystemExit('visual caveat marker missing')
s=s.replace(old,new,1)

start=s.index('## 14. Current release state')
end=s.index('## 15. Build / CI / release optimization')
release="""## 14. Current release state

### Published Beta — `0.4.2-beta.8`

- Package: `vn.pickpack1291.app.beta.publicbeta`
- VersionCode: `14`
- APK: `pick-pack-1291-public-beta-v0.4.2-beta.8.apk`
- SHA-256: `dbb86e8d3edcadc4ce4138410427f97d93279cb047cce45fb7e41d68578a7d5e`
- Fixed signer SHA-256 remains:
  `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`
- OTA authority/source: `GOOGLE_DRIVE`, Beta channel only.

Beta8 release gates passed:

- S08 visual source applied and Beta Debug + Stable Debug compile PASS
- Release Preflight PASS: architecture/UX guards, live GAS health, BETA/STABLE Drive isolation, Beta Release + Stable Release, package/version metadata
- APK signed with the existing official signing identity; no replacement key was created
- Beta6 -> Beta8 live `update_check` returns the new Beta
- actual OTA APK download SHA-256 matches the published SHA
- downloaded APK signer matches the fixed signer
- downloaded package/version metadata matches package + VersionCode 14 + `0.4.2-beta.8`
- Beta8 does not offer an update to itself
- Stable does not see the Beta8 build

The first recovery bridge upload attempt was abandoned because large APK transfer through the temporary Apps Script bridge stalled. The obsolete run was cancelled and cleanup passed. Final APK upload used the approved Google Drive connector directly, then independent read-only OTA gates verified the live bytes. This does not change steady-state OTA authority: Android still discovers updates only through GAS `update_check` -> the official Drive channel folder.

### Superseded unpublished candidate — `0.4.2-beta.7`

- VersionCode: `13`
- Contained the S07 persistent-shell/copy-rule refactor.
- It was **never published to Google Drive OTA**.
- Beta8 supersedes it and includes the S07 behavior plus the approved S08 visual implementation.

### Previous published Beta — `0.4.2-beta.6`

- VersionCode: `12`
- Remains the verified source version for the live Beta6 -> Beta8 upgrade acceptance path.

### Stable

Not promoted. Stable release still requires Beta soak/business acceptance and an explicit owner decision.

"""
s=s[:start]+release+s[end:]

old='On real PDA after next OTA candidate:'
new='On real PDA with published Beta `0.4.2-beta.8`:'
if old not in s: raise SystemExit('PDA marker missing')
s=s.replace(old,new,1)

old="""Until confirmed, use only the official existing signing recovery path and verify the fixed signer. Never create a replacement signing identity.
"""
new="""Until confirmed, use only the official existing signing recovery path and verify the fixed signer. Never create a replacement signing identity.

Beta8 confirmed that the official recovery material still produces the fixed signer. The standard four-secret path remains preferred because it removes temporary recovery handling from future releases.
"""
if old not in s: raise SystemExit('signing marker missing')
s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')
print('HANDOVER_CURRENT finalized for Beta8 release')
