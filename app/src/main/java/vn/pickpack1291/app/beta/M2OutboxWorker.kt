package vn.pickpack1291.app.beta

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/** S32_LOCAL_HISTORY_FLUSH_FIX: mutation flush is independent from canonical catch-up. */
class M2OutboxFlushWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {
    override fun doWork(): Result {
        if (!PpForegroundGate.isForeground()) return Result.success()
        return try {
            if (M2ServiceTransport(applicationContext).flushOutbox()) Result.success() else Result.retry()
        } catch (_: Throwable) { Result.retry() }
    }
}

/** Snapshot/master reconciliation is useful but must never gate local mutation delivery. */
class M2CatchUpWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {
    override fun doWork(): Result {
        if (!PpForegroundGate.isForeground()) return Result.success()
        return try {
            val caughtUp = M2BackgroundSync.catchUp(applicationContext)
            M2PushRegistration.flush(applicationContext)
            if (caughtUp) Result.success() else Result.retry()
        } catch (_: Throwable) { Result.retry() }
    }
}

/**
 * S43_FOREGROUND_OUTBOX_WAKE: fast background lane for a foreground PDA action.
 * The business event is already durable in SQLite before kick() is called. Network work never runs
 * on the UI thread. WorkManager remains the retry/durability path when this immediate attempt fails.
 */
object M2ImmediateOutbox {
    private val running = AtomicBoolean(false)
    private val executor = Executors.newSingleThreadExecutor()

    fun kick(context: Context) {
        M2TransportDiagnostics.noteWake(context,"IMMEDIATE")
        val app = context.applicationContext
        if (!running.compareAndSet(false, true)) return
        executor.execute {
            try {
                if (!M2ServiceTransport(app).flushOutbox()) M2WorkScheduler.schedule(app)
            } catch (_: Throwable) {
                M2WorkScheduler.schedule(app)
            } finally {
                running.set(false)
            }
        }
    }
}

object M2WorkScheduler {
    private const val FLUSH_UNIQUE = "pick-pack-1291-m2-outbox-flush"
    private const val CATCHUP_UNIQUE = "pick-pack-1291-m2-catchup"

    fun schedule(context: Context) {
        M2TransportDiagnostics.noteWake(context,"WORKMANAGER") // S44_SESSION_SINGLEFLIGHT_OBSERVABILITY
        val app = context.applicationContext
        if (!PpForegroundGate.isForeground()) return // S33_OWNER_UI_SYNC_RESOURCES
        val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        // REPLACE only the flush job: a newly queued Event ID must not sit behind stale backoff.
        // Event IDs are immutable/idempotent, so a replacement cannot create a second business event.
        val flush = OneTimeWorkRequestBuilder<M2OutboxFlushWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(app).enqueueUniqueWork(FLUSH_UNIQUE, ExistingWorkPolicy.REPLACE, flush)

        // Catch-up is coalesced separately. Its retry/backoff is no longer coupled to outbox delivery.
        val catchUp = OneTimeWorkRequestBuilder<M2CatchUpWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(app).enqueueUniqueWork(CATCHUP_UNIQUE, ExistingWorkPolicy.KEEP, catchUp)
    }
}

object M2ConnectivityMonitor {
    private val started = AtomicBoolean(false)
    fun start(context: Context) {
        if (!started.compareAndSet(false, true)) return
        val app = context.applicationContext
        val cm = app.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        runCatching {
            cm.registerDefaultNetworkCallback(object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) { if(PpForegroundGate.isForeground()) M2WorkScheduler.schedule(app) }
            })
        }.onFailure { started.set(false) }
    }
}
