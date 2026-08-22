package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Build
import android.provider.Settings
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Mac
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec
import java.util.concurrent.Executors
import java.util.UUID

/**
 * Pick Pack transport for the approved architecture:
 * Android App <-> Google Apps Script <-> Google Sheets.
 *
 * Google Apps Script is the only API endpoint used by this transport.
 * Password plaintext never leaves the Android process: authentication uses PBKDF2 + challenge/HMAC proof.
 */
class BetaApiClient(context: Context) {
    // S31A_NORMALIZED_API_CALL_ANCHOR
    data class Result(val ok: Boolean, val code: Int, val json: JSONObject?, val error: String?)

    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val executor = Executors.newSingleThreadExecutor()
    private val authExecutor = Executors.newSingleThreadExecutor() // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY
    private val localExecutor = Executors.newSingleThreadExecutor() // S31_SERVICE_FIRST_HOTPATH
    private val adminAuditTransport by lazy { M2ServiceTransport(appContext) } // S30_CANONICAL_ADMIN_AUDIT
    // M2_SERVICE_TRANSPORT_APPLIED: dynamic Service primary + GAS fallback.
    private val m2Transport = M2ServiceTransport(appContext)
    // S19_M2_RUNTIME_FIX_APPLIED: honest runtime route + inherited-session exchange.
    private val m2Runtime = M2RuntimeBridge(appContext)
    private val deviceId: String by lazy {
        val androidId = Settings.Secure.getString(appContext.contentResolver, Settings.Secure.ANDROID_ID).orEmpty()
        if (androidId.isNotBlank() && androidId != "9774d56d682e549c") {
            "android-" + sha256Text("PickPack1291|$androidId")
        } else {
            val saved = prefs.getString(KEY_DEVICE_ID, null)
            val id = saved ?: UUID.randomUUID().toString().also { prefs.edit().putString(KEY_DEVICE_ID, it).apply() }
            "install-$id"
        }
    }

    init {
        synchronized(sessionLock) {
            if (sharedToken == null) sharedToken = prefs.getString(KEY_TOKEN, null)
        }
        M2ConnectivityMonitor.start(appContext)
        M2WorkScheduler.schedule(appContext)
    }

    val token: String?
        get() = sharedToken

    fun clearToken() = clearSession()

    fun clearSession() {
        // S24_FCM_LOGOUT_REVOKE_APPLIED: capture current Service session before clearing auth.
        M2PushRegistration.revoke(appContext)
        synchronized(sessionLock) { sharedToken = null }
        prefs.edit().remove(KEY_TOKEN).remove(KEY_LOGIN).remove(KEY_NAME).remove(KEY_ROLE).remove(KEY_POSITION).remove(KEY_EMAIL).apply()
        m2Runtime.clear()
    }

    fun runtimeStatus(): JSONObject = m2Runtime.status()

    fun restoredAccount(): JSONObject? {
        if (token.isNullOrBlank()) return null
        val login = prefs.getString(KEY_LOGIN, "").orEmpty()
        if (login.isBlank()) return null
        return JSONObject().apply {
            put("login_id", login)
            put("display_name", prefs.getString(KEY_NAME, login).orEmpty().ifBlank { login })
            put("role", prefs.getString(KEY_ROLE, "USER").orEmpty().ifBlank { "USER" })
            put("position", prefs.getString(KEY_POSITION, "").orEmpty())
            put("email", prefs.getString(KEY_EMAIL, "").orEmpty())
        }
    }

    private fun persistSession(newToken: String, account: JSONObject?) {
        synchronized(sessionLock) { sharedToken = newToken }
        val e = prefs.edit().putString(KEY_TOKEN, newToken)
        if (account != null) {
            val login = account.optString("login_id")
            if (login.isNotBlank()) e.putString(KEY_LOGIN, login)
            e.putString(KEY_NAME, account.optString("display_name", login))
            e.putString(KEY_ROLE, account.optString("role", "USER"))
            e.putString(KEY_POSITION, account.optString("position", ""))
            e.putString(KEY_EMAIL, account.optString("email", ""))
        }
        e.apply()
    }

    private fun sha256Text(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8)).joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') }

    fun login(loginId: String, password: String, callback: (Result) -> Unit) {
        authExecutor.execute {
            try {
                val login = loginId.trim()
                val challenge = post(JSONObject().apply {
                    put("action", "login_challenge")
                    put("login_id", login)
                }, authenticated = false)
                if (!challenge.ok) { callback(challenge); return@execute }

                val j = challenge.json ?: throw IllegalStateException("LOGIN_CHALLENGE_EMPTY")
                val algorithm = j.optString("algorithm", "pbkdf2_sha256")
                val proof = proofForPassword(
                    password = password,
                    saltB64 = j.getString("salt"),
                    iterations = j.optInt("iterations", 120_000),
                    challenge = j.getString("challenge"),
                    algorithm = algorithm
                )
                val request = JSONObject().apply {
                    put("action", "login")
                    put("login_id", login)
                    put("challenge_id", j.getString("challenge_id"))
                    put("proof", proof)
                    if (algorithm == "reset_sha256") put("upgrade_verifier", makeVerifier(password))
                }
                val result = post(request, authenticated = false)
                if (result.ok) {
                    val newToken = result.json?.optString("token")?.takeIf { it.isNotBlank() }
                    if (newToken != null) persistSession(newToken, result.json.optJSONObject("account"))
                    m2Transport.loginFromPassword(login, password)
                }
                callback(result)
            } catch (t: Throwable) {
                callback(failure(t))
            }
        }
    }

    fun call(action: String, payload: JSONObject = JSONObject(), callback: (Result) -> Unit) {
        if(action in M2ServiceTransport.OPERATIONAL){
            localExecutor.execute {
                try {      if (action in setOf("resource_master_list","resource_master_upsert","resource_master_delete","history_correction","session_work_update","session_exit_guarded","attendance_time_correct","attendance_exit_delete","service_connections","account_delete","history_delete")) {
          val result=serviceOwnerCall(action,payload)
          if(result.code==401) clearSession()
          if(action in setOf("resource_master_upsert","resource_master_delete","history_correction")) AppHistory.record(appContext,action,result.ok,result.error.orEmpty())
          callback(result)
          return@execute
      }

                    val m2=m2Transport.operational(action,payload)
                    val result=Result(m2.ok,m2.code,m2.json,m2.error)
                    AppHistory.record(appContext,action,result.ok,result.error.orEmpty(),payload)
                    callback(result)
                } catch(t:Throwable){
                    val result=failure(t)
                    AppHistory.record(appContext,action,false,result.error.orEmpty(),payload)
                    callback(result)
                }
            }
            return
        }
        executor.execute {
        val trackUpload = SyncDirectionTracker.isUploadAction(action)
        if (trackUpload) SyncDirectionTracker.beginUpload()

            try {
                val gasSession = token
      var m2: M2ServiceTransport.TransportResult? = when {
          action in M2RuntimeBridge.DIRECT_READS -> m2Runtime.directRead(action, payload, gasSession)
          action in M2ServiceTransport.OPERATIONAL -> m2Transport.operational(action, payload)
          action in M2ServiceTransport.SYNC_ACTIONS -> {
              m2Runtime.ensureServiceSession(gasSession)
              m2Transport.sync(action, payload)
          }
          else -> null
      }
      if (m2?.handled == true && m2?.code == 401 && !gasSession.isNullOrBlank()) {
          m2 = when {
              action in M2RuntimeBridge.DIRECT_READS -> m2Runtime.directRead(action, payload, gasSession)
              action in M2ServiceTransport.OPERATIONAL -> m2Runtime.recoverAndRetryOperational(action, payload, gasSession)
              action in M2ServiceTransport.SYNC_ACTIONS -> m2Runtime.recoverAndRetrySync(action, payload, gasSession)
              else -> m2
          }
      }
      val usedService = m2?.handled == true
      val runtimeDataAction = action in M2RuntimeBridge.DIRECT_READS || action in M2ServiceTransport.OPERATIONAL || action in M2ServiceTransport.SYNC_ACTIONS
      val result = if (usedService) {
          Result(m2!!.ok, m2.code, m2.json, m2.error)
      } else if(runtimeDataAction && ServiceFaultInjection.googleDisabled(appContext)) {
          Result(false,-1,null,"TEST_GOOGLE_DISABLED")
      } else when (action) {
          "change_password" -> changePassword(payload)
          "account_upsert" -> accountUpsert(payload)
          else -> post(JSONObject(payload.toString()).apply { put("action", action) }, authenticated = true)
      }
      if (!usedService && action in M2ServiceTransport.OPERATIONAL) m2Transport.acknowledgeFallback(payload.optString("event_id"), result.ok, result.error)
      if (usedService && result.ok && result.code != 202) m2Runtime.recordDirect()
      else if (!usedService && (action in M2RuntimeBridge.DIRECT_READS || action in M2ServiceTransport.OPERATIONAL || action in M2ServiceTransport.SYNC_ACTIONS)) m2Runtime.recordFallback(m2?.error)
      if (result.ok) {
                    val refreshed = result.json?.optString("token")?.takeIf { it.isNotBlank() }
                    if (refreshed != null) persistSession(refreshed, result.json.optJSONObject("account") ?: restoredAccount())
                }
                if (result.ok && action in M2ServiceTransport.ADMIN_AUDIT_ACTIONS) adminAuditTransport.audit(action,payload)
      if (result.code == 401) clearSession()
                // S13 shared history is server-authoritative; no local mutation history.
                callback(result)
            } catch (t: Throwable) {
                val result=failure(t)
                // Failed requests do not create shared business history.
                callback(result)
            } finally {
                if (trackUpload) SyncDirectionTracker.endUpload()
            }
        }
    }

    fun health(callback: (Result) -> Unit) {
        executor.execute {
            try { callback(post(JSONObject().put("action", "health"), authenticated = false)) }
            catch (t: Throwable) { callback(failure(t)) }
        }
    }

    fun forgotPassword(loginId: String, callback: (Result) -> Unit) {
        executor.execute {
            try {
                callback(post(JSONObject().apply {
                    put("action", "forgot_password")
                    put("login_id", loginId.trim())
                }, authenticated = false))
            } catch (t: Throwable) { callback(failure(t)) }
        }
    }

    /** OTA metadata comes from Apps Script, which reads the channel-specific Google Drive release folder. */
    fun updateCheck(channel: String, currentVersion: String, callback: (Result) -> Unit) {
        executor.execute {
            try {
                callback(post(JSONObject().apply {
                    put("action", "update_check")
                    put("channel", channel)
                    put("current_version", currentVersion)
                }, authenticated = false))
            } catch (t: Throwable) { callback(failure(t)) }
        }
    }

    private fun changePassword(payload: JSONObject): Result {
        val current = payload.optString("current_password")
        val next = payload.optString("new_password")
        if (next.length !in 8..128) return Result(false, 400, JSONObject().put("ok", false).put("error", "PASSWORD_POLICY"), "PASSWORD_POLICY")

        val challenge = post(JSONObject().put("action", "password_challenge"), authenticated = true)
        if (!challenge.ok) return challenge
        val j = challenge.json ?: throw IllegalStateException("PASSWORD_CHALLENGE_EMPTY")
        val proof = proofForPassword(current, j.getString("salt"), j.getInt("iterations"), j.getString("challenge"))
        val verifier = makeVerifier(next)
        return post(JSONObject().apply {
            put("action", "change_password")
            put("challenge_id", j.getString("challenge_id"))
            put("proof", proof)
            put("new_verifier", verifier)
        }, authenticated = true)
    }

    // S33_OWNER_UI_SYNC_RESOURCES: owner resource/correction calls go to current Service authority only.
    private fun serviceOwnerCall(action:String,payload:JSONObject):Result{
        if(ServiceFaultInjection.cloudflareDisabled(appContext))return Result(false,-1,null,"TEST_CLOUDFLARE_DISABLED")
        val d=m2Transport.discoverySnapshot()?:return Result(false,503,null,"SERVICE_DISCOVERY_UNAVAILABLE")
        if(d.optString("authority_mode")!="SERVICE_PRIMARY")return Result(false,409,d,"SERVICE_NOT_WRITE_AUTHORITY")
        val base=d.optString("service_url").trimEnd('/');if(!base.startsWith("https://"))return Result(false,503,d,"SERVICE_URL_INVALID")
        val bearer=appContext.getSharedPreferences("pp_m2_service_transport",Context.MODE_PRIVATE).getString("service_token",null).orEmpty();if(bearer.isBlank())return Result(false,401,null,"UNAUTHORIZED")
        val path=when(action){"history_correction"->"/v1/corrections";"session_work_update"->"/v1/session/work";"session_exit_guarded"->"/v1/session/exit";"attendance_time_correct"->"/v1/session/time-correction";"attendance_exit_delete"->"/v1/session/delete-exit";"service_connections"->"/v1/service/connections";"account_delete"->"/v1/admin/accounts/delete";"history_delete"->"/v1/history/delete";else->"/v1/admin/resources"};val method=if(action in setOf("resource_master_list","service_connections"))"GET" else "POST";val body=JSONObject(payload.toString());if(action=="resource_master_upsert")body.put("operation","UPSERT");if(action=="resource_master_delete")body.put("operation","DELETE")
        var conn:HttpURLConnection?=null;return try{conn=(URL(base+path).openConnection() as HttpURLConnection).apply{requestMethod=method;connectTimeout=6_000;readTimeout=12_000;setRequestProperty("Accept","application/json");setRequestProperty("Authorization","Bearer $bearer");if(method=="POST"){doOutput=true;setRequestProperty("Content-Type","application/json; charset=utf-8")}};if(method=="POST")conn!!.outputStream.use{it.write(body.toString().toByteArray(Charsets.UTF_8))};val http=conn!!.responseCode;val stream=if(http in 200..299)conn!!.inputStream else conn!!.errorStream;val text=stream?.bufferedReader(Charsets.UTF_8)?.use{it.readText()}.orEmpty();val j=if(text.isBlank())JSONObject() else JSONObject(text);val ok=http in 200..299&&j.optBoolean("ok",false);Result(ok,http,j,if(ok)null else (j.optJSONObject("error")?.optString("code")?.takeIf{it.isNotBlank()}?:j.optString("error","HTTP_$http")))}catch(t:Throwable){Result(false,-1,null,t.message?:"SERVICE_OWNER_CALL_FAILED")}finally{conn?.disconnect()}
    }

    private fun accountUpsert(payload: JSONObject): Result {
        val copy = JSONObject(payload.toString()).apply { put("action", "account_upsert") }
        val password = copy.optString("password")
        copy.remove("password")
        if (password.isNotEmpty()) {
            if (password.length !in 8..128) return Result(false, 400, JSONObject().put("ok", false).put("error", "PASSWORD_POLICY"), "PASSWORD_POLICY")
            copy.put("password_verifier", makeVerifier(password))
        }
        return post(copy, authenticated = true)
    }

    private fun post(payload: JSONObject, authenticated: Boolean): Result {
        val endpoint = BuildConfig.GSHEET_API_URL.trim()
        if (endpoint.isBlank() || !endpoint.startsWith("https://script.google.com/")) {
            return Result(false, -1, null, "GSHEET_API_NOT_CONFIGURED")
        }
        val body = JSONObject(payload.toString()).apply {
            put("_app_version", BuildConfig.VERSION_NAME)
            put("_app_channel", BuildConfig.CHANNEL)
            put("_device_id", deviceId)
            put("_device_label", "${Build.MANUFACTURER} ${Build.MODEL}")
            if (authenticated) {
                val t = sharedToken ?: return Result(false, 401, JSONObject().put("ok", false).put("error", "UNAUTHORIZED"), "UNAUTHORIZED")
                put("_token", t)
            }
        }
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 8_000
                readTimeout = 18_000
                doOutput = true
                instanceFollowRedirects = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
                setRequestProperty("User-Agent", "PickPack1291/${BuildConfig.VERSION_NAME}")
            }
            val requestBytes=body.toString().toByteArray(Charsets.UTF_8);SyncDirectionTracker.recordUploadBytes(requestBytes.size.toLong())
            conn.outputStream.use { it.write(requestBytes) }
            val http = conn.responseCode
            val stream = if (http in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            SyncDirectionTracker.recordDownloadBytes(text.toByteArray(Charsets.UTF_8).size.toLong())
            val json = if (text.isBlank()) JSONObject() else JSONObject(text)
            val ok = http in 200..299 && json.optBoolean("ok", false)
            val error = if (ok) null else json.optString("error", "HTTP_$http")
            val logicalCode = when (error) {
                "UNAUTHORIZED", "INVALID_CREDENTIALS", "CURRENT_PASSWORD_INVALID" -> 401
                "FORBIDDEN" -> 403
                "EMPLOYEE_NOT_FOUND" -> 404
                "LOGIN_TEMP_LOCKED" -> 429
                else -> if (http in 200..299 && !ok) 400 else http
            }
            Result(ok, logicalCode, json, error)
        } finally {
            conn?.disconnect()
        }
    }

    private fun githubUpdate(channelRaw: String, current: String): Result {
        val channel = if (channelRaw.equals("STABLE", true)) "STABLE" else "BETA"
        val releases = getJsonArray(RELEASES_URL)
        var picked: JSONObject? = null
        var asset: JSONObject? = null
        for (i in 0 until releases.length()) {
            val r = releases.optJSONObject(i) ?: continue
            if (r.optBoolean("draft", false)) continue
            if (channel == "BETA" && !r.optBoolean("prerelease", false)) continue
            if (channel == "STABLE" && r.optBoolean("prerelease", false)) continue
            val assets = r.optJSONArray("assets") ?: JSONArray()
            for (a in 0 until assets.length()) {
                val candidate = assets.optJSONObject(a) ?: continue
                val name = candidate.optString("name").lowercase()
                if (!name.endsWith(".apk")) continue
                if (channel == "BETA" && !name.contains("beta")) continue
                if (channel == "STABLE" && !name.contains("stable")) continue
                picked = r; asset = candidate; break
            }
            if (picked != null) break
        }
        if (picked == null || asset == null) {
            val j = JSONObject().put("ok", true).put("channel", channel).put("available", false).put("reason", "NO_RELEASE")
            return Result(true, 200, j, null)
        }
        val tag = picked.optString("tag_name")
        val version = tag.removePrefix("v").replace(Regex("-publicbeta$", RegexOption.IGNORE_CASE), "")
        var sha = asset.optString("digest").removePrefix("sha256:")
        if (sha.isBlank()) {
            val assets = picked.optJSONArray("assets") ?: JSONArray()
            for (i in 0 until assets.length()) {
                val sums = assets.optJSONObject(i) ?: continue
                if (!sums.optString("name").uppercase().contains("SHA256")) continue
                val text = getText(sums.optString("browser_download_url"))
                sha = text.lineSequence().firstOrNull { it.contains(asset.optString("name")) }?.trim()?.split(Regex("\\s+"))?.firstOrNull().orEmpty()
                if (sha.isNotBlank()) break
            }
        }
        val j = JSONObject().apply {
            put("ok", true); put("channel", channel); put("available", isNewer(version, current))
            put("version_name", version); put("tag", tag); put("apk_url", asset.optString("browser_download_url"))
            put("sha256", sha); put("size", asset.optLong("size")); put("mandatory", Regex("\\[mandatory]", RegexOption.IGNORE_CASE).containsMatchIn(picked.optString("body")))
            put("notes", picked.optString("body").take(1800)); put("published_at", picked.optString("published_at"))
        }
        return Result(true, 200, j, null)
    }

    private fun getJsonArray(url: String): JSONArray = JSONArray(getText(url, "application/vnd.github+json"))

    private fun getText(url: String, accept: String = "text/plain"): String {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"; connectTimeout = 12_000; readTimeout = 20_000
                instanceFollowRedirects = true; setRequestProperty("Accept", accept); setRequestProperty("User-Agent", "PickPack1291-OTA/${BuildConfig.VERSION_NAME}")
            }
            val code = conn.responseCode
            if (code !in 200..299) throw IllegalStateException("HTTP_$code")
            conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally { conn?.disconnect() }
    }

    private fun isNewer(latest: String, current: String): Boolean {
        val a = Regex("\\d+").findAll(latest).map { it.value.toIntOrNull() ?: 0 }.take(5).toList()
        val b = Regex("\\d+").findAll(current).map { it.value.toIntOrNull() ?: 0 }.take(5).toList()
        for (i in 0 until maxOf(a.size, b.size)) {
            val av = a.getOrElse(i) { 0 }; val bv = b.getOrElse(i) { 0 }
            if (av != bv) return av > bv
        }
        return false
    }

    private fun proofForPassword(password: String, saltB64: String, iterations: Int, challenge: String, algorithm: String = "pbkdf2_sha256"): String {
        val key = if (algorithm == "reset_sha256") {
            MessageDigest.getInstance("SHA-256").digest("PP_RESET_V1|$saltB64|$password".toByteArray(Charsets.UTF_8))
        } else {
            derive(password, b64uDecode(saltB64), iterations)
        }
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return b64u(mac.doFinal(challenge.toByteArray(Charsets.UTF_8)))
    }

    private fun makeVerifier(password: String): String {
        val salt = ByteArray(16).also { SecureRandom().nextBytes(it) }
        val iterations = 120_000
        val key = derive(password, salt, iterations)
        return "pbkdf2_sha256\$$iterations\$${b64u(salt)}\$${b64u(key)}"
    }

    private fun derive(password: String, salt: ByteArray, iterations: Int): ByteArray {
        require(iterations in 100_000..1_000_000) { "PBKDF2_ITERATIONS_INVALID" }
        val spec = PBEKeySpec(password.toCharArray(), salt, iterations, 256)
        return try { SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded }
        finally { spec.clearPassword() }
    }

    private fun b64u(bytes: ByteArray): String = Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
    private fun b64uDecode(value: String): ByteArray = Base64.decode(value, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
    private fun failure(t: Throwable) = Result(false, -1, null, t.message ?: t.javaClass.simpleName)

    companion object {
        @Volatile private var sharedToken: String? = null
        private val sessionLock = Any()
        private const val PREFS_NAME = "pick_pack_auth_session_v2"
        private const val KEY_TOKEN = "token"
        private const val KEY_LOGIN = "login_id"
        private const val KEY_NAME = "display_name"
        private const val KEY_ROLE = "role"
        private const val KEY_POSITION = "position"
        private const val KEY_EMAIL = "email"
        private const val KEY_DEVICE_ID = "device_id"
        private const val RELEASES_URL = "https://api.github.com/repos/tam95supra-source/pick-pack-1291/releases?per_page=30"
    }
}
