package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Handler
import android.os.Looper
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.io.IOException
import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import kotlin.math.min

/**
 * Foreground-only Service realtime invalidation client.
 *
 * INVALIDATION_V1 is notification-only: DAY_CHANGED / MASTER_CHANGED wake the revision-driven
 * synchronizer. Correctness still comes from the Service delta/revision contract; this socket never
 * carries a full business dataset. Background durability remains WorkManager + FCM wake-up.
 */
class M2RealtimeClient(
    context: Context,
    private val scope: Scope = Scope.DAY,
    private val onInvalidation: (JSONObject) -> Unit,
) {
    enum class Scope { DAY, MASTER }

    private val app = context.applicationContext
    private val transport = M2ServiceTransport(app)
    private val prefs = app.getSharedPreferences("pp_m2_service_transport", Context.MODE_PRIVATE)
    private val handler = Handler(Looper.getMainLooper())
    private val client = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(20, TimeUnit.SECONDS)
        .build()

    @Volatile private var running = false
    @Volatile private var businessDate = ""
    @Volatile private var socket: WebSocket? = null
    @Volatile private var reconnectAttempt = 0
    @Volatile private var protocolReady = false

    fun start(date: String = "") {
        val d = date.trim()
        if (scope == Scope.DAY && d.isBlank()) return
        if (scope == Scope.DAY) businessDate = d
        if (running && socket != null) return
        running = true
        connect()
    }

    fun stop() {
        running = false
        protocolReady = false
        handler.removeCallbacksAndMessages(null)
        socket?.close(1000, "background")
        socket = null
        reconnectAttempt = 0
    }

    private fun connect() {
        if (!running || (scope == Scope.DAY && businessDate.isBlank())) return
        val discovery = transport.discoverySnapshot()
        if (discovery?.optString("authority_mode") != "SERVICE_PRIMARY") return scheduleReconnect()
        val base = discovery.optString("service_url").trimEnd('/')
        val token = prefs.getString("service_token", null)
        if (base.isBlank() || token.isNullOrBlank()) return scheduleReconnect()
        val query = if (scope == Scope.MASTER) "scope=master" else "business_date=${URLEncoder.encode(businessDate, "UTF-8")}" 
        val request = Request.Builder()
            .url("$base/v1/realtime/ticket?$query")
            .header("Authorization", "Bearer $token")
            .post("{}".toRequestBody("application/json; charset=utf-8".toMediaType()))
            .build()
        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) { scheduleReconnect() }
            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!it.isSuccessful) return scheduleReconnect()
                    val json = runCatching { JSONObject(it.body.string()) }.getOrNull() ?: return scheduleReconnect()
                    val ticket = json.optString("ticket")
                    if (ticket.isBlank()) return scheduleReconnect()
                    openWebSocket(base, ticket)
                }
            }
        })
    }

    private fun openWebSocket(base: String, ticket: String) {
        if (!running) return
        val wsBase = if (base.startsWith("https://")) "wss://${base.removePrefix("https://")}" else return scheduleReconnect()
        val url = "$wsBase/v1/realtime?ticket=${URLEncoder.encode(ticket, "UTF-8")}" 
        protocolReady = false
        socket = client.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) { reconnectAttempt = 0 }
            override fun onMessage(webSocket: WebSocket, text: String) {
                val json = runCatching { JSONObject(text) }.getOrNull() ?: return
                when (json.optString("type")) {
                    "REALTIME_READY" -> {
                        if (json.optString("protocol") != "INVALIDATION_V1") {
                            protocolReady = false
                            webSocket.close(1002, "unsupported_protocol")
                        } else protocolReady = true
                    }
                    "DAY_CHANGED" -> if (protocolReady && scope == Scope.DAY && json.optString("business_date") == businessDate) onInvalidation(json)
                    "MASTER_CHANGED" -> if (protocolReady && scope == Scope.MASTER) onInvalidation(json)
                }
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(code, reason) }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { protocolReady = false; socket = null; scheduleReconnect() }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) { protocolReady = false; socket = null; scheduleReconnect() }
        })
    }

    private fun scheduleReconnect() {
        if (!running) return
        socket = null
        protocolReady = false
        reconnectAttempt++
        val delay = min(15_000L, 1_000L * (1L shl min(reconnectAttempt, 4)))
        handler.removeCallbacksAndMessages(null)
        handler.postDelayed({ connect() }, delay)
    }
}
