package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Build
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * S13 production runtime bridge.
 *
 * Existing Beta18/Beta19 installations can retain a valid GAS session after OTA. This bridge
 * exchanges that already-authenticated session for a Service token without storing/reasking for
 * the password, then routes hot reads directly to Worker/D1. GAS remains discovery/fallback/OTA.
 */
class M2RuntimeBridge(context: Context) {
    private val app=context.applicationContext
    private val prefs=app.getSharedPreferences(PREFS,Context.MODE_PRIVATE)
    private val transport=M2ServiceTransport(app)

    fun ensureServiceSession(gasToken:String?,force:Boolean=false):Boolean {
        val d=transport.discoverySnapshot() ?: return false
        val mode=d.optString("authority_mode")
        val base=d.optString("service_url").trimEnd('/')
        prefs.edit().putString(KEY_AUTHORITY_MODE,mode).putString(KEY_SERVICE_URL,base).apply()
        if(mode!="SERVICE_PRIMARY"||!validServiceUrl(base))return false
        if(!force && !prefs.getString(KEY_SERVICE_TOKEN,null).isNullOrBlank())return true
        if(gasToken.isNullOrBlank())return false
        return try{
            val r=httpJson("$base/v1/auth/gas-session",JSONObject()
                .put("gas_token",gasToken)
                .put("device_id",M2DeviceIdentity.id(app))
                .put("device_label","${Build.MANUFACTURER} ${Build.MODEL}"),null)
            val token=r.json?.optString("token").orEmpty()
            if(r.ok&&token.isNotBlank()){
                prefs.edit().putString(KEY_SERVICE_TOKEN,token).putString(KEY_LAST_ROUTE,"SERVICE_D1_DIRECT").remove(KEY_LAST_ERROR).apply()
                true
            }else{
                prefs.edit().putString(KEY_LAST_ERROR,r.error?:"SESSION_EXCHANGE_FAILED").apply();false
            }
        }catch(t:Throwable){prefs.edit().putString(KEY_LAST_ERROR,t.message?:"SESSION_EXCHANGE_NETWORK").apply();false}
    }

    fun directRead(action:String,payload:JSONObject,gasToken:String?):M2ServiceTransport.TransportResult {
        if(action !in DIRECT_READS)return M2ServiceTransport.TransportResult(false,false,0,null,null)
        val d=transport.discoverySnapshot() ?: return M2ServiceTransport.TransportResult(false,false,0,null,"DISCOVERY_UNAVAILABLE")
        val mode=d.optString("authority_mode")
        val base=d.optString("service_url").trimEnd('/')
        prefs.edit().putString(KEY_AUTHORITY_MODE,mode).putString(KEY_SERVICE_URL,base).apply()
        if(mode!="SERVICE_PRIMARY"||!validServiceUrl(base))return M2ServiceTransport.TransportResult(false,false,0,null,null)
        if(!ensureServiceSession(gasToken))return M2ServiceTransport.TransportResult(false,false,0,null,"SERVICE_SESSION_UNAVAILABLE")
        fun one():HttpResult=httpJson("$base/v1/mobile/read",JSONObject(payload.toString()).put("action",action),prefs.getString(KEY_SERVICE_TOKEN,null))
        return try{
            var r=one()
            if(r.code==401&&ensureServiceSession(gasToken,force=true))r=one()
            if(r.code>=500||r.code==-1){
                recordFallback("SERVICE_READ_${r.code}")
                M2ServiceTransport.TransportResult(false,false,r.code,r.json,r.error)
            }else{
                if(r.code==401)prefs.edit().remove(KEY_SERVICE_TOKEN).apply()
                if(r.ok)recordDirect()
                M2ServiceTransport.TransportResult(true,r.ok,r.code,r.json,r.error)
            }
        }catch(t:Throwable){recordFallback(t.message?:"SERVICE_READ_NETWORK");M2ServiceTransport.TransportResult(false,false,-1,null,t.message)}
    }

    fun recoverAndRetryOperational(action:String,payload:JSONObject,gasToken:String?):M2ServiceTransport.TransportResult? {
        if(!ensureServiceSession(gasToken,force=true))return null
        val r=transport.operational(action,payload)
        if(r.handled&&r.ok)recordDirect()
        return r
    }

    fun recoverAndRetrySync(action:String,payload:JSONObject,gasToken:String?):M2ServiceTransport.TransportResult? {
        if(!ensureServiceSession(gasToken,force=true))return null
        val r=transport.sync(action,payload)
        if(r.handled&&r.ok)recordDirect()
        return r
    }

    fun recordDirect(){prefs.edit().putString(KEY_LAST_ROUTE,"SERVICE_D1_DIRECT").remove(KEY_LAST_ERROR).apply()}
    fun recordFallback(reason:String?=null){
        val mode=prefs.getString(KEY_AUTHORITY_MODE,"").orEmpty()
        val route=if(mode=="SERVICE_PRIMARY")"SERVICE_D1_VIA_GAS" else if(mode=="GOOGLE_FALLBACK")"GOOGLE_FALLBACK" else "GAS_COMPAT"
        val e=prefs.edit().putString(KEY_LAST_ROUTE,route);if(!reason.isNullOrBlank())e.putString(KEY_LAST_ERROR,reason.take(120));e.apply()
    }

    fun status():JSONObject {
        val d=transport.discoverySnapshot()
        val mode=d?.optString("authority_mode").orEmpty().ifBlank{prefs.getString(KEY_AUTHORITY_MODE,"").orEmpty()}
        val url=d?.optString("service_url").orEmpty().ifBlank{prefs.getString(KEY_SERVICE_URL,"").orEmpty()}
        val tokenPresent=!prefs.getString(KEY_SERVICE_TOKEN,null).isNullOrBlank()
        val route=prefs.getString(KEY_LAST_ROUTE,null) ?: when{
            mode=="SERVICE_PRIMARY"&&tokenPresent->"SERVICE_D1_DIRECT"
            mode=="SERVICE_PRIMARY"->"SERVICE_D1_VIA_GAS"
            mode=="GOOGLE_FALLBACK"->"GOOGLE_FALLBACK"
            else->"UNRESOLVED"
        }
        return JSONObject()
            .put("authority_mode",mode)
            .put("service_url",url)
            .put("service_session",tokenPresent)
            .put("route",route)
            .put("label",when(route){"SERVICE_D1_DIRECT"->"Cloudflare / D1";"SERVICE_D1_VIA_GAS"->"Cloudflare qua GAS";"GOOGLE_FALLBACK"->"Google dự phòng";"GAS_COMPAT"->"Google / GAS";else->"Đang xác định"})
            .put("last_error",prefs.getString(KEY_LAST_ERROR,"").orEmpty())
    }

    fun clear(){prefs.edit().remove(KEY_SERVICE_TOKEN).remove(KEY_LAST_ROUTE).remove(KEY_LAST_ERROR).apply()}

    private data class HttpResult(val ok:Boolean,val code:Int,val json:JSONObject?,val error:String?)
    private fun httpJson(endpoint:String,payload:JSONObject,bearer:String?):HttpResult{
        var conn:HttpURLConnection?=null
        return try{
            conn=(URL(endpoint).openConnection() as HttpURLConnection).apply{
                requestMethod="POST";connectTimeout=2_500;readTimeout=4_500;doOutput=true;instanceFollowRedirects=true
                setRequestProperty("Content-Type","application/json; charset=utf-8");setRequestProperty("Accept","application/json");setRequestProperty("User-Agent","PickPack1291-M2Runtime/${BuildConfig.VERSION_NAME}")
                if(!bearer.isNullOrBlank())setRequestProperty("Authorization","Bearer $bearer")
            }
            conn.outputStream.use{it.write(payload.toString().toByteArray(Charsets.UTF_8))}
            val code=conn.responseCode;val stream=if(code in 200..299)conn.inputStream else conn.errorStream
            val text=stream?.bufferedReader(Charsets.UTF_8)?.use{it.readText()}.orEmpty();val j=if(text.isBlank())JSONObject() else JSONObject(text)
            val ok=code in 200..299&&j.optBoolean("ok",false);val err=j.optJSONObject("error")?.optString("code")?.takeIf{it.isNotBlank()}?:j.optString("error","HTTP_$code")
            HttpResult(ok,code,j,if(ok)null else err)
        }catch(t:Throwable){HttpResult(false,-1,null,t.message?:"NETWORK")}
        finally{conn?.disconnect()}
    }

    private fun validServiceUrl(raw:String)=runCatching{val u=URL(raw);u.protocol=="https"&&u.host.isNotBlank()&&(u.host.endsWith(".workers.dev")||u.host.endsWith(".pages.dev"))}.getOrDefault(false)

    companion object{
        private const val PREFS="pp_m2_service_transport"
        private const val KEY_SERVICE_TOKEN="service_token"
        private const val KEY_AUTHORITY_MODE="runtime_authority_mode"
        private const val KEY_SERVICE_URL="runtime_service_url"
        private const val KEY_LAST_ROUTE="runtime_last_route"
        private const val KEY_LAST_ERROR="runtime_last_error"
        val DIRECT_READS=setOf("employee_context","master_options","history_shared")
    }
}
