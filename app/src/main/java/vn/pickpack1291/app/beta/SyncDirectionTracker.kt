package vn.pickpack1291.app.beta

import android.os.SystemClock
import java.util.ArrayDeque
import java.util.concurrent.atomic.AtomicInteger

/** Process-wide indicator for real synchronization direction and application payload throughput. */
object SyncDirectionTracker {
    data class Snapshot(
        val uploading: Boolean,
        val downloading: Boolean,
        val symbol: String,
        val label: String,
        val shortLabel: String,
        val active: Boolean,
        val uploadBps: Long,
        val downloadBps: Long,
        val uploadedBytes: Long,
        val downloadedBytes: Long,
    )

    private data class ByteSample(val at: Long, val bytes: Long)

    private val uploads = AtomicInteger(0)
    private val downloads = AtomicInteger(0)
    private val rateLock = Any()
    private val upSamples = ArrayDeque<ByteSample>()
    private val downSamples = ArrayDeque<ByteSample>()
    @Volatile private var uploadedTotal = 0L
    @Volatile private var downloadedTotal = 0L
    @Volatile private var lastUploadAt = 0L
    @Volatile private var lastDownloadAt = 0L

    private val uploadActions = setOf(
        "enter", "exit", "resource_change", "labor_start", "labor_finish",
        "staff_upsert", "staff_delete", "account_upsert", "account_status",
        "change_email", "change_password"
    )

    fun isUploadAction(action: String): Boolean = action in uploadActions

    fun beginUpload() {
        uploads.incrementAndGet()
        lastUploadAt = SystemClock.elapsedRealtime()
    }

    fun endUpload() {
        uploads.updateAndGet { if (it > 0) it - 1 else 0 }
        lastUploadAt = SystemClock.elapsedRealtime()
    }

    fun beginDownload() {
        downloads.incrementAndGet()
        lastDownloadAt = SystemClock.elapsedRealtime()
    }

    fun endDownload() {
        downloads.updateAndGet { if (it > 0) it - 1 else 0 }
        lastDownloadAt = SystemClock.elapsedRealtime()
    }

    fun recordUploadBytes(bytes: Long) {
        if (bytes <= 0) return
        val now = SystemClock.elapsedRealtime()
        synchronized(rateLock) {
            uploadedTotal += bytes
            upSamples.addLast(ByteSample(now, bytes))
            prune(upSamples, now)
        }
    }

    fun recordDownloadBytes(bytes: Long) {
        if (bytes <= 0) return
        val now = SystemClock.elapsedRealtime()
        synchronized(rateLock) {
            downloadedTotal += bytes
            downSamples.addLast(ByteSample(now, bytes))
            prune(downSamples, now)
        }
    }

    private fun prune(samples: ArrayDeque<ByteSample>, now: Long) {
        while (samples.isNotEmpty() && now - samples.first().at > RATE_WINDOW_MS) samples.removeFirst()
    }

    private fun rate(samples: ArrayDeque<ByteSample>, now: Long): Long {
        prune(samples, now)
        if (samples.isEmpty()) return 0L
        val bytes = samples.sumOf { it.bytes }
        val elapsed = (now - samples.first().at).coerceAtLeast(250L)
        return bytes * 1000L / elapsed
    }

    fun snapshot(): Snapshot {
        val upActive = uploads.get() > 0
        val downActive = downloads.get() > 0
        val now = SystemClock.elapsedRealtime()
        val rates = synchronized(rateLock) { rate(upSamples, now) to rate(downSamples, now) }
        val recentlyUp = rates.first > 0 || now - lastUploadAt < RATE_WINDOW_MS
        val recentlyDown = rates.second > 0 || now - lastDownloadAt < RATE_WINDOW_MS
        val up = upActive || recentlyUp
        val down = downActive || recentlyDown
        val base = when {
            up && down -> arrayOf("↕", "Đang đồng bộ hai chiều", "Hai chiều")
            up -> arrayOf("↑", "Đang đồng bộ lên", "Đang gửi")
            down -> arrayOf("↓", "Đang đồng bộ xuống", "Đang nhận")
            else -> arrayOf("✓", "Sẵn sàng", "Sẵn sàng")
        }
        return Snapshot(
            uploading = up,
            downloading = down,
            symbol = base[0],
            label = base[1],
            shortLabel = base[2],
            active = up || down,
            uploadBps = rates.first,
            downloadBps = rates.second,
            uploadedBytes = uploadedTotal,
            downloadedBytes = downloadedTotal,
        )
    }

    private const val RATE_WINDOW_MS = 2_500L
}
