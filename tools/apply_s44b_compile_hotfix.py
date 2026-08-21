#!/usr/bin/env python3
from pathlib import Path
import runpy
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt'
s=P.read_text(encoding='utf-8')
old='private val FLUSH_LOCK=Any() // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY private const val PREFS'
new='private val FLUSH_LOCK=Any() // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY\n        private const val PREFS'
if old in s:s=s.replace(old,new,1)
P.write_text(s,encoding='utf-8')
o=P.read_text(encoding='utf-8')
assert 'private val FLUSH_LOCK=Any() // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY\n        private const val PREFS' in o
assert 'val OPERATIONAL = setOf(' in o and 'val SYNC_ACTIONS = setOf(' in o and 'object M2DeviceIdentity' in o
print('Applied S44B compile hotfix: companion constants restored after S44 marker')
runpy.run_path(str(ROOT/'tools/apply_s45_beta40_owner_fixes.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s47_beta41_owner_fixes.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s47b_compile_hotfix.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s48_beta42_shift_work_summary.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s49_beta43_session_admin_corrections.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s49b_compile_hotfix.py'),run_name='__main__')
