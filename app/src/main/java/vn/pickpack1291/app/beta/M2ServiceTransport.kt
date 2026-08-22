package vn.pickpack1291.app.beta

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
    // S54_BETA48_OWNER_10_FIXES
    // retryDateWindowRejects is handled by durable OperationalDataStore selection.
    data class TransportResult(val handled: Boolean, val ok: Boolean, val code: Int, val json: JSONObject?, val error: String?)
    private val app = context.applicationContext
    private val prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val store = OperationalDataStore(app)
    private val connectivity = app.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    fun loginFromPassword(loginId: String, password: String) {
        if (ServiceFaultInjection.cloudflareDisabled(app)) return
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
        val businessDate=store.businessDate() // S45_BETA40_OWNER_FIXES
        payload.put("event_id",eventId).put("business_date",businessDate)
        val request = JSONObject().put("action", action).put("event_id", eventId).put("business_date",businessDate).put("device_id", M2DeviceIdentity.id(app))
            .put("payload", JSONObject(payload.toString()).put("event_id",eventId).put("business_date",businessDate))
        val exclusive = action == "enter" || action == "resource_change"
        store.enqueueMutation(request, exclusive)
        M2WorkScheduler.schedule(app)
        M2ImmediateOutbox.kick(app)
        val mode = cachedDiscoverySnapshot()?.optString("authority_mode").orEmpty()
        val projection = when { !hasNetwork() -> "OFFLINE_LOCAL"; mode == "GOOGLE_FALLBACK" -> "GOOGLE_FALLBACK_PENDING"; else -> "SERVICE_D1_PENDING" }
        return queuedResult(eventId, exclusive, projection)
    }

    // S31B_PRESERVE_ADMIN_AUDIT / S30_CANONICAL_ADMIN_AUDIT: sanitized admin audit uses the same durable outbox.
    fun audit(action:String,payload:JSONObject){
        if(action !in ADMIN_AUDIT_ACTIONS)return
        val eventId=java.util.UUID.randomUUID().toString()
        val targetId=when(action){
            "staff_upsert","staff_delete"->payload.optString("mnv")
            "account_upsert","account_status","change_email","change_password"->payload.optString("login_id").ifBlank{payload.optString("target_login_id")}
            else->""
        }
        val targetLabel=payload.optString("full_name").ifBlank{payload.optString("display_name")}.take(180)
        val detail=when(action){
            "staff_upsert"->"Thêm / cập nhật hồ sơ nhân sự"
            "staff_delete"->"Xóa hồ sơ nhân sự"
            "account_upsert"->"Tạo / cập nhật tài khoản"
            "account_status"->"Thay đổi trạng thái tài khoản"
            "change_email"->"Thay đổi email tài khoản"
            "change_password"->"Thay đổi mật khẩu"
            else->"Thao tác quản trị"
        }
        val body=JSONObject()
            .put("action","admin_audit")
            .put("event_id",eventId)
            .put("target_type",if(action.startsWith("staff_"))"STAFF" else "ACCOUNT")
            .put("target_id",targetId.take(180))
            .put("target_label",targetLabel)
            .put("result","OK")
            .put("detail",detail)
            .put("device_id",M2DeviceIdentity.id(app))
            .put("occurred_at",java.time.Instant.now().toString())
        store.enqueueMutation(body,false)
        M2WorkScheduler.schedule(app)
        M2ImmediateOutbox.kick(app)
    }

    fun acknowledgeFallback(eventId: String, ok: Boolean, error: String?) {
        if (eventId.isBlank()) return
        if (ok) store.markMutationSynced(eventId) else if (!error.isNullOrBlank()) store.markMutationRetry(eventId, error, 5_000L)
    }

    /** Direct Service read using cached discovery only. A Service failure is handled, never a GAS fall-through. */
    fun sync(action: String, payload: JSONObject): TransportResult {
        if (action !in SYNC_ACTIONS) return TransportResult(false, false, 0, null, null)
        if (ServiceFaultInjection.cloudflareDisabled(app)) return TransportResult(true,false,-1,null,"TEST_CLOUDFLARE_DISABLED")
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
            val r = if(action=="service_connections") httpGetJson("$base/v1/service/connections",token) else httpJson("$base/v1/legacy-sync", request, token)
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
    /** S39_EMPLOYEE_SESSION_HISTORY: background-only Service session recovery; UI hot path stays SQLite-first. */
    // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY: every immediate/WorkManager trigger shares this lock.
    fun flushOutbox(): Boolean = synchronized(FLUSH_LOCK) {
        val count=runCatching{store.unresolvedMutations(100).size}.getOrDefault(0)
        M2TransportDiagnostics.notePumpStart(app,count)
        val result=runCatching{flushOutboxLocked()}.getOrElse{M2TransportDiagnostics.notePumpEnd(app,false,it.message?:it.javaClass.simpleName);false}
        M2TransportDiagnostics.notePumpEnd(app,result)
        result
    }

    private fun flushOutboxLocked(): Boolean {
        if (!hasNetwork()) return false
        if(ServiceFaultInjection.cloudflareDisabled(app)){
            // Fault injection simulates provider loss only. Do not bypass the authority fence or
            // manufacture a Google write authority while production still says SERVICE_PRIMARY.
            return false
        }
        var discovery=cachedDiscoverySnapshot();if(discovery==null)discovery=discover(force=true);if(discovery==null)return false
        if(discovery.optString("authority_mode")=="GOOGLE_FALLBACK")return flushFallbackItems(store.unresolvedMutations(100))
        if(discovery.optString("authority_mode")!="SERVICE_PRIMARY")return false
        val items=store.unresolvedMutations(100);if(items.isEmpty())return true
        if(circuitOpen()){
            if(failureCount()>=FALLBACK_PROBE_FAILURES&&fallbackProbeDue()){val confirmed=discover(force=true);noteFallbackProbe();if(confirmed?.optString("authority_mode")=="GOOGLE_FALLBACK")return flushFallbackItems(items)}
            return false
        }
        val base=discovery.optString("service_url").trimEnd('/');if(!validServiceUrl(base))return false
        var token=prefs.getString(KEY_SERVICE_TOKEN,null)
        if(token.isNullOrBlank()){token=exchangeBackgroundServiceSession(base);if(token.isNullOrBlank()){items.forEach{store.markMutationRetry(it.eventId,"SERVICE_SESSION_REAUTH_REQUIRED",retryDelay(it.attemptCount))};return false}}
        fun submit(bearer:String):HttpResult{val body=JSONObject().put("events",JSONArray().apply{items.forEach{put(it.body)}});val started=System.currentTimeMillis();return httpJson("$base/v1/legacy-mutations/batch",body,bearer).also{M2TransportDiagnostics.noteBatch(app,it.code,it.ok,it.error,items.size,System.currentTimeMillis()-started)}}
        return try{
            var r=submit(token)
            if(r.code==401){M2ServiceSessionManager.clearIfSame(app,token);val refreshed=exchangeBackgroundServiceSession(base);if(!refreshed.isNullOrBlank())r=submit(refreshed)}
            if(r.code==401){items.forEach{store.markMutationRetry(it.eventId,"SERVICE_SESSION_REAUTH_REQUIRED",retryDelay(it.attemptCount))};return false}
            if(!r.ok||r.json==null){if(r.code>=500||r.code==-1)recordFailure();if(failureCount()>=FALLBACK_PROBE_FAILURES&&fallbackProbeDue()){val confirmed=discover(force=true);noteFallbackProbe();if(confirmed?.optString("authority_mode")=="GOOGLE_FALLBACK")return flushFallbackItems(items)};items.forEach{store.markMutationRetry(it.eventId,r.error?:"HTTP_${r.code}",retryDelay(it.attemptCount))};return false}
            val results=r.json.optJSONArray("results")?:JSONArray();val byId=items.associateBy{it.eventId};var retryNeeded=false
            for(i in 0 until results.length()){val result=results.optJSONObject(i)?:continue;val eventId=result.optString("local_event_id");val item=byId[eventId]?:continue;val error=result.optString("error_code").ifBlank{result.optJSONObject("conflict")?.toString().orEmpty()};when(result.optString("status")){"CONFIRMED","DUPLICATE"->store.markMutationSynced(eventId);"REVIEW_REQUIRED"->store.markMutationReviewRequired(eventId,error);"REJECTED"->if(result.optBoolean("retryable",false)){store.markMutationRetry(eventId,error.ifBlank{"RETRYABLE_REJECT"},retryDelay(item.attemptCount));retryNeeded=true}else store.markMutationRejected(eventId,error);else->{store.markMutationRetry(eventId,"BATCH_RESULT_INVALID",retryDelay(item.attemptCount));retryNeeded=true}}}
            val returned=HashSet<String>().apply{for(i in 0 until results.length())add(results.optJSONObject(i)?.optString("local_event_id").orEmpty())};items.filter{it.eventId !in returned}.forEach{store.markMutationRetry(it.eventId,"BATCH_RESULT_MISSING",retryDelay(it.attemptCount));retryNeeded=true};if(!retryNeeded)closeCircuit();!retryNeeded
        }catch(x:Throwable){recordFailure();items.forEach{store.markMutationRetry(it.eventId,x.message?:"NETWORK",retryDelay(it.attemptCount))};false}
    }

    private fun exchangeBackgroundServiceSession(base:String):String? = M2ServiceSessionManager.ensure(app,base,force=true)

    fun cachedDiscoverySnapshot(): JSONObject? = prefs.getString(KEY_DISCOVERY_JSON, null)?.let { runCatching { JSONObject(it) }.getOrNull() }
    fun discoverySnapshot(): JSONObject? = cachedDiscoverySnapshot()

    private fun flushFallbackItems(items: List<OperationalDataStore.PendingMutation>): Boolean {
        if (ServiceFaultInjection.googleDisabled(app)) return false
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
        if(ServiceFaultInjection.googleDisabled(app)) return cachedDiscoverySnapshot()
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
        if(requireServiceHost && ServiceFaultInjection.cloudflareDisabled(app)) return HttpResult(false,-1,null,"TEST_CLOUDFLARE_DISABLED")
        if(!requireServiceHost && ServiceFaultInjection.googleDisabled(app)) return HttpResult(false,-1,null,"TEST_GOOGLE_DISABLED")
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

    private fun httpGetJson(endpoint:String,bearer:String?):HttpResult{
        if(ServiceFaultInjection.cloudflareDisabled(app))return HttpResult(false,-1,null,"TEST_CLOUDFLARE_DISABLED")
        if(!validServiceUrl(endpoint.substringBefore("/v1/")))return HttpResult(false,-1,null,"SERVICE_URL_INVALID")
        var conn:HttpURLConnection?=null
        return try{
            conn=(URL(endpoint).openConnection() as HttpURLConnection).apply{
                requestMethod="GET";connectTimeout=3_000;readTimeout=5_000;instanceFollowRedirects=true
                setRequestProperty("Accept","application/json");setRequestProperty("User-Agent","PickPack1291-M2/${BuildConfig.VERSION_NAME}")
                if(!bearer.isNullOrBlank())setRequestProperty("Authorization","Bearer $bearer")
            }
            val code=conn.responseCode;val stream=if(code in 200..299)conn.inputStream else conn.errorStream
            val text=stream?.bufferedReader(Charsets.UTF_8)?.use{it.readText()}.orEmpty();val j=if(text.isBlank())JSONObject() else JSONObject(text)
            val ok=code in 200..299&&j.optBoolean("ok",false);val errObj=j.optJSONObject("error")
            HttpResult(ok,code,j,if(ok)null else errObj?.optString("code")?.takeIf{it.isNotBlank()}?:j.optString("error","HTTP_$code"))
        }finally{conn?.disconnect()}
    }

    private fun validServiceUrl(raw: String): Boolean = runCatching { val u = URL(raw); u.protocol == "https" && u.host.isNotBlank() && (u.host.endsWith(".workers.dev") || u.host.endsWith(".pages.dev") || u.host == "localhost") }.getOrDefault(false)
    private fun proofForPassword(password: String, saltB64: String, iterations: Int, challenge: String): String { val key = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(PBEKeySpec(password.toCharArray(), b64uDecode(saltB64), iterations, 256)).encoded; val mac = Mac.getInstance("HmacSHA256"); mac.init(SecretKeySpec(key, "HmacSHA256")); return b64u(mac.doFinal(challenge.toByteArray(Charsets.UTF_8))) }
    private fun b64u(bytes: ByteArray): String = Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
    private fun b64uDecode(v: String): ByteArray = Base64.decode(v, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)

    companion object {
        private val FLUSH_LOCK=Any() // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY
        private const val PREFS = "pp_m2_service_transport"; private const val KEY_SERVICE_TOKEN = "service_token"; private const val KEY_DISCOVERY_JSON = "discovery_json"; private const val KEY_DISCOVERY_AT = "discovery_at"; private const val KEY_FAILURES = "service_failures"; private const val KEY_CIRCUIT_UNTIL = "circuit_until"; private const val KEY_LAST_FALLBACK_PROBE_AT = "fallback_probe_at"; private const val AUTH_PREFS = "pick_pack_auth_session_v2"; private const val AUTH_TOKEN = "token"; private const val DISCOVERY_TTL_MS = 10 * 60_000L; private const val CIRCUIT_MS = 15_000L; private const val FALLBACK_PROBE_FAILURES = 3; private const val FALLBACK_PROBE_MIN_MS = 30_000L; val ADMIN_AUDIT_ACTIONS = setOf("staff_upsert","staff_delete","account_upsert","account_status","change_email","change_password"); val OPERATIONAL = setOf("enter", "exit", "resource_change", "labor_start", "labor_finish"); val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap", "service_connections") }
}

object M2DeviceIdentity { fun id(context: Context): String { val p=context.getSharedPreferences("pp_m2_device",Context.MODE_PRIVATE);p.getString("id",null)?.let{return it}; val androidId=android.provider.Settings.Secure.getString(context.contentResolver,android.provider.Settings.Secure.ANDROID_ID).orEmpty(); val raw=if(androidId.isNotBlank()&&androidId!="9774d56d682e549c")"android-$androidId" else "install-${java.util.UUID.randomUUID()}"; val digest=MessageDigest.getInstance("SHA-256").digest("PickPack1291|$raw".toByteArray()).joinToString(""){(it.toInt()and 0xff).toString(16).padStart(2,'0')}; return "m2-$digest".also{p.edit().putString("id",it).apply()} } }
