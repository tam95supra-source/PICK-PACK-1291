from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "app/src/main/java/vn/pickpack1291/app/beta"

coordinator = r'''package vn.pickpack1291.app.beta

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
'''
(PKG / "ForegroundSyncCoordinator.kt").write_text(coordinator, encoding="utf-8")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one anchor in {path}: {old[:80]!r}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


full = PKG / "FullBetaActivity.kt"
replace_once(
    full,
    '    private var syncText: TextView? = null\n',
    '''    private var syncText: TextView? = null
    private var liveEmployeeMnv = ""
    private val foregroundSync by lazy {
        ForegroundSyncCoordinator(this, api, object : ForegroundSyncCoordinator.Listener {
            override fun onStatus(status: ForegroundSyncCoordinator.Status) {
                if (status.connected) {
                    syncText?.text = "●  REALTIME • Seq ${status.serverSeq} • chờ Sheet ACK: ${status.projectionPending}"
                    syncText?.setTextColor(if (status.projectionPending == 0) green else orange)
                } else {
                    syncText?.text = "●  Mất kết nối realtime"
                    syncText?.setTextColor(red)
                }
                if (status.changed && liveEmployeeMnv.isNotBlank()) loadEmployee(liveEmployeeMnv)
            }

            override fun onAuthExpired() { sessionExpired() }
        })
    }
'''
)
replace_once(
    full,
    '''    override fun onStart() {
        super.onStart()
        UpdateManager.check(this)
    }
''',
    '''    override fun onStart() {
        super.onStart()
        UpdateManager.check(this)
        if (api.token != null) foregroundSync.start()
    }

    override fun onStop() {
        foregroundSync.stop()
        super.onStop()
    }
'''
)
replace_once(
    full,
    '''    private fun login() {
        api.clearToken()
''',
    '''    private fun login() {
        foregroundSync.stop()
        api.clearToken()
        liveEmployeeMnv = ""
'''
)
replace_once(
    full,
    '''                pass.setText("")
                dashboard()
''',
    '''                pass.setText("")
                dashboard()
                foregroundSync.start()
'''
)
replace_once(
    full,
    '''    private fun dashboard() {
        val root = column(bg)
''',
    '''    private fun dashboard() {
        liveEmployeeMnv = ""
        val root = column(bg)
'''
)
replace_once(
    full,
    '''    private fun employeeScan() {
        val root = column(bg); root.addView(appBar("QUÉT QR NHÂN SỰ", true))
''',
    '''    private fun employeeScan() {
        liveEmployeeMnv = ""
        val root = column(bg); root.addView(appBar("QUÉT QR NHÂN SỰ", true))
'''
)
replace_once(
    full,
    '''    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {
        val e=ctx.optJSONObject("employee") ?: JSONObject(); val state=ctx.optString("state"); val mnv=e.optString("mnv")
''',
    '''    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {
        val e=ctx.optJSONObject("employee") ?: JSONObject(); val state=ctx.optString("state"); val mnv=e.optString("mnv")
        liveEmployeeMnv = mnv
'''
)

ops = PKG / "OperationsActivity.kt"
replace_once(
    ops,
    '    private var initialMnv = ""\n',
    '''    private var initialMnv = ""
    private val foregroundSync by lazy {
        ForegroundSyncCoordinator(this, api, object : ForegroundSyncCoordinator.Listener {
            override fun onStatus(status: ForegroundSyncCoordinator.Status) {
                if (!status.connected || !status.changed) return
                // List/report screens are read-only and safe to refresh automatically.
                // Labor/resource editors intentionally keep the operator's in-progress input;
                // their writes are still revalidated atomically by the backend.
                when (module) {
                    "LISTS" -> listsScreen()
                    "REPORT" -> reportScreen()
                }
            }

            override fun onAuthExpired() { finish() }
        })
    }
'''
)
replace_once(
    ops,
    '    override fun onStart() { super.onStart(); UpdateManager.check(this) }\n',
    '''    override fun onStart() {
        super.onStart()
        UpdateManager.check(this)
        if (api.token != null) foregroundSync.start()
    }

    override fun onStop() {
        foregroundSync.stop()
        super.onStop()
    }
'''
)

print("S02 realtime patch applied")
