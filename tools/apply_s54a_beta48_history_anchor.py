#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ops=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
patch=ROOT/'tools/apply_s54_beta48_owner_10_fixes.py'
if 'S54_BETA48_OWNER_10_FIXES' in ops.read_text(encoding='utf-8'):
    print('S54A: S54 already materialized')
    raise SystemExit(0)

q=patch.read_text(encoding='utf-8')
def swap(old:str,new:str,name:str):
    global q
    if old not in q:
        raise SystemExit(f'S54A source block missing: {name}')
    q=q.replace(old,new,1)

swap('''    s = replace_once(
        s,
        'var selectedDate=operationalStore.latestBusinessDate().ifBlank{operationalStore.businessDate()};var filter="ALL";var pageSize=60;var query=""',
        'var selectedDate=operationalStore.businessDate();var filter="ALL";var pageSize=60;var query=""',
        "history-current-day",
    )
''','''    hs=s.find('    private fun historyScreen(){')
    he=s.find('\\n    private fun ',hs+20)
    if hs<0 or he<0: raise SystemExit("S54 historyScreen structural anchor missing")
    hb=s[hs:he]
    import re as _re
    hb,n=_re.subn(r'(?:var|val)\\s+selectedDate\\s*=\\s*[^;\\n]+', 'var selectedDate=operationalStore.businessDate()', hb, count=1)
    if n!=1: raise SystemExit(f"S54 history selectedDate structural anchor mismatch: {n}")
    s=s[:hs]+hb+s[he:]
''','history')

swap('''    s = replace_once(
        s,
        'private fun body()=column(bg).apply{setPadding(dp(16),dp(15),dp(16),dp(92))}',
        'private fun body()=column(bg).apply{setPadding(dp(14),dp(13),dp(14),dp(83))}',
        "body-spacing",
    )
    s = replace_once(
        s,
        'private fun gap(h:Int)=Space(this).apply{layoutParams=size(1,dp(h))}',
        'private fun gap(h:Int)=Space(this).apply{layoutParams=size(1,dp(((h*9)+5)/10))}',
        "gap-spacing",
    )
''','''    s,n=_re.subn(r'private fun body\\(\\)\\s*=\\s*column\\(bg\\)\\.apply\\{setPadding\\(dp\\(\\d+\\),dp\\(\\d+\\),dp\\(\\d+\\),dp\\(\\d+\\)\\)\\}', 'private fun body()=column(bg).apply{setPadding(dp(14),dp(13),dp(14),dp(83))}', s, count=1)
    if n!=1: raise SystemExit(f"S54 body-spacing structural mismatch: {n}")
    s,n=_re.subn(r'private fun gap\\(h:Int\\)\\s*=\\s*Space\\(this\\)\\.apply\\{layoutParams=size\\(1,dp\\(h\\)\\)\\}', 'private fun gap(h:Int)=Space(this).apply{layoutParams=size(1,dp(((h*9)+5)/10))}', s, count=1)
    if n!=1: raise SystemExit(f"S54 gap-spacing structural mismatch: {n}")
''','spacing')

swap('''    s = replace_once(
        s,
        '"Dữ liệu chờ gửi" to pending.toString(),"Luồng trao đổi dữ liệu"',
        '"Dữ liệu chờ gửi" to pending.toString(),"Dung lượng cache" to humanBytes(operationalStore.storageBytes()),"Luồng trao đổi dữ liệu"',
        "sync-cache-size",
    )
''','''    s,n=_re.subn(r'"Dữ liệu chờ gửi"\\s*to\\s*pending\\.toString\\(\\)\\s*,\\s*"Luồng trao đổi dữ liệu"', '"Dữ liệu chờ gửi" to pending.toString(),"Dung lượng cache" to humanBytes(operationalStore.storageBytes()),"Luồng trao đổi dữ liệu"', s, count=1)
    if n!=1: raise SystemExit(f"S54 sync-cache-size structural mismatch: {n}")
''','cache')

swap('''    s = replace_once(s, load_app_old, load_app_new, "sync-device-name")
''','''    la=s.find('        fun loadApp(){')
    lb=s.find('\\n        fun load(){',la)
    if la<0 or lb<0: raise SystemExit("S54 sync-device-name structural anchor missing")
    s=s[:la]+'        '+load_app_new+s[lb:]
''','load-app')

swap('''    t = replace_once(
        t,
        'val items = store.pendingMutations(100)',
        'store.retryDateWindowRejects()\\n        val items = store.pendingMutations(100)',
        "date-reject-requeue",
    )
''','''    m=_re.search(r'val items\\s*=\\s*store\\.pendingMutations\\([^)]*\\)',t)
    if not m: raise SystemExit("S54 date-reject-requeue structural anchor missing")
    t=t[:m.start()]+'store.retryDateWindowRejects()\\n        '+m.group(0)+t[m.end():]
''','transport-requeue')

swap('''    t = replace_once(
        t,
        'val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap")',
        'val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap", "service_connections")',
        "connections-action",
    )
''','''    t,n=_re.subn(r'val SYNC_ACTIONS\\s*=\\s*setOf\\(([^)]*)\\)',lambda m: m.group(0) if 'service_connections' in m.group(1) else 'val SYNC_ACTIONS = setOf('+m.group(1).rstrip()+', "service_connections")',t,count=1)
    if n!=1: raise SystemExit(f"S54 connections-action structural mismatch: {n}")
''','transport-actions')

patch.write_text(q,encoding='utf-8')
print('S54A converted UI and transport anchors to structural matching')
