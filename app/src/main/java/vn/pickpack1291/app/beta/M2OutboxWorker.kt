package vn.pickpack1291.app.beta

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.atomic.AtomicBoolean

class M2OutboxWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {
    override fun doWork(): Result = try {
        if (M2ServiceTransport(applicationContext).flushOutbox()) Result.success() else Result.retry()
    } catch (_: Throwable) { Result.retry() }
}

object M2WorkScheduler {
    private const val UNIQUE = "pick-pack-1291-m2-outbox"
    fun schedule(context: Context) {
        val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
        val request = OneTimeWorkRequestBuilder<M2OutboxWorker>().setConstraints(constraints).build()
        WorkManager.getInstance(context.applicationContext).enqueueUniqueWork(UNIQUE, ExistingWorkPolicy.REPLACE, request)
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
