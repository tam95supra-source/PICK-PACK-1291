package vn.pickpack1291.app.beta

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import org.json.JSONObject

/**
 * Event-driven foreground Service/D1 revision synchronizer.
 *
 * Normal triggers are: foreground start, network reconnect, DAY_CHANGED / MASTER_CHANGED realtime
 * invalidations, pending outbox work and explicit/manual refresh. There is no periodic "anything
 * changed?" polling loop. A single bounded recovery retry is allowed after a failed foreground read.
 */
class ForegroundSyncCoordinator(
    context: Context,
    private val api: BetaApiClient,
    private val listener: Listener,
) {
    enum class State { ACTIVE, DRAINING, SUSPENDED }

    data class Status(
        val state: State,
        val connected: Boolean,
        val serverSeq: Long,
        val projectionPending: Int,
        val changed: Boolean,
        val masterRevision: Long,
        val masterChanged: Boolean,
        val latencyMs: Long? = null,
        val syncE2eMs: Long? = null,
        val error: String? = null,
        val businessDate: String = "",
        val retentionFloor: String = "",
        val retentionEpoch: Long = 0L,
        val dayRevisions: JSONObject = JSONObject(),
    )

    interface Listener {
        fun onStatus(status: Status)
        fun onAuthExpired()
    }

    private val app = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private val prefs = app.getSharedPreferences("foreground_sync", Context.MODE_PRIVATE)
    private val cursorKey = "server_seq_${BuildConfig.CHANNEL}"
    private val masterCursorKey = "master_revision_${BuildConfig.CHANNEL}"
    private val connectivity = app.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private var state = State.SUSPENDED
    private var inFlight = false
    private var wakePending = false
    private var lastSeq = prefs.getLong(cursorKey, 0L)
    private var lastMasterRevision = prefs.getLong(masterCursorKey, 0L)
    private var generation = 0L
    private var networkCallbackRegistered = false
    private var failureRetriesRemaining = 0

    private val dayRealtime = M2RealtimeClient(app, M2RealtimeClient.Scope.DAY) { invalidation ->
        main.post {
            if (state != State.ACTIVE) return@post
            val seq = invalidation.optLong("authority_seq", 0L)
            if (seq > lastSeq || invalidation.optLong("day_revision", 0L) > 0L) requestSync()
        }
    }
    private val masterRealtime = M2RealtimeClient(app, M2RealtimeClient.Scope.MASTER) { invalidation ->
        main.post {
            if (state != State.ACTIVE) return@post
            val revision = invalidation.optLong("revision", 0L)
            if (revision > 0L) requestSync()
        }
    }
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            main.post {
                if (state == State.ACTIVE) {
                    failureRetriesRemaining = 1
                    M2WorkScheduler.schedule(app)
                    M2PushRegistration.flush(app)
                    requestSync()
                }
            }
        }
    }

    fun start() {
        check(Looper.myLooper() == Looper.getMainLooper()) { "ForegroundSyncCoordinator.start must run on main thread" }
        if (api.token == null || state == State.ACTIVE) return
        generation += 1
        state = State.ACTIVE
        wakePending = false
        failureRetriesRemaining = 1
        registerNetworkCallback()
        requestSync()
    }

    fun stop() {
        check(Looper.myLooper() == Looper.getMainLooper()) { "ForegroundSyncCoordinator.stop must run on main thread" }
        generation += 1
        wakePending = false
        main.removeCallbacksAndMessages(null)
        dayRealtime.stop()
        masterRealtime.stop()
        unregisterNetworkCallback()
        state = if (inFlight) State.DRAINING else State.SUSPENDED
    }

    /** Explicit/manual/event wake. Coalesces concurrent invalidations into one follow-up read. */
    fun requestSync() {
        if (state != State.ACTIVE || api.token == null) return
        if (inFlight) { wakePending = true; return }
        syncOnce()
    }

    private fun syncOnce() {
        if (state != State.ACTIVE || inFlight || api.token == null) return
        inFlight = true
        val requestGeneration = generation
        val startedAt = SystemClock.elapsedRealtime()
        api.call("sync_status", JSONObject()) { result ->
            val syncE2eMs = (SystemClock.elapsedRealtime() - startedAt).coerceAtLeast(0L)
            val serviceRttMs = result.json?.optLong("_service_rtt_ms", -1L)?.takeIf { it >= 0L }
            main.post {
                inFlight = false

                if (result.code == 401) {
                    state = State.SUSPENDED
                    dayRealtime.stop()
                    masterRealtime.stop()
                    unregisterNetworkCallback()
                    listener.onAuthExpired()
                    return@post
                }

                val body = result.json
                if (result.ok && body != null) {
                    failureRetriesRemaining = 1
                    val seq = body.optLong("server_seq", lastSeq)
                    val changed = seq != lastSeq
                    val masterRevision = body.optLong("master_revision", lastMasterRevision)
                    val masterChanged = masterRevision != lastMasterRevision
                    if (changed) {
                        lastSeq = seq
                        prefs.edit().putLong(cursorKey, seq).apply()
                    }
                    if (masterChanged) {
                        lastMasterRevision = masterRevision
                        prefs.edit().putLong(masterCursorKey, masterRevision).apply()
                    }
                    val businessDate = body.optString("business_date")
                    if (businessDate.isNotBlank()) dayRealtime.start(businessDate)
                    masterRealtime.start()
                    M2WorkScheduler.schedule(app)
                    M2PushRegistration.flush(app)

                    if (state == State.ACTIVE && requestGeneration == generation) {
                        listener.onStatus(
                            Status(
                                state = State.ACTIVE,
                                connected = true,
                                serverSeq = seq,
                                projectionPending = body.optInt("projection_pending", 0),
                                changed = changed,
                                masterRevision = masterRevision,
                                masterChanged = masterChanged,
                                latencyMs = serviceRttMs,
                                syncE2eMs = syncE2eMs,
                                businessDate = businessDate,
                                // S25_FALLBACK_RETENTION_COMPAT: legacy GAS may blank retention_floor.
                                retentionFloor = body.optString("retention_floor").ifBlank { body.optString("server_retention_floor") },
                                retentionEpoch = body.optLong("retention_epoch", 0L),
                                dayRevisions = body.optJSONObject("day_revisions") ?: JSONObject(),
                            )
                        )
                    }
                } else if (state == State.ACTIVE && requestGeneration == generation) {
                    listener.onStatus(
                        Status(
                            state = State.ACTIVE,
                            connected = false,
                            serverSeq = lastSeq,
                            projectionPending = -1,
                            changed = false,
                            masterRevision = lastMasterRevision,
                            masterChanged = false,
                            latencyMs = serviceRttMs,
                            syncE2eMs = syncE2eMs,
                            error = result.error ?: "SYNC_FAILED",
                        )
                    )
                    if (failureRetriesRemaining > 0) {
                        failureRetriesRemaining -= 1
                        main.postDelayed({ requestSync() }, 10_000L)
                    }
                }

                if (state == State.DRAINING || requestGeneration != generation) {
                    dayRealtime.stop()
                    masterRealtime.stop()
                    unregisterNetworkCallback()
                    state = State.SUSPENDED
                    return@post
                }

                if (wakePending && state == State.ACTIVE) {
                    wakePending = false
                    main.post { requestSync() }
                }
            }
        }
    }

    private fun registerNetworkCallback() {
        if (networkCallbackRegistered) return
        runCatching { connectivity.registerDefaultNetworkCallback(networkCallback) }
            .onSuccess { networkCallbackRegistered = true }
    }

    private fun unregisterNetworkCallback() {
        if (!networkCallbackRegistered) return
        runCatching { connectivity.unregisterNetworkCallback(networkCallback) }
        networkCallbackRegistered = false
    }
}
