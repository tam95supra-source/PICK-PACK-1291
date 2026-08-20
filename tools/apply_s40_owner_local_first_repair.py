#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
STORE=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt'
PROJ=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/PdaLocalProjection.kt'
TRANSPORT=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt'
MARK='S40_OWNER_LOCAL_FIRST_REPAIR'


def replace_fun(src:str, signature:str, replacement:str)->str:
    a=src.find('    private fun '+signature)
    if a<0: raise SystemExit('S40 function anchor missing: '+signature)
    b=src.find('\n    private fun ',a+20)
    if b<0: raise SystemExit('S40 next function anchor missing: '+signature)
    return src[:a]+replacement.rstrip()+'\n'+src[b:]

# 1) Local visible state must include every unresolved event, not only rows whose retry timer is due.
s=STORE.read_text(encoding='utf-8')
if 'fun unresolvedMutations(' not in s:
    anchor='    fun pendingMutations(limit: Int = 100): List<PendingMutation> = withDbLock {'
    if anchor not in s: raise SystemExit('S40 unresolved mutation anchor missing')
    helper=r'''    // S40_OWNER_LOCAL_FIRST_REPAIR: UI/local projection sees all unresolved events regardless of network retry backoff.
    fun unresolvedMutations(limit: Int = 500): List<PendingMutation> = withDbLock {
        val out=ArrayList<PendingMutation>()
        readableDb().query(
            "mutation_outbox",
            arrayOf("event_id","body_json","exclusive","status","attempt_count","queued_at"),
            "status IN ('LOCAL_PENDING','PENDING','RETRY','OFFLINE_PROVISIONAL')",
            null,null,null,"queued_at ASC",limit.coerceIn(1,500).toString(),
        ).use { c ->
            while(c.moveToNext()) runCatching{JSONObject(c.getString(1))}.getOrNull()?.let{body->
                out+=PendingMutation(c.getString(0),body,c.getInt(2)==1,c.getString(3),c.getInt(4),c.getLong(5))
            }
        }
        out
    }

'''
    s=s.replace(anchor,helper+anchor,1)
STORE.write_text(s,encoding='utf-8')

# 2) Device projection overlays all unresolved local events, including RETRY rows waiting for network retry.
# It must also be able to render NOT_ENTERED from master data on a cold/no-day-snapshot PDA.
p=PROJ.read_text(encoding='utf-8')
p=p.replace('store.pendingMutations(500)','store.unresolvedMutations(500)')
p=p.replace('''        val day = store.loadDay(businessDate) ?: return null
        val sessions = day.optJSONArray("sessions") ?: JSONArray()''','''        val day = store.loadDay(businessDate)
        val sessions = day?.optJSONArray("sessions") ?: JSONArray()''',1)
p=p.replace('''.put("business_date", day.optString("business_date", businessDate))''','''.put("business_date", day?.optString("business_date", businessDate) ?: businessDate)''',1)
old='''                        copyIfPresent(payload, this, "shift", "work_choice", "pda_serial", "user_pick", "pack_table", "user_pack")'''
if old in p:
    p=p.replace(old,'''                        copyIfPresent(payload, this, "shift", "work_choice", "pda_serial", "user_pick", "pack_table", "user_pack", "resource_note")
                        if(payload.has("pda_status_at_enter")) put("pda_enter_status",payload.optString("pda_status_at_enter"))''',1)
old_exit='''                    session = (session ?: JSONObject()).apply { put("mnv", mnv); put("state", "ENDED") }'''
if old_exit in p:
    p=p.replace(old_exit,'''                    session = (session ?: JSONObject()).apply {
                        put("mnv",mnv);put("state","ENDED")
                        if(payload.has("pda_exit_status"))put("pda_exit_status",payload.optString("pda_exit_status"))
                    }''',1)
PROJ.write_text(p,encoding='utf-8')

# 3) When a background worker is awake, submit every unresolved retryable event. WorkManager owns network backoff.
t=TRANSPORT.read_text(encoding='utf-8')
a=t.find('    fun flushOutbox(): Boolean {')
b=t.find('\n    fun cachedDiscoverySnapshot(): JSONObject?',a)
if a<0 or b<0: raise SystemExit('S40 flushOutbox anchors missing')
block=t[a:b]
block=block.replace('store.pendingMutations(100)','store.unresolvedMutations(100)')
t=t[:a]+block+t[b:]
TRANSPORT.write_text(t,encoding='utf-8')

# 4) Scan/session UI is local-first. Service revalidation may refresh confirmed state but may never block/overwrite unresolved local state.
o=OPS.read_text(encoding='utf-8')
load=r'''    // S40_OWNER_LOCAL_FIRST_REPAIR: owner lock = SQLite/PDA first, Service reconcile later.
    private fun loadEmployee(mnv: String, button: Button? = null) {
        val resolved=MasterDataCache.resolveEmployeeMnv(this,mnv)
        if(resolved.isBlank()){button?.isEnabled=true;showError("MNV_REQUIRED");return}
        val generation=++employeeLookupGeneration
        val localNow=PdaLocalProjection.employeeContext(this,resolved)
        val localOptions=PdaLocalProjection.resourceOptions(this,resolved)
        val cached=MasterDataCache.employee(this,resolved)

        // Never wait for Service to decide whether the operator may continue on the PDA.
        if(localNow!=null) renderEmployee(localNow,localOptions)
        else if(cached!=null) renderCachedEmployee(cached)

        api.call("employee_context",JSONObject().put("mnv",resolved).put("include_options",true).put("include_labor",false)){result->runOnUiThread{
            if(generation!=employeeLookupGeneration)return@runOnUiThread
            button?.isEnabled=true
            val overlay=PdaLocalProjection.employeeContext(this@OperationsActivity,resolved)
            if(!result.ok){
                // Local state remains usable and visible. A remote read error is informational only.
                if(overlay!=null){
                    renderEmployee(overlay,PdaLocalProjection.resourceOptions(this@OperationsActivity,resolved))
                    TopNotice.show(this@OperationsActivity,"Service chưa xác nhận được; thao tác vẫn lưu local và sẽ đồng bộ nền.",TopNotice.Kind.WARNING)
                }else if(result.code==401){sessionExpired()} else showError(result.error?:"Không kiểm tra được mã nhân viên")
                return@runOnUiThread
            }
            // If any unresolved local mutation exists for this employee, never let a stale server snapshot roll UI backward.
            if(overlay!=null&&overlay.optString("reconciliation_state")=="LOCAL_PENDING"){
                renderEmployee(overlay,PdaLocalProjection.resourceOptions(this@OperationsActivity,resolved));return@runOnUiThread
            }
            val ctx=result.json?:JSONObject();val options=ctx.optJSONObject("options")?:localOptions
            renderEmployee(ctx,options)
        }}
    }'''
o=replace_fun(o,'loadEmployee(mnv: String, button: Button? = null) {',load)

# 5) History metrics count actual immutable event rows, while cards may remain grouped for readability.
# S36 owns this History implementation; S39 only changes paging. Patch the S36 render metrics directly.
old_metrics='''val states=groups.map{g->if(g.value.any{statusOf(it)=="FAILED"})"FAILED" else if(g.value.any{statusOf(it)=="PENDING"})"PENDING" else "SYNCED"};val pending=states.count{it=="PENDING"};val failed=states.count{it=="FAILED"}
            fun updateMetric(v:View,n:Int){if(v is LinearLayout&&v.childCount>1)(v.getChildAt(1) as? TextView)?.text=n.toString()};updateMetric(allBtn,groups.size);updateMetric(pendingBtn,pending);updateMetric(failBtn,failed)'''
new_metrics='''val states=groups.map{g->if(g.value.any{statusOf(it)=="FAILED"})"FAILED" else if(g.value.any{statusOf(it)=="PENDING"})"PENDING" else "SYNCED"};val pending=rows.count{statusOf(it)=="PENDING"};val failed=rows.count{statusOf(it)=="FAILED"}
            fun updateMetric(v:View,n:Int){if(v is LinearLayout&&v.childCount>1)(v.getChildAt(1) as? TextView)?.text=n.toString()};updateMetric(allBtn,rows.size);updateMetric(pendingBtn,pending);updateMetric(failBtn,failed)'''
if old_metrics not in o: raise SystemExit('S40 S36 History metric anchor missing')
o=o.replace(old_metrics,new_metrics,1)
OPS.write_text(o,encoding='utf-8')

# Contract assertions: these are owner locks, not optional optimizations.
store=STORE.read_text(encoding='utf-8');proj=PROJ.read_text(encoding='utf-8');tr=TRANSPORT.read_text(encoding='utf-8');ops=OPS.read_text(encoding='utf-8')
checks=[
    ('fun unresolvedMutations(' in store,'all unresolved local state'),
    ('store.unresolvedMutations(500)' in proj,'projection includes retry rows'),
    ('val day = store.loadDay(businessDate)\n        val sessions = day?.optJSONArray("sessions") ?: JSONArray()' in proj,'cold-cache local employee projection'),
    ('pda_status_at_enter' in proj and 'pda_enter_status' in proj,'local PDA condition'),
    ('store.unresolvedMutations(100)' in tr,'awake worker flushes unresolved'),
    ('PdaLocalProjection.employeeContext(this,resolved)' in ops,'scan renders local projection first'),
    ('Service chưa xác nhận được; thao tác vẫn lưu local' in ops,'remote read never blocks local UI'),
    ('val pending=rows.count{statusOf(it)=="PENDING"}' in ops,'waiting count is event-level'),
    ('val failed=rows.count{statusOf(it)=="FAILED"}' in ops,'failed count is event-level'),
    ('updateMetric(allBtn,rows.size)' in ops,'total count is event-level'),
]
for ok,label in checks:
    if not ok: raise SystemExit('S40 contract missing: '+label)
print('Applied S40: restored owner-locked PDA-local-first scan/session semantics, cold-cache projection, unresolved overlay/flush, and exact event metrics')
