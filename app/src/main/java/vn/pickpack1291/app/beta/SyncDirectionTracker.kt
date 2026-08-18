package vn.pickpack1291.app.beta

import android.os.SystemClock
import java.util.concurrent.atomic.AtomicInteger

/** Process-wide indicator for real synchronization direction. */
object SyncDirectionTracker {
    data class Snapshot(
        val uploading: Boolean,
        val downloading: Boolean,
        val symbol: String,
        val label: String,
        val shortLabel: String,
        val active: Boolean,
    )

    private val uploads = AtomicInteger(0)
    private val downloads = AtomicInteger(0)
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

    fun snapshot(): Snapshot {
        val up = uploads.get() > 0
        val down = downloads.get() > 0
        return when {
            up && down -> Snapshot(true, true, "↕", "Đang đồng bộ hai chiều", "Hai chiều", true)
            up -> Snapshot(true, false, "↑", "Đang đồng bộ lên", "Đang gửi", true)
            down -> Snapshot(false, true, "↓", "Đang đồng bộ xuống", "Đang nhận", true)
            else -> Snapshot(false, false, "✓", "Sẵn sàng", "Sẵn sàng", false)
        }
    }
}
