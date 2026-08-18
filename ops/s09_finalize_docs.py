from pathlib import Path
import re

# UI UX consistency
p=Path('docs/UI_UX_SYSTEM.md')
s=p.read_text()
s=s.replace('- `Tài khoản: <login>`','- Tên user / login ID, hiển thị trực tiếp, không tiền tố `Tài khoản:`')
p.write_text(s)

# Build/release playbook: capture the concrete S09 failure mode.
p=Path('docs/BUILD_RELEASE_PLAYBOOK.md')
s=p.read_text()
anchor='''## Failure patterns to avoid\n'''
extra='''- This repository does not rely on a checked-in `gradlew` wrapper. CI must use `gradle/actions/setup-gradle` and invoke `gradle ...`; do not add one-shot jobs that assume `./gradlew` exists.\n'''
if extra not in s:
    if anchor in s:
        s=s.replace(anchor,anchor+'\n'+extra,1)
    else:
        s=s.rstrip()+'''\n\n## S09 build rule\n\n'''+extra
p.write_text(s)

# Cumulative handover
p=Path('docs/HANDOVER_CURRENT.md')
s=p.read_text()
s=re.sub(r'Last updated: \*\*.*?\*\*  ', 'Last updated: **2026-08-18 11:48 +07:00 (Asia/Bangkok)**  ', s, count=1)
s=re.sub(r'Latest implementation checkpoint: \*\*.*?\*\*', 'Latest implementation checkpoint: **S09 — actual-device UI corrections, strict catalog namespaces, Admin role lock, Beta 0.4.2-beta.9 released by Drive OTA**', s, count=1)
s=s.replace('3. `Tài khoản: <login>`','3. Tên user/login ID, hiển thị trực tiếp; không tiền tố `Tài khoản:`')
admin_anchor='''`Danh sách Admin` now has a **Mail** field. Existing accounts were initialized to the owner-approved reset address. Each account may change its own reset-mail address through the app; forgot-password delivery uses the configured email for that account.\n'''
admin_rule='''\n`Danh sách Admin` is a specialized account namespace. Its `Vị trí` is owner-locked to exactly `superadmin`, `admin`, `user`; no cross-sheet/catalog fallback is allowed. Android/GAS derive Admin position from account role. Existing rows were normalized to this mapping in S09. See `docs/ADMIN_ACCOUNT_RULES.md`.\n'''
if admin_rule.strip() not in s and admin_anchor in s:
    s=s.replace(admin_anchor,admin_anchor+admin_rule,1)

s09_ui='''\n### S09 actual-device corrections — RELEASED IN BETA9\n\nOwner review of real-device Beta8 screenshots identified implementation drift from the approved mockup. S09 corrected the implementation rather than changing the approved design family:\n\n- root tabs no longer show duplicate page titles such as `Nghiệp vụ`, `Nhân sự`, `Lịch sử`, `Đồng bộ`, `Cài đặt` inside the gradient header\n- authenticated header has no avatar placeholder; identity is left aligned as exactly three constrained lines: display name, position, login ID\n- no `Tài khoản:` prefix in the header\n- connection status is persistent Activity state; tab switches do not reset the header to a transient `Mạng: Đang nối/Đang kết nối` state\n- Nhân sự renders incrementally instead of constructing thousands of cards on the UI thread; search still uses the complete local master cache\n- `Danh mục` is exposed in master snapshot as `catalog_fields`; each `SHEET_FIELD` is a strict namespace for the matching editable field\n- cross-sheet fallback is forbidden; similarly named fields do not authorize value reuse\n- system-owned status catalogs are not offered in operational assignment flows; e.g. `DANH SÁCH PDA_Tình trạng` is not selectable when assigning a PDA to PICK\n- `Danh sách Admin_Vị trí` is not catalog-driven and is fixed to `superadmin/admin/user` per owner lock\n- Nghiệp vụ cards, staff list actions, header status areas and shared controls were refined toward the approved semantic-icon/rounded enterprise layout\n\n'''
marker='''## 8. Notifications / interaction — CHỐT\n'''
if '### S09 actual-device corrections — RELEASED IN BETA9' not in s and marker in s:
    s=s.replace(marker,s09_ui+marker,1)

release_pattern=r'''### Published Beta — `0\.4\.2-beta\.8`.*?(?=### Superseded unpublished candidate — `0\.4\.2-beta\.7`)'''
release_block='''### Published Beta — `0.4.2-beta.9`\n\n- Package: `vn.pickpack1291.app.beta.publicbeta`\n- VersionCode: `15`\n- APK: `pick-pack-1291-public-beta-v0.4.2-beta.9.apk`\n- Drive file ID: `112PGd6cWOnKER_NFxhz7huq8apXG5x2f`\n- SHA-256: `6c96a9415299bd11f73ed21e314fb354c530c093f30ae1e23bfa7332d0ff3b6b`\n- Fixed signer SHA-256 remains: `d180450ae47ac6e8daf26840308e62bd602d5f8d6ac12ee0da58e5eb1a44731e`\n- OTA authority/source: `GOOGLE_DRIVE`, Beta channel only.\n\nBeta9 release gates passed:\n\n- S09 source patch + strict Admin rule applied; Beta Debug + Stable Debug PASS\n- GAS syntax PASS and explicit live `Deploy Current GAS` PASS\n- Fast Check PASS with semantic-icon/Admin guards\n- Release Preflight PASS: architecture/UX gates, live GAS health, BETA/STABLE Drive isolation, Beta Release + Stable Release, package/version metadata\n- unsigned release artifact signed from the official encrypted recovery bundle using the existing fixed Android signing identity; no replacement key was created\n- signed APK was verified against the fixed signer before upload\n- Beta8 -> Beta9 live `update_check` returns the new Beta\n- actual OTA download SHA-256 matches the published APK\n- Beta9 does not offer an update to itself\n- Stable does not see Beta9\n- APK has Drive `anyone/reader` download permission established through the live OTA path\n\nS09 also normalized `Danh sách Admin_Vị trí` values to the owner-locked mapping: `superadmin`, `admin`, `user`.\n\n### Previous published Beta — `0.4.2-beta.8`\n\n- VersionCode: `14`\n- SHA-256: `dbb86e8d3edcadc4ce4138410427f97d93279cb047cce45fb7e41d68578a7d5e`\n- Superseded by Beta9 after real-device UI review.\n\n'''
s,n=re.subn(release_pattern,release_block,s,flags=re.S)
if n!=1:
    raise SystemExit(f'published beta section replace count={n}')
p.write_text(s)
print('S09 docs finalized')
