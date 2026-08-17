package vn.pickpack1291.app.beta

import android.os.Build
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class BetaApiClient {
    data class Result(val ok: Boolean, val code: Int, val json: JSONObject?, val error: String?)

    private val executor = Executors.newSingleThreadExecutor()
    @Volatile var token: String? = null
        private set

    fun clearToken() { token = null }

    fun login(loginId: String, password: String, callback: (Result) -> Unit) {
        request(JSONObject().apply {
            put("action", "login")
            put("login_id", loginId)
            put("password", password)
        }, false) { result ->
            if (result.ok) token = result.json?.optString("token")?.takeIf { it.isNotBlank() }
            callback(result)
        }
    }

    fun call(action: String, payload: JSONObject = JSONObject(), callback: (Result) -> Unit) {
        payload.put("action", action)
        request(payload, true, callback)
    }

    fun health(callback: (Result) -> Unit) {
        request(JSONObject().put("action", "health"), false, callback)
    }

    private fun request(payload: JSONObject, authenticated: Boolean, callback: (Result) -> Unit) {
        executor.execute {
            var conn: HttpURLConnection? = null
            try {
                conn = (URL(API_URL).openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 12_000
                    readTimeout = 18_000
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("X-App-Version", "0.2.0-beta.1")
                    setRequestProperty("X-Device-Label", "${Build.MANUFACTURER} ${Build.MODEL}")
                    if (authenticated) {
                        val t = token ?: throw IllegalStateException("UNAUTHORIZED")
                        setRequestProperty("Authorization", "Bearer $t")
                    }
                }
                conn.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
                val body = if (text.isBlank()) JSONObject() else JSONObject(text)
                val ok = code in 200..299 && body.optBoolean("ok", false)
                callback(Result(ok, code, body, if (ok) null else body.optString("error", "HTTP_$code")))
            } catch (t: Throwable) {
                callback(Result(false, -1, null, t.message ?: t.javaClass.simpleName))
            } finally {
                conn?.disconnect()
            }
        }
    }

    companion object {
        private const val API_URL = "https://oedasgcdjppjwidhlqdr.supabase.co/functions/v1/pick-pack-beta-api"
    }
}
