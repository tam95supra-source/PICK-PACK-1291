package vn.pickpack1291.app.beta

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
