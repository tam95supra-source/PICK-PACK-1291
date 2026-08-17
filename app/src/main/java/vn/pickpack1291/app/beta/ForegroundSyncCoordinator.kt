package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Handler
import android.os.Looper
import org.json.JSONObject

/**
 * Foreground-only server sequence watcher.
 *
 * Contract:
 * - starts with an immediate sync when an Activity enters foreground;
 * - never overlaps requests;
 * - backs off while idle to reduce bandwidth;
 * - when the app leaves foreground during a request, enters DRAINING, lets that
 *   request finish, persists the cursor, then becomes SUSPENDED;
 * - never starts a new request while DRAINING/SUSPENDED.
 *
 * server_seq is only a change detector. Callers still reload authoritative state
 * through the existing business endpoints instead of trusting cached deltas.
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
        val error: String? = null,
    )

    interface Listener {
        fun onStatus(status: Status)
        fun onAuthExpired()
    }

    private val main = Handler(Looper.getMainLooper())
    private val prefs = context.applicationContext.getSharedPreferences("foreground_sync", Context.MODE_PRIVATE)
    private val cursorKey = "server_seq_${BuildConfig.CHANNEL}"
    private var state = State.SUSPENDED
    private var inFlight = false
    private var idlePolls = 0
    private var lastSeq = prefs.getLong(cursorKey, 0L)
    private var generation = 0L

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
        state = if (inFlight) State.DRAINING else State.SUSPENDED
    }

    private fun poll() {
        if (state != State.ACTIVE || inFlight || api.token == null) return
        inFlight = true
        val requestGeneration = generation
        api.call("sync_status", JSONObject()) { result ->
            main.post {
                inFlight = false

                if (result.code == 401) {
                    state = State.SUSPENDED
                    main.removeCallbacks(tick)
                    listener.onAuthExpired()
                    return@post
                }

                val body = result.json
                if (result.ok && body != null) {
                    val seq = body.optLong("server_seq", lastSeq)
                    val changed = seq != lastSeq
                    if (changed) {
                        lastSeq = seq
                        prefs.edit().putLong(cursorKey, seq).apply()
                        idlePolls = 0
                    } else {
                        idlePolls = (idlePolls + 1).coerceAtMost(1000)
                    }

                    // A response that began while ACTIVE is allowed to finish during DRAINING,
                    // but UI callbacks/rescheduling are foreground-only.
                    if (state == State.ACTIVE && requestGeneration == generation) {
                        listener.onStatus(
                            Status(
                                state = State.ACTIVE,
                                connected = true,
                                serverSeq = seq,
                                projectionPending = body.optInt("projection_pending", 0),
                                changed = changed,
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
                            error = result.error ?: "SYNC_FAILED",
                        )
                    )
                }

                if (state == State.DRAINING || requestGeneration != generation) {
                    state = State.SUSPENDED
                    return@post
                }

                if (state == State.ACTIVE) {
                    main.postDelayed(tick, nextDelay(result.ok))
                }
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
