#!/usr/bin/env python3
from pathlib import Path
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