#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'app/src/main/java/vn/pickpack1291/app/beta'
TRANSPORT=BASE/'M2ServiceTransport.kt'
RUNTIME=BASE/'M2RuntimeBridge.kt'
STORE=BASE/'OperationalDataStore.kt'
WORKER=BASE/'M2OutboxWorker.kt'
API=BASE/'BetaApiClient.kt'
LOG=BASE/'LocalLogManager.kt'
MANAGER=BASE/'M2ServiceSessionManager.kt'
MARK='S44_SESSION_SINGLEFLIGHT_OBSERVABILITY'

manager=r'''package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Build
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean

/**
 * S44_SESSION_SINGLEFLIGHT_OBSERVABILITY
 * One process-wide owner for Service PDA session acquisition/refresh.
 * Never logs bearer/GAS tokens, verifier material, passwords, cookies or secrets.
 */
object M2ServiceSessionManager {
    private const val PREFS="pp_m2_service_transport"
    private const val KEY_SERVICE_TOKEN="service_token"
    private val lock=Any()

    fun ensure(context:Context,base:String,gasTokenHint:String?=null,force:Boolean=false):String?=synchronized(lock){
        val app=context.applicationContext
        val prefs=app.getSharedPreferences(PREFS,Context.MODE_PRIVATE)
        val current=prefs.getString(KEY_SERVICE_TOKEN,null)
        if(!force&&!current.isNullOrBlank())return@synchronized current
        val gasToken=gasTokenHint?.takeIf{it.isNotBlank()} ?: BetaApiClient(app).token
        if(gasToken.isNullOrBlank()){
            M2TransportDiagnostics.noteSession(app,-1,false,false,"GAS_SESSION_MISSING",null)
            return@synchronized null
        }
        var conn:HttpURLConnection?=null
        val started=System.currentTimeMillis()
        try{
            conn=(URL("${base.trimEnd('/')}/v1/auth/gas-session").openConnection() as HttpURLConnection).apply{
                requestMethod="POST";connectTimeout=3000;readTimeout=6000;doOutput=true;instanceFollowRedirects=true
                setRequestProperty("Content-Type","application/json; charset=utf-8")
                setRequestProperty("Accept","application/json")
                setRequestProperty("User-Agent","PickPack1291-S44/${BuildConfig.VERSION_NAME}")
            }
            val payload=JSONObject().put("gas_token",gasToken).put("device_id",M2DeviceIdentity.id(app)).put("device_label","${Build.MANUFACTURER} ${Build.MODEL}")
            conn.outputStream.use{it.write(payload.toString().toByteArray(Charsets.UTF_8))}
            val code=conn.responseCode
            val stream=if(code in 200..299)conn.inputStream else conn.errorStream
            val text=stream?.bufferedReader(Charsets.UTF_8)?.use{it.readText()}.orEmpty()
            val json=runCatching{if(text.isBlank())JSONObject() else JSONObject(text)}.getOrNull()
            val ok=code in 200..299&&json?.optBoolean("ok",false)==true
            val token=json?.optString("token").orEmpty()
            val sessionId=tokenFingerprint(json?.optJSONObject("session")?.optString("session_id").orEmpty().ifBlank{token})
            val reused=json?.optJSONObject("session")?.optBoolean("reused",false)?:false
            val error=if(ok)null else json?.optJSONObject("error")?.optString("code")?.ifBlank{null}?:json?.optString("error")?.ifBlank{null}?:"HTTP_$code"
            if(ok&&token.isNotBlank()){
                prefs.edit().putString(KEY_SERVICE_TOKEN,token).apply()
                M2TransportDiagnostics.noteSession(app,code,true,reused,null,sessionId,System.currentTimeMillis()-started)
                token
            }else{
                M2TransportDiagnostics.noteSession(app,code,false,reused,error,sessionId,System.currentTimeMillis()-started)
                null
            }
        }catch(t:Throwable){
            M2TransportDiagnostics.noteSession(app,-1,false,false,t.javaClass.simpleName+":"+(t.message?:"NETWORK"),null,System.currentTimeMillis()-started)
            null
        }finally{conn?.disconnect()}
    }

    fun current(context:Context):String?=context.applicationContext.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getString(KEY_SERVICE_TOKEN,null)

    /** A stale 401 response may only clear the exact bearer it used, never a newer token. */
    fun clearIfSame(context:Context,used:String?){
        if(used.isNullOrBlank())return
        synchronized(lock){
            val prefs=context.applicationContext.getSharedPreferences(PREFS,Context.MODE_PRIVATE)
            if(prefs.getString(KEY_SERVICE_TOKEN,null)==used)prefs.edit().remove(KEY_SERVICE_TOKEN).apply()
        }
    }

    fun clear(context:Context)=synchronized(lock){context.applicationContext.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().remove(KEY_SERVICE_TOKEN).apply()}

    private fun tokenFingerprint(value:String):String?{
        if(value.isBlank())return null
        val d=MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        return d.take(6).joinToString(""){(it.toInt()and 0xff).toString(16).padStart(2,'0')}
    }
}

/** Safe, bounded diagnostics. No authentication material is stored. */
object M2TransportDiagnostics {
    private const val PREFS="pp_m2_transport_diag_s44"
    private val pumpRunning=AtomicBoolean(false)
    private fun prefs(c:Context)=c.applicationContext.getSharedPreferences(PREFS,Context.MODE_PRIVATE)
    private fun edit(c:Context,block:(android.content.SharedPreferences.Editor)->Unit){val e=prefs(c).edit();block(e);e.apply()}

    fun noteWake(c:Context,source:String)=edit(c){it.putString("last_wake",source.take(40)).putLong("last_wake_at",System.currentTimeMillis())}
    fun notePumpStart(c:Context,count:Int){pumpRunning.set(true);edit(c){it.putLong("pump_start_at",System.currentTimeMillis()).putInt("pump_start_items",count).putString("pump_result","RUNNING")}}
    fun notePumpEnd(c:Context,ok:Boolean,error:String?=null){pumpRunning.set(false);edit(c){it.putLong("pump_end_at",System.currentTimeMillis()).putString("pump_result",if(ok)"SUCCESS" else "RETRY");if(error.isNullOrBlank())it.remove("pump_error") else it.putString("pump_error",safe(error,300))}}
    fun noteBatch(c:Context,code:Int,ok:Boolean,error:String?,count:Int,durationMs:Long){edit(c){it.putLong("batch_at",System.currentTimeMillis()).putInt("batch_http",code).putBoolean("batch_ok",ok).putInt("batch_items",count).putLong("batch_ms",durationMs);if(error.isNullOrBlank())it.remove("batch_error") else it.putString("batch_error",safe(error,300))}}
    fun noteSession(c:Context,code:Int,ok:Boolean,reused:Boolean,error:String?,fingerprint:String?,durationMs:Long=0){edit(c){it.putLong("session_at",System.currentTimeMillis()).putInt("session_http",code).putBoolean("session_ok",ok).putBoolean("session_reused",reused).putLong("session_ms",durationMs);if(fingerprint.isNullOrBlank())it.remove("session_fp") else it.putString("session_fp",fingerprint);if(error.isNullOrBlank())it.remove("session_error") else it.putString("session_error",safe(error,300))}}

    fun snapshotLines(context:Context):List<String>{
        val app=context.applicationContext;prefs(app).let{p->
            val serviceTokenPresent=!app.getSharedPreferences("pp_m2_service_transport",Context.MODE_PRIVATE).getString("service_token",null).isNullOrBlank()
            val transport=app.getSharedPreferences("pp_m2_service_transport",Context.MODE_PRIVATE)
            return listOf(
                "diag_schema=S44_V1",
                "pump_running=${pumpRunning.get()}",
                "pump_start_at_ms=${p.getLong("pump_start_at",0)}",
                "pump_end_at_ms=${p.getLong("pump_end_at",0)}",
                "pump_start_items=${p.getInt("pump_start_items",0)}",
                "pump_result=${safe(p.getString("pump_result","").orEmpty(),80)}",
                "pump_error=${safe(p.getString("pump_error","").orEmpty(),300)}",
                "last_wake=${safe(p.getString("last_wake","").orEmpty(),40)}",
                "last_wake_at_ms=${p.getLong("last_wake_at",0)}",
                "batch_at_ms=${p.getLong("batch_at",0)}",
                "batch_http=${p.getInt("batch_http",0)}",
                "batch_ok=${p.getBoolean("batch_ok",false)}",
                "batch_items=${p.getInt("batch_items",0)}",
                "batch_ms=${p.getLong("batch_ms",0)}",
                "batch_error=${safe(p.getString("batch_error","").orEmpty(),300)}",
                "service_token_present=$serviceTokenPresent",
                "session_at_ms=${p.getLong("session_at",0)}",
                "session_http=${p.getInt("session_http",0)}",
                "session_ok=${p.getBoolean("session_ok",false)}",
                "session_reused=${p.getBoolean("session_reused",false)}",
                "session_ms=${p.getLong("session_ms",0)}",
                "session_fp=${safe(p.getString("session_fp","").orEmpty(),40)}",
                "session_error=${safe(p.getString("session_error","").orEmpty(),300)}",
                "service_failures=${transport.getInt("service_failures",0)}",
                "service_circuit_until_ms=${transport.getLong("circuit_until",0)}",
                "runtime_route=${safe(transport.getString("runtime_last_route","").orEmpty(),80)}",
                "runtime_error=${safe(transport.getString("runtime_last_error","").orEmpty(),300)}",
                "authority_mode=${safe(transport.getString("discovery_json","").orEmpty().let{runCatching{JSONObject(it).optString("authority_mode")}.getOrDefault("")},80)}"
            )
        }
    }
    private fun safe(v:String,n:Int)=v.replace("\n"," ").replace("\r"," ").take(n)
}
'''
MANAGER.write_text(manager,encoding='utf-8')

# --- BetaApiClient: login must not queue behind general API traffic. ---
a=API.read_text(encoding='utf-8')
if MARK not in a:
    needle='    private val executor = Executors.newSingleThreadExecutor()\n'
    if needle not in a: raise SystemExit('S44 BetaApi executor anchor missing')
    a=a.replace(needle,needle+'    private val authExecutor = Executors.newSingleThreadExecutor() // '+MARK+'\n',1)
    start=a.find('    fun login(loginId: String, password: String, callback: (Result) -> Unit) {')
    if start<0: raise SystemExit('S44 login anchor missing')
    pos=a.find('        executor.execute {',start)
    if pos<0: raise SystemExit('S44 login executor call missing')
    a=a[:pos]+a[pos:].replace('        executor.execute {','        authExecutor.execute {',1)
API.write_text(a,encoding='utf-8')

# --- Store: safe per-item outbox diagnostics. ---
s=STORE.read_text(encoding='utf-8')
if 'fun diagnosticOutbox(' not in s:
    anchor='    fun pendingMutationCount(): Int = withDbLock {'
    if anchor not in s: raise SystemExit('S44 store diagnostic anchor missing')
    fn=r'''    // S44: bounded safe diagnostics; body payload is intentionally NOT emitted.
    fun diagnosticOutbox(limit:Int=50): JSONArray = withDbLock {
        val out=JSONArray()
        readableDb().query("mutation_outbox",arrayOf("event_id","body_json","exclusive","status","attempt_count","next_attempt_at","queued_at","updated_at","last_error"),null,null,null,null,"queued_at ASC",limit.coerceIn(1,100).toString()).use{c->
            while(c.moveToNext()){
                val body=runCatching{JSONObject(c.getString(1))}.getOrDefault(JSONObject())
                out.put(JSONObject()
                    .put("event_id",c.getString(0)).put("action",body.optString("action")).put("exclusive",c.getInt(2)!=0)
                    .put("status",c.getString(3)).put("attempt_count",c.getInt(4)).put("next_attempt_at",c.getLong(5))
                    .put("queued_at",c.getLong(6)).put("updated_at",c.getLong(7)).put("last_error",c.getString(8)?:""))
            }
        }
        out
    }

'''
    s=s.replace(anchor,fn+anchor,1)
STORE.write_text(s,encoding='utf-8')

# --- Transport: one process-global flush owner; all session exchange delegates to manager. ---
t=TRANSPORT.read_text(encoding='utf-8')
if MARK not in t:
    sig='    fun flushOutbox(): Boolean {'
    if sig not in t: raise SystemExit('S44 flush signature missing')
    t=t.replace(sig,'''    // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY: every immediate/WorkManager trigger shares this lock.
    fun flushOutbox(): Boolean = synchronized(FLUSH_LOCK) {
        val count=runCatching{store.unresolvedMutations(100).size}.getOrDefault(0)
        M2TransportDiagnostics.notePumpStart(app,count)
        val result=runCatching{flushOutboxLocked()}.getOrElse{M2TransportDiagnostics.notePumpEnd(app,false,it.message?:it.javaClass.simpleName);false}
        M2TransportDiagnostics.notePumpEnd(app,result)
        result
    }

    private fun flushOutboxLocked(): Boolean {''',1)
    # Background exchange helper body -> shared manager.
    a0=t.find('    private fun exchangeBackgroundServiceSession(base:String):String?{')
    if a0<0: raise SystemExit('S44 background exchange anchor missing')
    b0=t.find('\n    fun cachedDiscoverySnapshot(): JSONObject?',a0)
    if b0<0: b0=t.find('\n    fun discoverySnapshot(): JSONObject?',a0)
    if b0<0: raise SystemExit('S44 exchange end anchor missing')
    repl='''    private fun exchangeBackgroundServiceSession(base:String):String? = M2ServiceSessionManager.ensure(app,base,force=true)
'''
    t=t[:a0]+repl+t[b0:]
    # Safe stale-401 clear.
    t=t.replace('prefs.edit().remove(KEY_SERVICE_TOKEN).apply();val refreshed=exchangeBackgroundServiceSession(base)', 'M2ServiceSessionManager.clearIfSame(app,token);val refreshed=exchangeBackgroundServiceSession(base)')
    t=t.replace('prefs.edit().remove(KEY_SERVICE_TOKEN).apply()\n                return false','M2ServiceSessionManager.clearIfSame(app,token)\n                return false')
    # Instrument batch submit (post-S39 shape).
    old='fun submit(bearer:String):HttpResult{val body=JSONObject().put("events",JSONArray().apply{items.forEach{put(it.body)}});return httpJson("$base/v1/legacy-mutations/batch",body,bearer)}'
    new='fun submit(bearer:String):HttpResult{val body=JSONObject().put("events",JSONArray().apply{items.forEach{put(it.body)}});val started=System.currentTimeMillis();return httpJson("$base/v1/legacy-mutations/batch",body,bearer).also{M2TransportDiagnostics.noteBatch(app,it.code,it.ok,it.error,items.size,System.currentTimeMillis()-started)}}'
    if old not in t: raise SystemExit('S44 submit instrumentation anchor missing')
    t=t.replace(old,new,1)
    # companion global lock
    comp='    companion object {'
    if comp not in t: raise SystemExit('S44 transport companion missing')
    t=t.replace(comp,comp+'\n        private val FLUSH_LOCK=Any() // '+MARK,1)
TRANSPORT.write_text(t,encoding='utf-8')

# --- Runtime direct-read bridge must use exactly the same session manager. ---
r=RUNTIME.read_text(encoding='utf-8')
if MARK not in r:
    st=r.find('    fun ensureServiceSession(')
    en=r.find('\n    fun directRead(',st)
    if st<0 or en<0: raise SystemExit('S44 runtime ensure anchors missing')
    replacement=r'''    // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY: no independent session exchange lane.
    fun ensureServiceSession(gasToken:String?,force:Boolean=false):Boolean {
        val d=transport.cachedDiscoverySnapshot() ?: transport.discoverySnapshot() ?: return false
        val mode=d.optString("authority_mode");val base=d.optString("service_url").trimEnd('/')
        prefs.edit().putString(KEY_AUTHORITY_MODE,mode).putString(KEY_SERVICE_URL,base).apply()
        if(mode!="SERVICE_PRIMARY"||!validServiceUrl(base))return false
        val token=M2ServiceSessionManager.ensure(app,base,gasToken,force)
        if(!token.isNullOrBlank()){prefs.edit().putString(KEY_LAST_ROUTE,"SERVICE_D1_DIRECT").remove(KEY_LAST_ERROR).apply();return true}
        recordServicePending("SESSION_EXCHANGE_FAILED");return false
    }
'''
    r=r[:st]+replacement+r[en:]
RUNTIME.write_text(r,encoding='utf-8')

# --- Wake diagnostics; WorkManager is backup, not a competing pump owner. ---
w=WORKER.read_text(encoding='utf-8')
if MARK not in w:
    wake='    fun schedule(context: Context) {\n'
    if wake not in w: raise SystemExit('S44 scheduler anchor missing')
    w=w.replace(wake,wake+'        M2TransportDiagnostics.noteWake(context,"WORKMANAGER") // '+MARK+'\n',1)
    kick='    fun kick(context: Context) {\n'
    if kick in w:
        w=w.replace(kick,kick+'        M2TransportDiagnostics.noteWake(context,"IMMEDIATE")\n',1)
WORKER.write_text(w,encoding='utf-8')

# --- All diagnostic logs (manual/daily/crash) get bounded safe transport + outbox evidence. ---
l=LOG.read_text(encoding='utf-8')
if MARK not in l:
    common='''        appendLine("device=${safe(Build.DEVICE)}")\n'''
    if common not in l: raise SystemExit('S44 LocalLog common anchor missing')
    extra=r'''        appendLine("diagnostics_begin=S44_V1")
        runCatching { M2TransportDiagnostics.snapshotLines(context).forEach { appendLine(it) } }
            .onFailure { appendLine("transport_diag_error=${safe(it.javaClass.simpleName+":"+(it.message?:""))}") }
        runCatching {
            val arr=OperationalDataStore(context).diagnosticOutbox(50)
            appendLine("outbox_rows=${arr.length()}")
            for(i in 0 until arr.length()){
                val x=arr.optJSONObject(i)?:continue
                appendLine("outbox[$i].event_id=${safe(x.optString("event_id"))}")
                appendLine("outbox[$i].action=${safe(x.optString("action"))}")
                appendLine("outbox[$i].status=${safe(x.optString("status"))}")
                appendLine("outbox[$i].exclusive=${x.optBoolean("exclusive")}")
                appendLine("outbox[$i].attempt_count=${x.optInt("attempt_count")}")
                appendLine("outbox[$i].next_attempt_at=${x.optLong("next_attempt_at")}")
                appendLine("outbox[$i].queued_at=${x.optLong("queued_at")}")
                appendLine("outbox[$i].updated_at=${x.optLong("updated_at")}")
                appendLine("outbox[$i].last_error=${safe(x.optString("last_error"))}")
            }
        }.onFailure { appendLine("outbox_diag_error=${safe(it.javaClass.simpleName+":"+(it.message?:""))}") }
        appendLine("diagnostics_end=S44_V1")
'''
    l=l.replace(common,common+extra,1)
    l=l.replace('object LocalLogManager {','object LocalLogManager {\n    // '+MARK,1)
LOG.write_text(l,encoding='utf-8')

# Contracts.
T=TRANSPORT.read_text();R=RUNTIME.read_text();S=STORE.read_text();W=WORKER.read_text();A=API.read_text();L=LOG.read_text();M=MANAGER.read_text()
checks=[
    ('private val FLUSH_LOCK=Any()' in T and 'flushOutboxLocked' in T,'global flush single-flight'),
    ('M2ServiceSessionManager.ensure(app,base,force=true)' in T,'transport session delegation'),
    ('M2ServiceSessionManager.ensure(app,base,gasToken,force)' in R,'runtime session delegation'),
    ('clearIfSame' in T and 'clearIfSame' in M,'stale 401 safety'),
    ('authExecutor.execute' in A,'dedicated login executor'),
    ('fun diagnosticOutbox(' in S,'outbox diagnostics'),
    ('diagnostics_begin=S44_V1' in L and 'last_error=' in L,'manual/daily/crash rich diagnostics'),
    ('service_token_present=' in M and 'gas_token=' not in M and 'authorization=' not in M.lower(),'no secret diagnostic fields'),
    ('M2TransportDiagnostics.noteWake' in W,'wake diagnostics'),
    ('S40_OWNER_LOCAL_FIRST_REPAIR' in (BASE/'OperationsActivity.kt').read_text(),'S40 local-first preserved'),
]
for ok,label in checks:
    if not ok: raise SystemExit('S44 contract missing: '+label)
print('Applied S44 Android: single-flight session/outbox, safe rich diagnostics, dedicated login lane')
