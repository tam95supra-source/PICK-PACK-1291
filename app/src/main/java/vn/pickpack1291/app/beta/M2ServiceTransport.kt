package vn.pickpack1291.app.beta

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.util.Base64
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec
import kotlin.math.min

/** M2 Service transport. The APK never contains a Worker URL; discovery remains on the stable GAS endpoint. */
class M2ServiceTransport(context: Context) {
    data class TransportResult(val handled: Boolean, val ok: Boolean, val code: Int, val json: JSONObject?, val error: String?)

    private val app = context.applicationContext
    private val prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val store = OperationalDataStore(app)
    private val connectivity = app.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    fun loginFromPassword(loginId: String, password: String) {
        if (!hasNetwork()) return
        val d = discover(force = true) ?: return
        if (d.optString("authority_mode") != "SERVICE_PRIMARY") return
        val base = d.optString("service_url").trimEnd('/')
        if (!validServiceUrl(base)) return
        runCatching {
            val challenge = httpJson("$base/v1/auth/challenge", JSONObject().put("login_id", loginId.trim()), null)
            if (!challenge.ok || challenge.json == null) return
            val c = challenge.json
            val proof = proofForPassword(password, c.getString("salt"), c.optInt("iterations", 120_000), c.getString("challenge"))
            val body = JSONObject()
                .put("login_id", loginId.trim())
                .put("challenge_id", c.getString("challenge_id"))
                .put("proof", proof)
                .put("device_id", M2DeviceIdentity.id(app))
                .put("device_label", "${Build.MANUFACTURER} ${Build.MODEL}")
            val session = httpJson("$base/v1/auth/login", body, null)
            if (session.ok) {
                val token = session.json?.optString("token").orEmpty()
                if (token.isNotBlank()) prefs.edit().putString(KEY_SERVICE_TOKEN, token).apply()
                closeCircuit()
            }
        }.onFailure { recordFailure() }
    }

    fun operational(action: String, payload: JSONObject): TransportResult {
        if (action !in OPERATIONAL) return TransportResult(false, false, 0, null, null)
        if (!hasNetwork()) return queueOffline(action, payload)
        if (circuitOpen()) return TransportResult(false, false, 0, null, "CIRCUIT_OPEN")
        val discovery = discover() ?: return TransportResult(false, false, 0, null, "DISCOVERY_UNAVAILABLE")
        if (discovery.optString("authority_mode") != "SERVICE_PRIMARY") return TransportResult(false, false, 0, null, null)
        val base = discovery.optString("service_url").trimEnd('/'), token = prefs.getString(KEY_SERVICE_TOKEN, null)
        if (!validServiceUrl(base) || token.isNullOrBlank()) return TransportResult(false, false, 0, null, "SERVICE_SESSION_UNAVAILABLE")
        val eventId = payload.optString("event_id").ifBlank { java.util.UUID.randomUUID().toString() }
        val request = JSONObject()
            .put("action", action)
            .put("event_id", eventId)
            .put("device_id", M2DeviceIdentity.id(app))
            .put("payload", JSONObject(payload.toString()).put("event_id", eventId))
        return try {
            val r = httpJson("$base/v1/legacy-mutations", request, token)
            if (r.code >= 500 || r.code == -1) {
                recordFailure()
                TransportResult(false, false, r.code, r.json, r.error)
            } else {
                if (r.code == 401) prefs.edit().remove(KEY_SERVICE_TOKEN).apply()
                if (r.ok) closeCircuit()
                TransportResult(true, r.ok, r.code, r.json, r.error)
            }
        } catch (t: Throwable) {
            recordFailure()
            TransportResult(false, false, -1, null, t.message ?: "SERVICE_NETWORK_ERROR")
        }
    }

    fun flushOutbox(): Boolean {
        if (!hasNetwork() || circuitOpen()) return false
        val discovery = discover(force = true) ?: return false
        if (discovery.optString("authority_mode") != "SERVICE_PRIMARY") return false
        val base = discovery.optString("service_url").trimEnd('/'), token = prefs.getString(KEY_SERVICE_TOKEN, null)
        if (!validServiceUrl(base) || token.isNullOrBlank()) return false
        var retryNeeded = false
        for (item in store.pendingMutations(100)) {
            try {
                val r = httpJson("$base/v1/legacy-mutations", item.body, token)
                when {
                    r.ok -> store.markMutationSynced(item.eventId)
                    r.code == 409 || r.code == 403 || r.code == 400 -> store.markMutationConflict(item.eventId, r.json?.toString() ?: r.error.orEmpty())
                    r.code == 401 -> { prefs.edit().remove(KEY_SERVICE_TOKEN).apply(); retryNeeded = true; break }
                    else -> { store.markMutationRetry(item.eventId, r.error ?: "HTTP_${r.code}", retryDelay(item.attemptCount)); retryNeeded = true; recordFailure(); break }
                }
            } catch (t: Throwable) {
                store.markMutationRetry(item.eventId, t.message ?: "NETWORK", retryDelay(item.attemptCount)); retryNeeded = true; recordFailure(); break
            }
        }
        return !retryNeeded
    }

    fun discoverySnapshot(): JSONObject? = discover()

    private fun queueOffline(action: String, payload: JSONObject): TransportResult {
        val eventId = payload.optString("event_id").ifBlank { java.util.UUID.randomUUID().toString() }
        val request = JSONObject()
            .put("action", action)
            .put("event_id", eventId)
            .put("device_id", M2DeviceIdentity.id(app))
            .put("payload", JSONObject(payload.toString()).put("event_id", eventId))
        val exclusive = action == "enter" || action == "resource_change"
        store.enqueueMutation(request, exclusive)
        M2WorkScheduler.schedule(app)
        val json = JSONObject().put("ok", true).put("queued", true).put("offline_provisional", exclusive).put("projection", "OFFLINE_LOCAL").put("result", JSONObject().put("event_id", eventId))
        return TransportResult(true, true, 202, json, null)
    }

    private fun discover(force: Boolean = false): JSONObject? {
        val now = System.currentTimeMillis()
        if (!force) {
            val cachedAt = prefs.getLong(KEY_DISCOVERY_AT, 0L)
            val cached = prefs.getString(KEY_DISCOVERY_JSON, null)
            if (cached != null && now - cachedAt < DISCOVERY_TTL_MS) return runCatching { JSONObject(cached) }.getOrNull()
        }
        if (!hasNetwork()) return prefs.getString(KEY_DISCOVERY_JSON, null)?.let { runCatching { JSONObject(it) }.getOrNull() }
        return try {
            val body = JSONObject().put("action", "service_discovery").put("_device_id", M2DeviceIdentity.id(app)).put("_app_version", BuildConfig.VERSION_NAME).put("_app_channel", BuildConfig.CHANNEL)
            val r = httpJson(BuildConfig.GSHEET_API_URL, body, null, requireServiceHost = false)
            if (!r.ok || r.json == null) return null
            val j = r.json
            val service = j.optString("service_url")
            if (service.isNotBlank() && !validServiceUrl(service)) return null
            prefs.edit().putString(KEY_DISCOVERY_JSON, j.toString()).putLong(KEY_DISCOVERY_AT, now).apply()
            j.optJSONObject("authority")?.let(store::saveAuthority)
            j
        } catch (_: Throwable) { prefs.getString(KEY_DISCOVERY_JSON, null)?.let { runCatching { JSONObject(it) }.getOrNull() } }
    }

    private fun hasNetwork(): Boolean {
        val n = connectivity.activeNetwork ?: return false
        val c = connectivity.getNetworkCapabilities(n) ?: return false
        return c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    private fun circuitOpen(): Boolean = System.currentTimeMillis() < prefs.getLong(KEY_CIRCUIT_UNTIL, 0L)
    private fun recordFailure() {
        val failures = prefs.getInt(KEY_FAILURES, 0) + 1
        val e = prefs.edit().putInt(KEY_FAILURES, failures)
        if (failures >= 2) e.putLong(KEY_CIRCUIT_UNTIL, System.currentTimeMillis() + CIRCUIT_MS)
        e.apply()
    }
    private fun closeCircuit() { prefs.edit().putInt(KEY_FAILURES, 0).putLong(KEY_CIRCUIT_UNTIL, 0L).apply() }
    private fun retryDelay(attempt: Int): Long = min(15 * 60_000L, 5_000L * (1L shl min(attempt, 8)))

    private data class HttpResult(val ok: Boolean, val code: Int, val json: JSONObject?, val error: String?)
    private fun httpJson(endpoint: String, payload: JSONObject, bearer: String?, requireServiceHost: Boolean = true): HttpResult {
        if (requireServiceHost && !validServiceUrl(endpoint.substringBefore("/v1/"))) return HttpResult(false, -1, null, "SERVICE_URL_INVALID")
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"; connectTimeout = 3_000; readTimeout = 5_000; doOutput = true; instanceFollowRedirects = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8"); setRequestProperty("Accept", "application/json"); setRequestProperty("User-Agent", "PickPack1291-M2/${BuildConfig.VERSION_NAME}")
                if (!bearer.isNullOrBlank()) setRequestProperty("Authorization", "Bearer $bearer")
            }
            conn.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            val j = if (text.isBlank()) JSONObject() else JSONObject(text)
            val ok = code in 200..299 && j.optBoolean("ok", false)
            val errObj = j.optJSONObject("error")
            val error = if (ok) null else errObj?.optString("code")?.takeIf { it.isNotBlank() } ?: j.optString("error", "HTTP_$code")
            HttpResult(ok, code, j, error)
        } finally { conn?.disconnect() }
    }

    private fun validServiceUrl(raw: String): Boolean = runCatching {
        val u = URL(raw); u.protocol == "https" && u.host.isNotBlank() && (u.host.endsWith(".workers.dev") || u.host.endsWith(".pages.dev") || u.host == "localhost")
    }.getOrDefault(false)

    private fun proofForPassword(password: String, saltB64: String, iterations: Int, challenge: String): String {
        val key = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(PBEKeySpec(password.toCharArray(), b64uDecode(saltB64), iterations, 256)).encoded
        val mac = Mac.getInstance("HmacSHA256"); mac.init(SecretKeySpec(key, "HmacSHA256")); return b64u(mac.doFinal(challenge.toByteArray(Charsets.UTF_8)))
    }
    private fun b64u(bytes: ByteArray): String = Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
    private fun b64uDecode(v: String): ByteArray = Base64.decode(v, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)

    companion object {
        private const val PREFS = "pp_m2_service_transport"
        private const val KEY_SERVICE_TOKEN = "service_token"
        private const val KEY_DISCOVERY_JSON = "discovery_json"
        private const val KEY_DISCOVERY_AT = "discovery_at"
        private const val KEY_FAILURES = "service_failures"
        private const val KEY_CIRCUIT_UNTIL = "circuit_until"
        private const val DISCOVERY_TTL_MS = 60_000L
        private const val CIRCUIT_MS = 15_000L
        val OPERATIONAL = setOf("enter", "exit", "resource_change", "labor_start", "labor_finish")
    }
}

object M2DeviceIdentity {
    fun id(context: Context): String {
        val p=context.getSharedPreferences("pp_m2_device",Context.MODE_PRIVATE);p.getString("id",null)?.let{return it}
        val androidId=android.provider.Settings.Secure.getString(context.contentResolver,android.provider.Settings.Secure.ANDROID_ID).orEmpty()
        val raw=if(androidId.isNotBlank()&&androidId!="9774d56d682e549c")"android-$androidId" else "install-${java.util.UUID.randomUUID()}"
        val digest=MessageDigest.getInstance("SHA-256").digest("PickPack1291|$raw".toByteArray()).joinToString(""){(it.toInt()and 0xff).toString(16).padStart(2,'0')}
        return "m2-$digest".also{p.edit().putString("id",it).apply()}
    }
}
