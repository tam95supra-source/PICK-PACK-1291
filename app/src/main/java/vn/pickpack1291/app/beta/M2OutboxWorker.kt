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
import java.util.concurrent.atomic.AtomicBoolean

/** Durable outbox replay plus authoritative day/master catch-up after reconnect or FCM wake. */
class M2OutboxWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {
    override fun doWork(): Result = try {
        val transport = M2ServiceTransport(applicationContext)
        val flushed = transport.flushOutbox()
        val caughtUp = M2BackgroundSync.catchUp(applicationContext)
        M2PushRegistration.flush(applicationContext)
        if (flushed && caughtUp) Result.success() else Result.retry()
    } catch (_: Throwable) { Result.retry() }
}

object M2WorkScheduler {
    private const val UNIQUE = "pick-pack-1291-m2-outbox"
    fun schedule(context: Context) {
        val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
        val request = OneTimeWorkRequestBuilder<M2OutboxWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .build()
        // Coalesce reconnect/FCM/outbox wakes instead of replacing an in-flight authoritative catch-up.
        WorkManager.getInstance(context.applicationContext).enqueueUniqueWork(UNIQUE, ExistingWorkPolicy.KEEP, request)
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
                override fun onAvailable(network: Network) { M2WorkScheduler.schedule(app) }
            })
        }.onFailure { started.set(false) }
    }
}
