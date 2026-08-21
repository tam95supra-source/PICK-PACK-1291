#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
OPS = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
TRANSPORT = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt'
RUNTIME = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/M2RuntimeBridge.kt'
FG = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/ForegroundSyncCoordinator.kt'
BG = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/M2BackgroundSync.kt'
NET = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/DeviceNetworkStatus.kt'
MARK = 'S31_SERVICE_FIRST_HOTPATH'

transport = r'''package vn.pickpack1291.app.beta

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.os.SystemClock
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec
import kotlin.math.min

/** S31_SERVICE_FIRST_HOTPATH: SQLite hot path; Service/D1 direct; GAS background authority fallback only. */
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
            val body = JSONObject().put("login_id", loginId.trim()).put("challenge_id", c.getString("challenge_id")).put("proof", proof)
                .put("device_id", M2DeviceIdentity.id(app)).put("device_label", "${Build.MANUFACTURER} ${Build.MODEL}")
            val session = httpJson("$base/v1/auth/login", body, null)
            if (session.ok) {
                val token = session.json?.optString("token").orEmpty()
                if (token.isNotBlank()) prefs.edit().putString(KEY_SERVICE_TOKEN, token).apply()
                closeCircuit()
            }
        }.onFailure { recordFailure() }
    }

    /** Durable SQLite enqueue only. No network/discovery/authority lookup is allowed here. */
    fun operational(action: String, payload: JSONObject): TransportResult {
        if (action !in OPERATIONAL) return TransportResult(false, false, 0, null, null)
        val eventId = payload.optString("event_id").ifBlank { java.util.UUID.randomUUID().toString() }
        payload.put("event_id", eventId)
        val request = JSONObject().put("action", action).put("event_id", eventId).put("device_id", M2DeviceIdentity.id(app))
            .put("payload", JSONObject(payload.toString()).put("event_id", eventId))
        val exclusive = action == "enter" || action == "resource_change"
        store.enqueueMutation(request, exclusive)
        M2WorkScheduler.schedule(app)
        val mode = cachedDiscoverySnapshot()?.optString("authority_mode").orEmpty()
        val projection = when { !hasNetwork() -> "OFFLINE_LOCAL"; mode == "GOOGLE_FALLBACK" -> "GOOGLE_FALLBACK_PENDING"; else -> "SERVICE_D1_PENDING" }
        return queuedResult(eventId, exclusive, projection)
    }

    fun acknowledgeFallback(eventId: String, ok: Boolean, error: String?) {
        if (eventId.isBlank()) return
        if (ok) store.markMutationSynced(eventId) else if (!error.isNullOrBlank()) store.markMutationRetry(eventId, error, 5_000L)
    }

    /** Direct Service read using cached discovery only. A Service failure is handled, never a GAS fall-through. */
    fun sync(action: String, payload: JSONObject): TransportResult {
        if (action !in SYNC_ACTIONS) return TransportResult(false, false, 0, null, null)
        if (!hasNetwork()) return TransportResult(true, false, -1, null, "OFFLINE_LOCAL")
        val discovery = cachedDiscoverySnapshot() ?: return TransportResult(true, false, 0, null, "DISCOVERY_WARMING")
        val mode = discovery.optString("authority_mode")
        if (mode == "GOOGLE_FALLBACK") return TransportResult(false, false, 0, null, "FENCED_GOOGLE_FALLBACK")
        if (mode != "SERVICE_PRIMARY") return TransportResult(true, false, 0, null, "AUTHORITY_NOT_SERVICE_PRIMARY")
        if (circuitOpen()) return TransportResult(true, false, -1, null, "SERVICE_CIRCUIT_OPEN")
        val base = discovery.optString("service_url").trimEnd('/')
        val token = prefs.getString(KEY_SERVICE_TOKEN, null)
        if (!validServiceUrl(base) || token.isNullOrBlank()) return TransportResult(true, false, 0, null, "SERVICE_SESSION_UNAVAILABLE")
        val request = JSONObject(payload.toString()).put("action", action)
        val started = SystemClock.elapsedRealtime()
        return try {
            val r = httpJson("$base/v1/legacy-sync", request, token)
            val rtt = (SystemClock.elapsedRealtime() - started).coerceAtLeast(0L)
            val body = (r.json?.let { JSONObject(it.toString()) } ?: JSONObject()).put("_service_rtt_ms", rtt)
            if (r.code >= 500 || r.code == -1) {
                recordFailure(); M2WorkScheduler.schedule(app); TransportResult(true, false, r.code, body, r.error ?: "SERVICE_UNAVAILABLE")
            } else {
                if (r.code == 401) prefs.edit().remove(KEY_SERVICE_TOKEN).apply()
                if (r.ok) closeCircuit()
                TransportResult(true, r.ok, r.code, body, r.error)
            }
        } catch (t: Throwable) {
            val rtt = (SystemClock.elapsedRealtime() - started).coerceAtLeast(0L)
            recordFailure(); M2WorkScheduler.schedule(app)
            TransportResult(true, false, -1, JSONObject().put("_service_rtt_ms", rtt), t.message ?: "SERVICE_READ_NETWORK_ERROR")
        }
    }

    /** Background worker: Service first. GAS may confirm fallback only after 3 consecutive Service failures. */
    fun flushOutbox(): Boolean {
        if (!hasNetwork()) return false
        var discovery = cachedDiscoverySnapshot()
        if (discovery == null) discovery = discover(force = true)
        if (discovery == null) return false
        if (discovery.optString("authority_mode") == "GOOGLE_FALLBACK") return flushFallbackItems(store.pendingMutations(100))
        if (discovery.optString("authority_mode") != "SERVICE_PRIMARY") return false
        if (circuitOpen()) {
            if (failureCount() >= FALLBACK_PROBE_FAILURES && fallbackProbeDue()) {
                val confirmed = discover(force = true); noteFallbackProbe()
                if (confirmed?.optString("authority_mode") == "GOOGLE_FALLBACK") return flushFallbackItems(store.pendingMutations(100))
            }
            return false
        }
        val base = discovery.optString("service_url").trimEnd('/')
        val token = prefs.getString(KEY_SERVICE_TOKEN, null)
        if (!validServiceUrl(base) || token.isNullOrBlank()) return false
        val items = store.pendingMutations(100)
        if (items.isEmpty()) return true
        return try {
            val body = JSONObject().put("events", JSONArray().apply { items.forEach { put(it.body) } })
            val r = httpJson("$base/v1/legacy-mutations/batch", body, token)
            if (r.code == 401) {
                prefs.edit().remove(KEY_SERVICE_TOKEN).apply()
                items.forEach { store.markMutationRetry(it.eventId, "SERVICE_SESSION_UNAVAILABLE", retryDelay(it.attemptCount)) }
                return false
            }
            if (!r.ok || r.json == null) {
                if (r.code >= 500 || r.code == -1) recordFailure()
                if (failureCount() >= FALLBACK_PROBE_FAILURES && fallbackProbeDue()) {
                    val confirmed = discover(force = true); noteFallbackProbe()
                    if (confirmed?.optString("authority_mode") == "GOOGLE_FALLBACK") return flushFallbackItems(items)
                }
                items.forEach { store.markMutationRetry(it.eventId, r.error ?: "HTTP_${r.code}", retryDelay(it.attemptCount)) }
                return false
            }
            val results = r.json.optJSONArray("results") ?: JSONArray()
            val byId = items.associateBy { it.eventId }
            var retryNeeded = false
            for (i in 0 until results.length()) {
                val result = results.optJSONObject(i) ?: continue
                val eventId = result.optString("local_event_id")
                val item = byId[eventId] ?: continue
                val error = result.optString("error_code").ifBlank { result.optJSONObject("conflict")?.toString().orEmpty() }
                when (result.optString("status")) {
                    "CONFIRMED", "DUPLICATE" -> store.markMutationSynced(eventId)
                    "REVIEW_REQUIRED" -> store.markMutationReviewRequired(eventId, error)
                    "REJECTED" -> if (result.optBoolean("retryable", false)) { store.markMutationRetry(eventId, error.ifBlank { "RETRYABLE_REJECT" }, retryDelay(item.attemptCount)); retryNeeded = true } else store.markMutationRejected(eventId, error)
                    else -> { store.markMutationRetry(eventId, "BATCH_RESULT_INVALID", retryDelay(item.attemptCount)); retryNeeded = true }
                }
            }
            val returned = HashSet<String>().apply { for (i in 0 until results.length()) add(results.optJSONObject(i)?.optString("local_event_id").orEmpty()) }
            items.filter { it.eventId !in returned }.forEach { store.markMutationRetry(it.eventId, "BATCH_RESULT_MISSING", retryDelay(it.attemptCount)); retryNeeded = true }
            if (!retryNeeded) closeCircuit()
            !retryNeeded
        } catch (t: Throwable) {
            recordFailure()
            if (failureCount() >= FALLBACK_PROBE_FAILURES && fallbackProbeDue()) {
                val confirmed = discover(force = true); noteFallbackProbe()
                if (confirmed?.optString("authority_mode") == "GOOGLE_FALLBACK") return flushFallbackItems(items)
            }
            items.forEach { store.markMutationRetry(it.eventId, t.message ?: "NETWORK", retryDelay(it.attemptCount)) }
            false
        }
    }

    fun cachedDiscoverySnapshot(): JSONObject? = prefs.getString(KEY_DISCOVERY_JSON, null)?.let { runCatching { JSONObject(it) }.getOrNull() }
    fun discoverySnapshot(): JSONObject? = cachedDiscoverySnapshot()

    private fun flushFallbackItems(items: List<OperationalDataStore.PendingMutation>): Boolean {
        if (items.isEmpty()) return true
        val gasToken = app.getSharedPreferences(AUTH_PREFS, Context.MODE_PRIVATE).getString(AUTH_TOKEN, null).orEmpty()
        if (gasToken.isBlank()) return false
        var allEligibleDone = true
        for (item in items) {
            val action = item.body.optString("action")
            if (action !in OPERATIONAL) { allEligibleDone = false; continue }
            val payload = JSONObject((item.body.optJSONObject("payload") ?: JSONObject()).toString()).put("action", action).put("event_id", item.eventId)
                .put("_app_version", BuildConfig.VERSION_NAME).put("_app_channel", BuildConfig.CHANNEL).put("_device_id", M2DeviceIdentity.id(app))
                .put("_device_label", "${Build.MANUFACTURER} ${Build.MODEL}").put("_token", gasToken)
            val r = httpJson(BuildConfig.GSHEET_API_URL, payload, null, requireServiceHost = false)
            if (r.ok) store.markMutationSynced(item.eventId) else { allEligibleDone = false; store.markMutationRetry(item.eventId, r.error ?: "GOOGLE_FALLBACK_FAILED", retryDelay(item.attemptCount)) }
        }
        return allEligibleDone
    }

    private fun queuedResult(eventId: String, exclusive: Boolean, projection: String): TransportResult = TransportResult(true, true, 202,
        JSONObject().put("ok", true).put("queued", true).put("reconciliation_state", "LOCAL_PENDING").put("provisional", exclusive)
            .put("projection", projection).put("result", JSONObject().put("event_id", eventId)), null)

    private fun discover(force: Boolean = false): JSONObject? {
        val now = System.currentTimeMillis()
        if (!force) {
            val cachedAt = prefs.getLong(KEY_DISCOVERY_AT, 0L); val cached = prefs.getString(KEY_DISCOVERY_JSON, null)
            if (cached != null && now - cachedAt < DISCOVERY_TTL_MS) return runCatching { JSONObject(cached) }.getOrNull()
        }
        if (!hasNetwork()) return cachedDiscoverySnapshot()
        return try {
            val body = JSONObject().put("action", "service_discovery").put("_device_id", M2DeviceIdentity.id(app)).put("_app_version", BuildConfig.VERSION_NAME).put("_app_channel", BuildConfig.CHANNEL)
            val r = httpJson(BuildConfig.GSHEET_API_URL, body, null, requireServiceHost = false)
            if (!r.ok || r.json == null) return cachedDiscoverySnapshot()
            val j = r.json; val service = j.optString("service_url")
            if (service.isNotBlank() && !validServiceUrl(service)) return cachedDiscoverySnapshot()
            prefs.edit().putString(KEY_DISCOVERY_JSON, j.toString()).putLong(KEY_DISCOVERY_AT, now).apply(); j.optJSONObject("authority")?.let(store::saveAuthority); j
        } catch (_: Throwable) { cachedDiscoverySnapshot() }
    }

    private fun hasNetwork(): Boolean { val n = connectivity.activeNetwork ?: return false; val c = connectivity.getNetworkCapabilities(n) ?: return false; return c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) }
    private fun failureCount(): Int = prefs.getInt(KEY_FAILURES, 0)
    private fun circuitOpen(): Boolean = System.currentTimeMillis() < prefs.getLong(KEY_CIRCUIT_UNTIL, 0L)
    private fun recordFailure() { val failures = failureCount() + 1; val e = prefs.edit().putInt(KEY_FAILURES, failures); if (failures >= FALLBACK_PROBE_FAILURES) e.putLong(KEY_CIRCUIT_UNTIL, System.currentTimeMillis() + CIRCUIT_MS); e.apply() }
    private fun closeCircuit() { prefs.edit().putInt(KEY_FAILURES, 0).putLong(KEY_CIRCUIT_UNTIL, 0L).apply() }
    private fun fallbackProbeDue(): Boolean = System.currentTimeMillis() - prefs.getLong(KEY_LAST_FALLBACK_PROBE_AT, 0L) >= FALLBACK_PROBE_MIN_MS
    private fun noteFallbackProbe() { prefs.edit().putLong(KEY_LAST_FALLBACK_PROBE_AT, System.currentTimeMillis()).apply() }
    private fun retryDelay(attempt: Int): Long = min(15 * 60_000L, 5_000L * (1L shl min(attempt, 8)))

    private data class HttpResult(val ok: Boolean, val code: Int, val json: JSONObject?, val error: String?)
    private fun httpJson(endpoint: String, payload: JSONObject, bearer: String?, requireServiceHost: Boolean = true): HttpResult {
        if (requireServiceHost && !validServiceUrl(endpoint.substringBefore("/v1/"))) return HttpResult(false, -1, null, "SERVICE_URL_INVALID")
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(endpoint).openConnection() as HttpURLConnection).apply { requestMethod = "POST"; connectTimeout = if (requireServiceHost) 1_500 else 3_000; readTimeout = if (requireServiceHost) 3_000 else 8_000; doOutput = true; instanceFollowRedirects = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8"); setRequestProperty("Accept", "application/json"); setRequestProperty("User-Agent", "PickPack1291-M2/${BuildConfig.VERSION_NAME}"); if (!bearer.isNullOrBlank()) setRequestProperty("Authorization", "Bearer $bearer") }
            conn.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }; val code = conn.responseCode; val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty(); val j = if (text.isBlank()) JSONObject() else JSONObject(text); val ok = code in 200..299 && j.optBoolean("ok", false)
            val error = if (ok) null else j.optJSONObject("error")?.optString("code")?.takeIf { it.isNotBlank() } ?: j.optString("error", "HTTP_$code"); HttpResult(ok, code, j, error)
        } catch (t: Throwable) { HttpResult(false, -1, null, t.message ?: "NETWORK") } finally { conn?.disconnect() }
    }

    private fun validServiceUrl(raw: String): Boolean = runCatching { val u = URL(raw); u.protocol == "https" && u.host.isNotBlank() && (u.host.endsWith(".workers.dev") || u.host.endsWith(".pages.dev") || u.host == "localhost") }.getOrDefault(false)
    private fun proofForPassword(password: String, saltB64: String, iterations: Int, challenge: String): String { val key = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(PBEKeySpec(password.toCharArray(), b64uDecode(saltB64), iterations, 256)).encoded; val mac = Mac.getInstance("HmacSHA256"); mac.init(SecretKeySpec(key, "HmacSHA256")); return b64u(mac.doFinal(challenge.toByteArray(Charsets.UTF_8))) }
    private fun b64u(bytes: ByteArray): String = Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
    private fun b64uDecode(v: String): ByteArray = Base64.decode(v, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)

    companion object { private const val PREFS = "pp_m2_service_transport"; private const val KEY_SERVICE_TOKEN = "service_token"; private const val KEY_DISCOVERY_JSON = "discovery_json"; private const val KEY_DISCOVERY_AT = "discovery_at"; private const val KEY_FAILURES = "service_failures"; private const val KEY_CIRCUIT_UNTIL = "circuit_until"; private const val KEY_LAST_FALLBACK_PROBE_AT = "fallback_probe_at"; private const val AUTH_PREFS = "pick_pack_auth_session_v2"; private const val AUTH_TOKEN = "token"; private const val DISCOVERY_TTL_MS = 10 * 60_000L; private const val CIRCUIT_MS = 15_000L; private const val FALLBACK_PROBE_FAILURES = 3; private const val FALLBACK_PROBE_MIN_MS = 30_000L; val OPERATIONAL = setOf("enter", "exit", "resource_change", "labor_start", "labor_finish"); val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap") }
}

object M2DeviceIdentity { fun id(context: Context): String { val p=context.getSharedPreferences("pp_m2_device",Context.MODE_PRIVATE);p.getString("id",null)?.let{return it}; val androidId=android.provider.Settings.Secure.getString(context.contentResolver,android.provider.Settings.Secure.ANDROID_ID).orEmpty(); val raw=if(androidId.isNotBlank()&&androidId!="9774d56d682e549c")"android-$androidId" else "install-${java.util.UUID.randomUUID()}"; val digest=MessageDigest.getInstance("SHA-256").digest("PickPack1291|$raw".toByteArray()).joinToString(""){(it.toInt()and 0xff).toString(16).padStart(2,'0')}; return "m2-$digest".also{p.edit().putString("id",it).apply()} } }
'''
TRANSPORT.write_text(transport, encoding='utf-8')

runtime = r'''package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Build
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** S31 runtime bridge: Service-first cached route; GAS is never a Service-primary request fallback. */
class M2RuntimeBridge(context: Context) {
    private val app=context.applicationContext; private val prefs=app.getSharedPreferences(PREFS,Context.MODE_PRIVATE); private val transport=M2ServiceTransport(app)
    fun ensureServiceSession(gasToken:String?,force:Boolean=false):Boolean { val d=transport.cachedDiscoverySnapshot() ?: return false; val mode=d.optString("authority_mode"); val base=d.optString("service_url").trimEnd('/'); prefs.edit().putString(KEY_AUTHORITY_MODE,mode).putString(KEY_SERVICE_URL,base).apply(); if(mode!="SERVICE_PRIMARY"||!validServiceUrl(base))return false; if(!force && !prefs.getString(KEY_SERVICE_TOKEN,null).isNullOrBlank())return true; if(gasToken.isNullOrBlank())return false; return try{ val r=httpJson("$base/v1/auth/gas-session",JSONObject().put("gas_token",gasToken).put("device_id",M2DeviceIdentity.id(app)).put("device_label","${Build.MANUFACTURER} ${Build.MODEL}"),null); val token=r.json?.optString("token").orEmpty(); if(r.ok&&token.isNotBlank()){prefs.edit().putString(KEY_SERVICE_TOKEN,token).putString(KEY_LAST_ROUTE,"SERVICE_D1_DIRECT").remove(KEY_LAST_ERROR).apply();true}else{recordServicePending(r.error?:"SESSION_EXCHANGE_FAILED");false} }catch(t:Throwable){recordServicePending(t.message?:"SESSION_EXCHANGE_NETWORK");false} }
    fun directRead(action:String,payload:JSONObject,gasToken:String?):M2ServiceTransport.TransportResult { if(action !in DIRECT_READS)return M2ServiceTransport.TransportResult(false,false,0,null,null); val d=transport.cachedDiscoverySnapshot() ?: return M2ServiceTransport.TransportResult(true,false,0,null,"DISCOVERY_WARMING"); val mode=d.optString("authority_mode"); val base=d.optString("service_url").trimEnd('/'); prefs.edit().putString(KEY_AUTHORITY_MODE,mode).putString(KEY_SERVICE_URL,base).apply(); if(mode=="GOOGLE_FALLBACK")return M2ServiceTransport.TransportResult(false,false,0,null,"FENCED_GOOGLE_FALLBACK"); if(mode!="SERVICE_PRIMARY"||!validServiceUrl(base))return M2ServiceTransport.TransportResult(true,false,0,null,"AUTHORITY_NOT_SERVICE_PRIMARY"); if(!ensureServiceSession(gasToken))return M2ServiceTransport.TransportResult(true,false,0,null,"SERVICE_SESSION_UNAVAILABLE"); fun one():HttpResult=httpJson("$base/v1/mobile/read",JSONObject(payload.toString()).put("action",action),prefs.getString(KEY_SERVICE_TOKEN,null)); return try{ var r=one(); if(r.code==401&&ensureServiceSession(gasToken,force=true))r=one(); if(r.code>=500||r.code==-1){recordServicePending("SERVICE_READ_${r.code}");M2WorkScheduler.schedule(app);M2ServiceTransport.TransportResult(true,false,r.code,r.json,r.error)}else{if(r.code==401)prefs.edit().remove(KEY_SERVICE_TOKEN).apply();if(r.ok)recordDirect();M2ServiceTransport.TransportResult(true,r.ok,r.code,r.json,r.error)}}catch(t:Throwable){recordServicePending(t.message?:"SERVICE_READ_NETWORK");M2WorkScheduler.schedule(app);M2ServiceTransport.TransportResult(true,false,-1,null,t.message)} }
    fun recoverAndRetryOperational(action:String,payload:JSONObject,gasToken:String?):M2ServiceTransport.TransportResult?=transport.operational(action,payload)
    fun recoverAndRetrySync(action:String,payload:JSONObject,gasToken:String?):M2ServiceTransport.TransportResult?{if(!ensureServiceSession(gasToken,force=true))return M2ServiceTransport.TransportResult(true,false,0,null,"SERVICE_SESSION_UNAVAILABLE");val r=transport.sync(action,payload);if(r.handled&&r.ok)recordDirect();return r}
    fun recordDirect(){prefs.edit().putString(KEY_LAST_ROUTE,"SERVICE_D1_DIRECT").remove(KEY_LAST_ERROR).apply()}; fun recordServicePending(reason:String?=null){val e=prefs.edit().putString(KEY_LAST_ROUTE,"SERVICE_D1_PENDING");if(!reason.isNullOrBlank())e.putString(KEY_LAST_ERROR,reason.take(120));e.apply()}
    fun recordFallback(reason:String?=null){val mode=transport.cachedDiscoverySnapshot()?.optString("authority_mode").orEmpty().ifBlank{prefs.getString(KEY_AUTHORITY_MODE,"").orEmpty()};val route=if(mode=="GOOGLE_FALLBACK")"GOOGLE_FALLBACK" else if(mode=="SERVICE_PRIMARY")"SERVICE_D1_PENDING" else "UNRESOLVED";val e=prefs.edit().putString(KEY_LAST_ROUTE,route);if(!reason.isNullOrBlank())e.putString(KEY_LAST_ERROR,reason.take(120));e.apply()}
    fun status():JSONObject { val d=transport.cachedDiscoverySnapshot(); val mode=d?.optString("authority_mode").orEmpty().ifBlank{prefs.getString(KEY_AUTHORITY_MODE,"").orEmpty()}; val url=d?.optString("service_url").orEmpty().ifBlank{prefs.getString(KEY_SERVICE_URL,"").orEmpty()}; val tokenPresent=!prefs.getString(KEY_SERVICE_TOKEN,null).isNullOrBlank(); val route=prefs.getString(KEY_LAST_ROUTE,null) ?: when{mode=="GOOGLE_FALLBACK"->"GOOGLE_FALLBACK";mode=="SERVICE_PRIMARY"&&tokenPresent->"SERVICE_D1_DIRECT";mode=="SERVICE_PRIMARY"->"SERVICE_D1_PENDING";else->"UNRESOLVED"}; return JSONObject().put("authority_mode",mode).put("service_url",url).put("service_session",tokenPresent).put("route",route).put("label",when(route){"SERVICE_D1_DIRECT"->"Cloudflare / D1";"SERVICE_D1_PENDING"->"Cloudflare • chờ đồng bộ";"GOOGLE_FALLBACK"->"Google dự phòng";else->"Đang xác định"}).put("last_error",prefs.getString(KEY_LAST_ERROR,"").orEmpty()) }
    fun clear(){prefs.edit().remove(KEY_SERVICE_TOKEN).remove(KEY_LAST_ROUTE).remove(KEY_LAST_ERROR).apply()}
    private data class HttpResult(val ok:Boolean,val code:Int,val json:JSONObject?,val error:String?); private fun httpJson(endpoint:String,payload:JSONObject,bearer:String?):HttpResult{var conn:HttpURLConnection?=null;return try{conn=(URL(endpoint).openConnection() as HttpURLConnection).apply{requestMethod="POST";connectTimeout=1_500;readTimeout=3_000;doOutput=true;instanceFollowRedirects=true;setRequestProperty("Content-Type","application/json; charset=utf-8");setRequestProperty("Accept","application/json");setRequestProperty("User-Agent","PickPack1291-M2Runtime/${BuildConfig.VERSION_NAME}");if(!bearer.isNullOrBlank())setRequestProperty("Authorization","Bearer $bearer")};conn.outputStream.use{it.write(payload.toString().toByteArray(Charsets.UTF_8))};val code=conn.responseCode;val stream=if(code in 200..299)conn.inputStream else conn.errorStream;val text=stream?.bufferedReader(Charsets.UTF_8)?.use{it.readText()}.orEmpty();val j=if(text.isBlank())JSONObject() else JSONObject(text);val ok=code in 200..299&&j.optBoolean("ok",false);val err=j.optJSONObject("error")?.optString("code")?.takeIf{it.isNotBlank()}?:j.optString("error","HTTP_$code");HttpResult(ok,code,j,if(ok)null else err)}catch(t:Throwable){HttpResult(false,-1,null,t.message?:"NETWORK")}finally{conn?.disconnect()}}
    private fun validServiceUrl(raw:String)=runCatching{val u=URL(raw);u.protocol=="https"&&u.host.isNotBlank()&&(u.host.endsWith(".workers.dev")||u.host.endsWith(".pages.dev"))}.getOrDefault(false)
    companion object{private const val PREFS="pp_m2_service_transport";private const val KEY_SERVICE_TOKEN="service_token";private const val KEY_AUTHORITY_MODE="runtime_authority_mode";private const val KEY_SERVICE_URL="runtime_service_url";private const val KEY_LAST_ROUTE="runtime_last_route";private const val KEY_LAST_ERROR="runtime_last_error";val DIRECT_READS=setOf("employee_context","master_options","history_shared")}
}
'''
RUNTIME.write_text(runtime, encoding='utf-8')

bg = BG.read_text(encoding='utf-8').replace('refreshMasterIfChanged(app, transport.discoverySnapshot())','refreshMasterIfChanged(app, transport.cachedDiscoverySnapshot())')
BG.write_text(bg, encoding='utf-8')

fg = FG.read_text(encoding='utf-8')
if 'val syncE2eMs: Long? = null' not in fg: fg=fg.replace('        val latencyMs: Long? = null,\n','        val latencyMs: Long? = null,\n        val syncE2eMs: Long? = null,\n',1)
fg=fg.replace('            val latencyMs = (SystemClock.elapsedRealtime() - startedAt).coerceAtLeast(0L)\n','            val syncE2eMs = (SystemClock.elapsedRealtime() - startedAt).coerceAtLeast(0L)\n            val serviceRttMs = result.json?.optLong("_service_rtt_ms", -1L)?.takeIf { it >= 0L }\n',1)
fg=fg.replace('                                latencyMs = latencyMs,\n','                                latencyMs = serviceRttMs,\n                                syncE2eMs = syncE2eMs,\n',1)
fg=fg.replace('                            latencyMs = latencyMs,\n                            error = result.error ?: "SYNC_FAILED",\n','                            latencyMs = serviceRttMs,\n                            syncE2eMs = syncE2eMs,\n                            error = result.error ?: "SYNC_FAILED",\n',1)
FG.write_text(fg, encoding='utf-8')

net=NET.read_text(encoding='utf-8').replace('return if (ms != null) "$transport • ${ms}ms" else transport','return if (ms != null) "$transport • Service ${ms}ms" else transport')
NET.write_text(net, encoding='utf-8')

api=API.read_text(encoding='utf-8')
if MARK not in api:
    anchor='    private val executor = Executors.newSingleThreadExecutor()\n'
    if anchor not in api: raise SystemExit('S31 API executor anchor missing')
    api=api.replace(anchor,anchor+'    private val localExecutor = Executors.newSingleThreadExecutor() // S31_SERVICE_FIRST_HOTPATH\n',1)
    sig='    fun call(action: String, payload: JSONObject = JSONObject(), callback: (Result) -> Unit) {\n        executor.execute {\n'
    if sig not in api: raise SystemExit('S31 API call signature anchor missing')
    fast='''    fun call(action: String, payload: JSONObject = JSONObject(), callback: (Result) -> Unit) {\n        if(action in M2ServiceTransport.OPERATIONAL){\n            localExecutor.execute {\n                try {\n                    val m2=m2Transport.operational(action,payload)\n                    val result=Result(m2.ok,m2.code,m2.json,m2.error)\n                    AppHistory.record(appContext,action,result.ok,result.error.orEmpty(),payload)\n                    callback(result)\n                } catch(t:Throwable){\n                    val result=failure(t)\n                    AppHistory.record(appContext,action,false,result.error.orEmpty(),payload)\n                    callback(result)\n                }\n            }\n            return\n        }\n        executor.execute {\n'''
    api=api.replace(sig,fast,1)
    old='''          action in M2ServiceTransport.OPERATIONAL -> {\n              m2Runtime.ensureServiceSession(gasSession)\n              m2Transport.operational(action, payload)\n          }\n'''
    if old in api: api=api.replace(old,'          action in M2ServiceTransport.OPERATIONAL -> m2Transport.operational(action, payload)\n',1)
    API.write_text(api,encoding='utf-8')

ops=OPS.read_text(encoding='utf-8')
if MARK not in ops:
    cls='class OperationsActivity : Activity() {\n'
    if cls not in ops: raise SystemExit('S31 Operations class anchor missing')
    ops=ops.replace(cls,cls+'    // S31_SERVICE_FIRST_HOTPATH\n',1)
    if '    private var lastLatencyMs: Long? = null\n' in ops and 'lastSyncE2eMs' not in ops: ops=ops.replace('    private var lastLatencyMs: Long? = null\n','    private var lastLatencyMs: Long? = null\n    private var lastSyncE2eMs: Long? = null\n',1)
    if '                lastLatencyMs = status.latencyMs\n' in ops: ops=ops.replace('                lastLatencyMs = status.latencyMs\n','                lastLatencyMs = status.latencyMs\n                lastSyncE2eMs = status.syncE2eMs\n',1)
    diag='''                    "Mạng" to net.header(lastLatencyMs),\n                    "Internet xác thực" to if(net.validated)"Có" else if(net.hasInternet)"Đang xác nhận" else "Không",\n'''
    if diag in ops: ops=ops.replace(diag,'''                    "Mạng" to net.header(null),\n                    "Service RTT" to (lastLatencyMs?.let{"${it}ms"}?:"Chưa đo"),\n                    "Sync E2E" to (lastSyncE2eMs?.let{"${it}ms"}?:"Chưa đo"),\n                    "Internet xác thực" to if(net.validated)"Có" else if(net.hasInternet)"Đang xác nhận" else "Không",\n''',1)
    OPS.write_text(ops,encoding='utf-8')

api2=API.read_text(encoding='utf-8');runtime2=RUNTIME.read_text(encoding='utf-8');transport2=TRANSPORT.read_text(encoding='utf-8')
if 'SERVICE_D1_VIA_GAS' in runtime2: raise SystemExit('S31 forbidden SERVICE_D1_VIA_GAS survived')
if 'val discovery = discover()' in transport2.split('fun operational',1)[1].split('fun acknowledgeFallback',1)[0]: raise SystemExit('S31 operational still performs discovery')
if 'm2Runtime.ensureServiceSession(gasSession)\n              m2Transport.operational' in api2: raise SystemExit('S31 operational still blocks on Service session')
print('Applied S31 strict Service-first non-blocking PDA hot path + background-only authority fallback + RTT split')
