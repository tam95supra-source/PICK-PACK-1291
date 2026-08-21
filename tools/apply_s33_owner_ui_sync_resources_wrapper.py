#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'tools/apply_s33_owner_ui_sync_resources.py'
src=SCRIPT.read_text(encoding='utf-8')
old=(
"    # Generated call has one stable result assignment after the m2 selection.\n"
"    target='      val result = if (m2?.handled == true) {'\n"
"    if target not in s: raise SystemExit('S33 API result anchor missing')\n"
"    s=s.replace(target,'      val result = if (action in setOf(\"resource_master_list\",\"resource_master_upsert\",\"resource_master_delete\",\"history_correction\")) serviceOwnerCall(action,payload) else if (m2?.handled == true) {',1)\n"
)
new=(
"    # S33 wrapper: route owner-only Service actions before the existing S31 call router.\n"
"    call_pos=s.find('fun call(action: String')\n"
"    try_pos=s.find('try {',call_pos) if call_pos>=0 else -1\n"
"    if call_pos<0 or try_pos<0: raise SystemExit('S33 API call router anchor missing')\n"
"    owner_branch=(\n"
"        '      if (action in setOf(\\\"resource_master_list\\\",\\\"resource_master_upsert\\\",\\\"resource_master_delete\\\",\\\"history_correction\\\")) {\\n'\n"
"        '          val result=serviceOwnerCall(action,payload)\\n'\n"
"        '          if(result.code==401) clearSession()\\n'\n"
"        '          if(action in setOf(\\\"resource_master_upsert\\\",\\\"resource_master_delete\\\",\\\"history_correction\\\")) AppHistory.record(appContext,action,result.ok,result.error.orEmpty())\\n'\n"
"        '          callback(result)\\n'\n"
"        '          return@execute\\n'\n"
"        '      }\\n'\n"
"    )\n"
"    s=s[:try_pos+5]+owner_branch+s[try_pos+5:]\n"
)
if old not in src:
    raise SystemExit('S33 wrapper target block missing')
patched=src.replace(old,new,1)
ns={'__name__':'__main__','__file__':str(SCRIPT)}
exec(compile(patched,str(SCRIPT),'exec'),ns,ns)

# S33B compile/lifecycle guard. S32 uses expression-body Workers; foreground gating
# must use block bodies so an off-screen invocation exits before starting new sync.
WORKER=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2OutboxWorker.kt'
w=WORKER.read_text(encoding='utf-8')
old_flush='''    override fun doWork(): Result = try {
        if (!PpForegroundGate.isForeground()) return Result.success()
        if (M2ServiceTransport(applicationContext).flushOutbox()) Result.success() else Result.retry()
    } catch (_: Throwable) { Result.retry() }'''
new_flush='''    override fun doWork(): Result {
        if (!PpForegroundGate.isForeground()) return Result.success()
        return try {
            if (M2ServiceTransport(applicationContext).flushOutbox()) Result.success() else Result.retry()
        } catch (_: Throwable) { Result.retry() }
    }'''
old_catch='''    override fun doWork(): Result = try {
        if (!PpForegroundGate.isForeground()) return Result.success()
        val caughtUp = M2BackgroundSync.catchUp(applicationContext)
        M2PushRegistration.flush(applicationContext)
        if (caughtUp) Result.success() else Result.retry()
    } catch (_: Throwable) { Result.retry() }'''
new_catch='''    override fun doWork(): Result {
        if (!PpForegroundGate.isForeground()) return Result.success()
        return try {
            val caughtUp = M2BackgroundSync.catchUp(applicationContext)
            M2PushRegistration.flush(applicationContext)
            if (caughtUp) Result.success() else Result.retry()
        } catch (_: Throwable) { Result.retry() }
    }'''
if old_flush not in w or old_catch not in w:
    raise SystemExit('S33B Worker compile anchors missing')
w=w.replace(old_flush,new_flush,1).replace(old_catch,new_catch,1)
WORKER.write_text(w,encoding='utf-8')

# Preserve the S22 runtime provider helper if later UI block replacement removed it,
# and enforce existing edit rights: USER read-only, ADMIN N/N-1, SUPERADMIN N..N-6.
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
o=OPS.read_text(encoding='utf-8')
perm_old='private fun historyCanEdit(e:JSONObject):Boolean{val date=e.optString("business_date").ifBlank{e.optString("cache_business_date")};val ix=operationalStore.availableDates().take(7).indexOf(date);return ix>=0&&ix<=if(isSuper())6 else 1}'
perm_new='private fun historyCanEdit(e:JSONObject):Boolean{if(!isAdmin())return false;val date=e.optString("business_date").ifBlank{e.optString("cache_business_date")};val ix=operationalStore.availableDates().take(7).indexOf(date);return ix>=0&&ix<=if(isSuper())6 else 1}'
if perm_old not in o:
    raise SystemExit('S33B history permission anchor missing')
o=o.replace(perm_old,perm_new,1)
if 'private fun serviceProviderFromRuntime():String' not in o:
    anchor='    private fun connectionSummary():String{'
    if anchor not in o:
        raise SystemExit('S33B provider helper anchor missing')
    helper='''    private fun serviceProviderFromRuntime():String{
        val st=api.runtimeStatus();val mode=st.optString("authority_mode");val route=st.optString("route")
        return when{
            mode=="GOOGLE_FALLBACK"||route=="GAS_COMPAT"->"Google Drive"
            mode=="SERVICE_PRIMARY"||mode=="RECONCILING"||route.startsWith("SERVICE_")->"Cloudflare"
            st.optString("service_url").isNotBlank()->"Cloudflare"
            else->serviceProviderCache
        }
    }
'''
    o=o.replace(anchor,helper+anchor,1)
OPS.write_text(o,encoding='utf-8')

# Fail closed if any of the release-critical guards were not materialized.
w=WORKER.read_text(encoding='utf-8');o=OPS.read_text(encoding='utf-8')
assert 'override fun doWork(): Result {' in w and w.count('PpForegroundGate.isForeground()')>=3
assert 'if(!isAdmin())return false' in o
assert 'private fun serviceProviderFromRuntime():String' in o
print('Applied S33B compile-safe foreground gate, provider helper and history permission guard')
