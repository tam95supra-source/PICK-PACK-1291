package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Build
import android.os.SystemClock
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object LocalLogManager {
    private const val PREFS = "pp1291_log_state"
    private const val KEY_DAILY = "last_daily_log"

    fun installCrashHandler(context: Context) {
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching {
                val content = buildString {
                    appendLine("type=CRASH")
                    appendCommon(context)
                    appendLine("thread=${safe(thread.name)}")
                    appendLine("exception=${safe(error.javaClass.name)}")
                    appendLine("message=${safe(error.message)}")
                    appendLine("stacktrace=")
                    appendLine(error.stackTraceToString())
                }
                write(context, "CRASH", content)
            }
            previous?.uncaughtException(thread, error)
        }
    }

    fun createDailyIfNeeded(context: Context): File? {
        val day = SimpleDateFormat("yyyyMMdd", Locale.US).format(Date())
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY_DAILY, null) == day) return null
        val file = write(context, "ANDROID_DAILY", buildString {
            appendLine("type=ANDROID_DAILY")
            appendCommon(context)
            appendLine("uptime_ms=${SystemClock.elapsedRealtime()}")
            appendLine("note=Pending upload until backend logging endpoint is enabled.")
        })
        prefs.edit().putString(KEY_DAILY, day).apply()
        return file
    }

    fun createManualReport(context: Context, screen: String, syncState: String): File {
        return write(context, "MANUAL_REPORT", buildString {
            appendLine("type=MANUAL_REPORT")
            appendCommon(context)
            appendLine("screen=${safe(screen)}")
            appendLine("sync_state=${safe(syncState)}")
            appendLine("uptime_ms=${SystemClock.elapsedRealtime()}")
            appendLine("memory_max_mb=${Runtime.getRuntime().maxMemory() / 1024 / 1024}")
            appendLine("memory_total_mb=${Runtime.getRuntime().totalMemory() / 1024 / 1024}")
            appendLine("memory_free_mb=${Runtime.getRuntime().freeMemory() / 1024 / 1024}")
            appendLine("pending_queue=0")
            appendLine("last_server_seq=preview-not-connected")
            appendLine("network=backend-not-connected")
            appendLine("note=This preview intentionally excludes credentials, tokens, password verifiers, cookies, private keys and real operational data.")
        })
    }

    private fun StringBuilder.appendCommon(context: Context) {
        appendLine("timestamp=${SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(Date())}")
        appendLine("package=${context.packageName}")
        appendLine("version=0.1.0-beta.1-preview")
        appendLine("channel=BETA_PREVIEW")
        appendLine("manufacturer=${safe(Build.MANUFACTURER)}")
        appendLine("model=${safe(Build.MODEL)}")
        appendLine("android=${safe(Build.VERSION.RELEASE)}")
        appendLine("api=${Build.VERSION.SDK_INT}")
        appendLine("device=${safe(Build.DEVICE)}")
    }

    private fun write(context: Context, prefix: String, content: String): File {
        val dir = File(context.filesDir, "diagnostic_logs").apply { mkdirs() }
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(Date())
        return File(dir, "${prefix}_${stamp}.log").apply { writeText(content) }
    }

    private fun safe(value: String?): String = value.orEmpty()
        .replace("\n", " ")
        .replace("\r", " ")
        .take(300)
}
