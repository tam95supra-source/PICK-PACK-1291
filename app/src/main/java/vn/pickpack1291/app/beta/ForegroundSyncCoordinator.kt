package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import org.json.JSONObject

/**
 * Foreground Service/D1 revision watcher with WebSocket wakeups and polling fallback.
 *
 * Contract:
 * - starts with an immediate sync when an Activity enters foreground;
 * - never overlaps requests;
 * - foreground Service primary also opens a realtime ticket/WebSocket;
 * - any DELTA immediately wakes the manifest/day sync path;
 * - polling remains as reconnect/fallback protection;
 * - when app leaves foreground, WebSocket closes and any in-flight request drains safely.
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

    private val main = Handler(Looper.getMainLooper())
    private val prefs = context.applicationContext.getSharedPreferences("foreground_sync", Context.MODE_PRIVATE)
    private val cursorKey = "server_seq_${BuildConfig.CHANNEL}"
    private val masterCursorKey = "master_revision_${BuildConfig.CHANNEL}"
    private var state = State.SUSPENDED
    private var inFlight = false
    private var idlePolls = 0
    private var lastSeq = prefs.getLong(cursorKey, 0L)
    private var lastMasterRevision = prefs.getLong(masterCursorKey, 0L)
    private var generation = 0L
    private val realtime = M2RealtimeClient(context.applicationContext) {
        main.post {
            if (state == State.ACTIVE) {
                idlePolls = 0
                main.removeCallbacks(tick)
                if (!inFlight) main.post(tick)
            }
        }
    }

    private val tick = Runnable { poll() }

    fun start() {
        check(Looper.myLooper() == Looper.getMainLooper()) { "ForegroundSyncCoordinator.start must run on main thread" }
        if (api.token == null) return
        if (state == State.ACTIVE) return
        generation += 1
        state = State.ACTIVE
        idlePolls = 0
        main.removeCallbacks(tick)
        main.post(tick)
    }

    fun stop() {
        check(Looper.myLooper() == Looper.getMainLooper()) { "ForegroundSyncCoordinator.stop must run on main thread" }
        generation += 1
        main.removeCallbacks(tick)
        realtime.stop()
        state = if (inFlight) State.DRAINING else State.SUSPENDED
    }

    private fun poll() {
        if (state != State.ACTIVE || inFlight || api.token == null) return
        inFlight = true
        val requestGeneration = generation
        val startedAt = SystemClock.elapsedRealtime()
        api.call("sync_status", JSONObject()) { result ->
            val latencyMs = (SystemClock.elapsedRealtime() - startedAt).coerceAtLeast(0L)
            main.post {
                inFlight = false

                if (result.code == 401) {
                    state = State.SUSPENDED
                    realtime.stop()
                    main.removeCallbacks(tick)
                    listener.onAuthExpired()
                    return@post
                }

                val body = result.json
                if (result.ok && body != null) {
                    val seq = body.optLong("server_seq", lastSeq)
                    val changed = seq != lastSeq
                    val masterRevision = body.optLong("master_revision", lastMasterRevision)
                    val masterChanged = masterRevision != lastMasterRevision
                    if (changed) {
                        lastSeq = seq
                        prefs.edit().putLong(cursorKey, seq).apply()
                        idlePolls = 0
                    }
                    if (masterChanged) {
                        lastMasterRevision = masterRevision
                        prefs.edit().putLong(masterCursorKey, masterRevision).apply()
                        idlePolls = 0
                    } else if (!changed) {
                        idlePolls = (idlePolls + 1).coerceAtMost(1000)
                    }
                    val businessDate = body.optString("business_date")
                    if (businessDate.isNotBlank()) realtime.start(businessDate)

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
                                latencyMs = latencyMs,
                                businessDate = businessDate,
                                retentionFloor = body.optString("retention_floor"),
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
                            latencyMs = latencyMs,
                            error = result.error ?: "SYNC_FAILED",
                        )
                    )
                }

                if (state == State.DRAINING || requestGeneration != generation) {
                    realtime.stop()
                    state = State.SUSPENDED
                    return@post
                }

                if (state == State.ACTIVE) main.postDelayed(tick, nextDelay(result.ok))
            }
        }
    }

    private fun nextDelay(success: Boolean): Long {
        if (!success) return 5_000L
        return when {
            idlePolls <= 3 -> 1_500L
            idlePolls <= 12 -> 2_500L
            else -> 4_000L
        }
    }
}
