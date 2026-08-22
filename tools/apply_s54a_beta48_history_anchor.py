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
''','''    # Date-window rejects are re-admitted by OperationalDataStore.pendingMutations().
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

store_header='''d = STORE.read_text(encoding="utf-8")
if MARK not in d:
'''
store_inject=r'''d = STORE.read_text(encoding="utf-8")
if MARK not in d:
    pending_old = '"status IN (\'LOCAL_PENDING\',\'PENDING\',\'RETRY\',\'OFFLINE_PROVISIONAL\') AND next_attempt_at <= ?"'
    pending_new = '"(status IN (\'LOCAL_PENDING\',\'PENDING\',\'RETRY\',\'OFFLINE_PROVISIONAL\') OR (status=\'REJECTED\' AND last_error=\'BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW\')) AND next_attempt_at <= ?"'
    if pending_old not in d: raise SystemExit("S54 pendingMutations durable-date-reject anchor missing")
    d=d.replace(pending_old,pending_new,1)
    count_old = '"SELECT COUNT(*) FROM mutation_outbox WHERE status IN (\'LOCAL_PENDING\',\'PENDING\',\'RETRY\',\'OFFLINE_PROVISIONAL\')"'
    count_new = '"SELECT COUNT(*) FROM mutation_outbox WHERE status IN (\'LOCAL_PENDING\',\'PENDING\',\'RETRY\',\'OFFLINE_PROVISIONAL\') OR (status=\'REJECTED\' AND last_error=\'BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW\')"'
    if count_old not in d: raise SystemExit("S54 pendingMutationCount durable-date-reject anchor missing")
    d=d.replace(count_old,count_new,1)
'''
if store_header not in q: raise SystemExit('S54A STORE header missing')
q=q.replace(store_header,store_inject,1)

swap('''    d = replace_once(
        d,
        'class OperationalDataStore(context: Context) {\\n    private val helper = helper(context.applicationContext)',
        'class OperationalDataStore(context: Context) {\\n    // S54_BETA48_OWNER_10_FIXES\\n    private val app = context.applicationContext\\n    private val helper = helper(app)',
        "store-context",
    )
''','''    d,n=_re.subn(r'class OperationalDataStore\\s*\\(\\s*context\\s*:\\s*Context\\s*\\)\\s*\\{', 'class OperationalDataStore(context: Context) {\\n    // S54_BETA48_OWNER_10_FIXES\\n    private val app = context.applicationContext', d, count=1)
    if n!=1: raise SystemExit(f"S54 store class structural mismatch: {n}")
    d,n=_re.subn(r'private val helper\\s*=\\s*helper\\(\\s*context\\.applicationContext\\s*\\)', 'private val helper = helper(app)', d, count=1)
    if n!=1: raise SystemExit(f"S54 store helper structural mismatch: {n}")
''','store-context')

swap('''    dates_anchor = '''    fun revisions(): Map<String, Long> = withDbLock {'''
    dp = d.find(dates_anchor)
    if dp < 0:
        raise SystemExit("S54 historyWindowDates insertion anchor missing")
''','''    dp=d.find('    fun revisions(')
    if dp < 0: raise SystemExit("S54 historyWindowDates structural insertion anchor missing")
''','store-dates')

swap('''    retry_anchor = '    fun markMutationSynced(eventId: String) = markMutationResolved(eventId, "CONFIRMED", "")\\n'
    retry_fun = '''    fun retryDateWindowRejects():Int=withDbLock{\\n        val db=writableDb();val now=System.currentTimeMillis();var count=0\\n        db.rawQuery("SELECT COUNT(*) FROM mutation_outbox WHERE status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW'",null).use{c->if(c.moveToFirst())count=c.getInt(0)}\\n        if(count>0)db.execSQL("UPDATE mutation_outbox SET status='RETRY',next_attempt_at=?,updated_at=? WHERE status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW'",arrayOf(now,now))\\n        count\\n    }\\n\\n'''
    d = replace_once(d, retry_anchor, retry_fun + retry_anchor, "date-retry-method")
''','''    retry_fun = '''    fun retryDateWindowRejects():Int=withDbLock{\\n        val db=writableDb();val now=System.currentTimeMillis();var count=0\\n        db.rawQuery("SELECT COUNT(*) FROM mutation_outbox WHERE status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW'",null).use{c->if(c.moveToFirst())count=c.getInt(0)}\\n        if(count>0)db.execSQL("UPDATE mutation_outbox SET status='RETRY',next_attempt_at=?,updated_at=? WHERE status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW'",arrayOf(now,now))\\n        count\\n    }\\n\\n'''
    rp=d.find('    fun markMutationSynced(')
    if rp<0: raise SystemExit("S54 date-retry-method structural anchor missing")
    d=d[:rp]+retry_fun+d[rp:]
''','store-retry')

swap('''    summary_anchor = '    fun pendingCount(context: Context): Int = logDir(context).listFiles()?.count { it.isFile } ?: 0\\n'
    summary_fun = '''    // S54_BETA48_OWNER_10_FIXES\\n    fun summary(context:Context):String{\\n        val files=logDir(context).listFiles()?.filter{it.isFile}.orEmpty();val bytes=files.sumOf{it.length()};val latest=files.maxOfOrNull{it.lastModified()}?:0L\\n        fun size(v:Long)=when{v<1024L->"$v B";v<1024L*1024L->String.format(Locale.US,"%.1f KB",v/1024.0);else->String.format(Locale.US,"%.1f MB",v/(1024.0*1024.0))}\\n        val at=if(latest<=0L)"—" else SimpleDateFormat("HH:mm:ss dd/MM/yyyy",Locale.US).format(Date(latest))\\n        return "${files.size} tệp • ${size(bytes)} • mới nhất $at"\\n    }\\n\\n'''
    l = replace_once(l, summary_anchor, summary_anchor + '\\n' + summary_fun, "log-summary")
''','''    summary_fun = '''    // S54_BETA48_OWNER_10_FIXES\\n    fun summary(context:Context):String{\\n        val files=logDir(context).listFiles()?.filter{it.isFile}.orEmpty();val bytes=files.sumOf{it.length()};val latest=files.maxOfOrNull{it.lastModified()}?:0L\\n        fun size(v:Long)=when{v<1024L->"$v B";v<1024L*1024L->String.format(Locale.US,"%.1f KB",v/1024.0);else->String.format(Locale.US,"%.1f MB",v/(1024.0*1024.0))}\\n        val at=if(latest<=0L)"—" else SimpleDateFormat("HH:mm:ss dd/MM/yyyy",Locale.US).format(Date(latest))\\n        return "${files.size} tệp • ${size(bytes)} • mới nhất $at"\\n    }\\n\\n'''
    lp=l.find('    fun pendingCount(')
    if lp<0: raise SystemExit("S54 log-summary structural anchor missing")
    le=l.find('\\n',lp)
    if le<0: raise SystemExit("S54 log-summary line end missing")
    l=l[:le+1]+'\\n'+summary_fun+l[le+1:]
''','log-summary')

patch.write_text(q,encoding='utf-8')
print('S54A structuralized UI, transport, store and log patches')
