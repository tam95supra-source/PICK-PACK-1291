package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Build
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * S31D_RUNTIME_BRIDGE_COMPILE_FIX
 * Cache-only routing for hot reads. GAS is never used as a request fallback while the cached
 * canonical authority is SERVICE_PRIMARY. GAS session material may only be exchanged directly
 * with Service to obtain a Service token; no GAS network request is made here.
 */
class M2RuntimeBridge(context: Context) {
    private val app = context.applicationContext
    private val prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val transport = M2ServiceTransport(app)

    // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY: no independent session exchange lane.
    fun ensureServiceSession(gasToken:String?,force:Boolean=false):Boolean {
        if(ServiceFaultInjection.cloudflareDisabled(app)){recordServicePending("TEST_CLOUDFLARE_DISABLED");return false}
        val d=transport.cachedDiscoverySnapshot() ?: transport.discoverySnapshot() ?: return false
        val mode=d.optString("authority_mode");val base=d.optString("service_url").trimEnd('/')
        prefs.edit().putString(KEY_AUTHORITY_MODE,mode).putString(KEY_SERVICE_URL,base).apply()
        if(mode!="SERVICE_PRIMARY"||!validServiceUrl(base))return false
        val token=M2ServiceSessionManager.ensure(app,base,gasToken,force)
        if(!token.isNullOrBlank()){prefs.edit().putString(KEY_LAST_ROUTE,"SERVICE_D1_DIRECT").remove(KEY_LAST_ERROR).apply();return true}
        recordServicePending("SESSION_EXCHANGE_FAILED");return false
    }

    fun directRead(
        action: String,
        payload: JSONObject,
        gasToken: String?,
    ): M2ServiceTransport.TransportResult {
        if (action !in DIRECT_READS) {
            return M2ServiceTransport.TransportResult(false, false, 0, null, null)
        }

        val discovery = transport.cachedDiscoverySnapshot()
            ?: return M2ServiceTransport.TransportResult(true, false, 0, null, "DISCOVERY_WARMING")
        val mode = discovery.optString("authority_mode")
        val base = discovery.optString("service_url").trimEnd('/')
        prefs.edit().putString(KEY_AUTHORITY_MODE, mode).putString(KEY_SERVICE_URL, base).apply()

        // Only an explicit canonical Google authority may hand the read to the GAS compatibility path.
        if (mode == "GOOGLE_FALLBACK") {
            return M2ServiceTransport.TransportResult(false, false, 0, null, "FENCED_GOOGLE_FALLBACK")
        }
        if (mode != "SERVICE_PRIMARY" || !validServiceUrl(base)) {
            return M2ServiceTransport.TransportResult(true, false, 0, null, "AUTHORITY_NOT_SERVICE_PRIMARY")
        }
        if (!ensureServiceSession(gasToken)) {
            return M2ServiceTransport.TransportResult(true, false, 0, null, "SERVICE_SESSION_UNAVAILABLE")
        }

        fun one(): HttpResult = httpJson(
            "$base/v1/mobile/read",
            JSONObject(payload.toString()).put("action", action),
            prefs.getString(KEY_SERVICE_TOKEN, null),
        )

        return try {
            var response = one()
            if (response.code == 401 && ensureServiceSession(gasToken, force = true)) response = one()
            if (response.code >= 500 || response.code == -1) {
                recordServicePending(response.error ?: "SERVICE_READ_${response.code}")
                M2WorkScheduler.schedule(app)
                M2ServiceTransport.TransportResult(true, false, response.code, response.json, response.error)
            } else {
                if (response.code == 401) prefs.edit().remove(KEY_SERVICE_TOKEN).apply()
                if (response.ok) recordDirect()
                M2ServiceTransport.TransportResult(true, response.ok, response.code, response.json, response.error)
            }
        } catch (t: Throwable) {
            recordServicePending(t.message ?: "SERVICE_READ_NETWORK")
            M2WorkScheduler.schedule(app)
            M2ServiceTransport.TransportResult(true, false, -1, null, t.message)
        }
    }

    fun recoverAndRetryOperational(
        action: String,
        payload: JSONObject,
        gasToken: String?,
    ): M2ServiceTransport.TransportResult? = transport.operational(action, payload)

    fun recoverAndRetrySync(
        action: String,
        payload: JSONObject,
        gasToken: String?,
    ): M2ServiceTransport.TransportResult? {
        if (!ensureServiceSession(gasToken, force = true)) {
            return M2ServiceTransport.TransportResult(true, false, 0, null, "SERVICE_SESSION_UNAVAILABLE")
        }
        val result = transport.sync(action, payload)
        if (result.handled && result.ok) recordDirect()
        return result
    }

    fun recordDirect() {
        prefs.edit().putString(KEY_LAST_ROUTE, "SERVICE_D1_DIRECT").remove(KEY_LAST_ERROR).apply()
    }

    fun recordServicePending(reason: String? = null) {
        val edit = prefs.edit().putString(KEY_LAST_ROUTE, "SERVICE_D1_PENDING")
        if (!reason.isNullOrBlank()) edit.putString(KEY_LAST_ERROR, reason.take(120))
        edit.apply()
    }

    /** Compatibility method kept for callers; it cannot manufacture a Google route. */
    fun recordFallback(reason: String? = null) {
        val mode = transport.cachedDiscoverySnapshot()?.optString("authority_mode").orEmpty()
            .ifBlank { prefs.getString(KEY_AUTHORITY_MODE, "").orEmpty() }
        val route = when (mode) {
            "GOOGLE_FALLBACK" -> "GOOGLE_FALLBACK"
            "SERVICE_PRIMARY" -> "SERVICE_D1_PENDING"
            else -> "UNRESOLVED"
        }
        val edit = prefs.edit().putString(KEY_LAST_ROUTE, route)
        if (!reason.isNullOrBlank()) edit.putString(KEY_LAST_ERROR, reason.take(120))
        edit.apply()
    }

    /** Cache-only status. Rendering this method never performs discovery or other network I/O. */
    fun status(): JSONObject {
        val discovery = transport.cachedDiscoverySnapshot()
        val mode = discovery?.optString("authority_mode").orEmpty()
            .ifBlank { prefs.getString(KEY_AUTHORITY_MODE, "").orEmpty() }
        val url = discovery?.optString("service_url").orEmpty()
            .ifBlank { prefs.getString(KEY_SERVICE_URL, "").orEmpty() }
        val tokenPresent = !prefs.getString(KEY_SERVICE_TOKEN, null).isNullOrBlank()
        val route = prefs.getString(KEY_LAST_ROUTE, null) ?: when {
            mode == "GOOGLE_FALLBACK" -> "GOOGLE_FALLBACK"
            mode == "SERVICE_PRIMARY" && tokenPresent -> "SERVICE_D1_DIRECT"
            mode == "SERVICE_PRIMARY" -> "SERVICE_D1_PENDING"
            else -> "UNRESOLVED"
        }
        val label = when (route) {
            "SERVICE_D1_DIRECT" -> "Cloudflare / D1"
            "SERVICE_D1_PENDING" -> "Cloudflare • chờ đồng bộ"
            "GOOGLE_FALLBACK" -> "Google dự phòng"
            else -> "Đang xác định"
        }
        return JSONObject()
            .put("authority_mode", mode)
            .put("service_url", url)
            .put("service_session", tokenPresent)
            .put("route", route)
            .put("label", label)
            .put("provider", if (mode == "GOOGLE_FALLBACK") "Google dự phòng" else if (url.isNotBlank()) "Cloudflare" else "—")
            .put("last_error", prefs.getString(KEY_LAST_ERROR, "").orEmpty())
            .put("test_mode",ServiceFaultInjection.mode(app).stored)
    }

    fun clear() {
        prefs.edit().remove(KEY_SERVICE_TOKEN).remove(KEY_LAST_ROUTE).remove(KEY_LAST_ERROR).apply()
    }

    private data class HttpResult(
        val ok: Boolean,
        val code: Int,
        val json: JSONObject?,
        val error: String?,
    )

    private fun httpJson(endpoint: String, payload: JSONObject, bearer: String?): HttpResult {
        if(ServiceFaultInjection.cloudflareDisabled(app))return HttpResult(false,-1,null,"TEST_CLOUDFLARE_DISABLED")
        var connection: HttpURLConnection? = null
        return try {
            connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 1_500
                readTimeout = 3_000
                doOutput = true
                instanceFollowRedirects = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
                setRequestProperty("User-Agent", "PickPack1291-M2Runtime/${BuildConfig.VERSION_NAME}")
                if (!bearer.isNullOrBlank()) setRequestProperty("Authorization", "Bearer $bearer")
            }
            val requestBytes = payload.toString().toByteArray(Charsets.UTF_8)
            SyncDirectionTracker.recordUploadBytes(requestBytes.size.toLong())
            connection.outputStream.use { it.write(requestBytes) }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            SyncDirectionTracker.recordDownloadBytes(text.toByteArray(Charsets.UTF_8).size.toLong())
            val json = if (text.isBlank()) JSONObject() else JSONObject(text)
            val ok = code in 200..299 && json.optBoolean("ok", false)
            val error = if (ok) null else json.optJSONObject("error")?.optString("code")
                ?.takeIf { it.isNotBlank() } ?: json.optString("error", "HTTP_$code")
            HttpResult(ok, code, json, error)
        } catch (t: Throwable) {
            HttpResult(false, -1, null, t.message ?: "NETWORK")
        } finally {
            connection?.disconnect()
        }
    }

    private fun validServiceUrl(raw: String): Boolean = runCatching {
        val url = URL(raw)
        url.protocol == "https" && url.host.isNotBlank() &&
            (url.host.endsWith(".workers.dev") || url.host.endsWith(".pages.dev"))
    }.getOrDefault(false)

    companion object {
        private const val PREFS = "pp_m2_service_transport"
        private const val KEY_SERVICE_TOKEN = "service_token"
        private const val KEY_AUTHORITY_MODE = "runtime_authority_mode"
        private const val KEY_SERVICE_URL = "runtime_service_url"
        private const val KEY_LAST_ROUTE = "runtime_last_route"
        private const val KEY_LAST_ERROR = "runtime_last_error"
        val DIRECT_READS = setOf("employee_context", "master_options", "history_shared")
    }
}
