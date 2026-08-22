#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ops=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
patch=ROOT/'tools/apply_s54_beta48_owner_10_fixes.py'
if 'S54_BETA48_OWNER_10_FIXES' in ops.read_text(encoding='utf-8'):
    print('S54A: S54 already materialized')
    raise SystemExit(0)

q=patch.read_text(encoding='utf-8')
old='''    s = replace_once(
        s,
        'var selectedDate=operationalStore.latestBusinessDate().ifBlank{operationalStore.businessDate()};var filter="ALL";var pageSize=60;var query=""',
        'var selectedDate=operationalStore.businessDate();var filter="ALL";var pageSize=60;var query=""',
        "history-current-day",
    )
'''
new='''    # History declaration shape has evolved across S36..S53. Scope replacement to historyScreen
    # and change only selectedDate, preserving surrounding filters/paging/search declarations.
    hs=s.find('    private fun historyScreen(){')
    he=s.find('\\n    private fun ',hs+20)
    if hs<0 or he<0:
        raise SystemExit("S54 historyScreen structural anchor missing")
    hb=s[hs:he]
    import re as _re
    hb,n=_re.subn(r'(?:var|val)\\s+selectedDate\\s*=\\s*[^;\\n]+', 'var selectedDate=operationalStore.businessDate()', hb, count=1)
    if n!=1:
        raise SystemExit(f"S54 history selectedDate structural anchor mismatch: {n}")
    s=s[:hs]+hb+s[he:]
'''
if old not in q:
    raise SystemExit('S54A source patch block not found')
patch.write_text(q.replace(old,new,1),encoding='utf-8')
print('S54A converted S54 History patch to structural matching')
