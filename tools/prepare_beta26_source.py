#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
M2=ROOT/'tools/apply_m2_android_transport_patch.py'
GRADLE=ROOT/'app/build.gradle.kts'

s=M2.read_text(encoding='utf-8')
if 'apply_s30_admin_audit_android.py' not in s:
    s=s.replace('runpy.run_path(str(ROOT / "tools/apply_s29_owner_localfirst_history.py"), run_name="__main__")','runpy.run_path(str(ROOT / "tools/apply_s29_owner_localfirst_history.py"), run_name="__main__")\n    runpy.run_path(str(ROOT / "tools/apply_s30_admin_audit_android.py"), run_name="__main__")',1)
    # second occurrence has no indentation in source tail
    tail='runpy.run_path(str(ROOT / "tools/apply_s29_owner_localfirst_history.py"), run_name="__main__")\nprint(f"Applied M2 dynamic Service transport'
    if tail in s:
        s=s.replace(tail,'runpy.run_path(str(ROOT / "tools/apply_s29_owner_localfirst_history.py"), run_name="__main__")\nrunpy.run_path(str(ROOT / "tools/apply_s30_admin_audit_android.py"), run_name="__main__")\nprint(f"Applied M2 dynamic Service transport',1)
    s=s.replace('S19/S20/S21/S22/S23/S24/S25/S27/S29 runtime fixes','S19/S20/S21/S22/S23/S24/S25/S27/S29/S30 runtime fixes')
    s=s.replace('S19/S20/S21/S22/S23/S24/S25/S27/S29 runtime patches','S19/S20/S21/S22/S23/S24/S25/S27/S29/S30 runtime patches')
    M2.write_text(s,encoding='utf-8')

g=GRADLE.read_text(encoding='utf-8')
if 'tools/apply_s29_owner_localfirst_history.py' not in g:
    anchor='    inputs.file(rootProject.file("tools/apply_s27_projection_ack_gap_fix.py"))\n'
    if anchor not in g: raise SystemExit('Beta26 Gradle S27 input anchor missing')
    g=g.replace(anchor,anchor+'    inputs.file(rootProject.file("tools/apply_s29_owner_localfirst_history.py"))\n    inputs.file(rootProject.file("tools/apply_s30_admin_audit_android.py"))\n',1)
g=g.replace('versionCode = 31\n            versionName = "0.4.2-beta.25"','versionCode = 32\n            versionName = "0.4.2-beta.26"',1)
g=g.replace('S10..S25 + S27','S10..S25 + S27 + S29 + S30')
GRADLE.write_text(g,encoding='utf-8')
print('Prepared Beta26 compose chain and version 0.4.2-beta.26 (32)')
