package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Build
import android.os.SystemClock
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

object LocalLogManager {
    private const val PREFS = "pp1291_log_state"
    private const val KEY_DAILY = "last_daily_log"

    fun installCrashHandler(context: Context) {
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching {
                write(context, "CRASH", buildString {
                    appendLine("type=CRASH"); appendCommon(context)
                    appendLine("thread=${safe(thread.name)}")
                    appendLine("exception=${safe(error.javaClass.name)}")
                    appendLine("message=${safe(error.message)}")
                    appendLine("stacktrace="); appendLine(error.stackTraceToString().take(50000))
                })
            }
            previous?.uncaughtException(thread, error)
        }
    }

    fun createDailyIfNeeded(context: Context): File? {
        val day = SimpleDateFormat("yyyyMMdd", Locale.US).format(Date())
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY_DAILY, null) == day) return null
        val file = write(context, "ANDROID_DAILY", buildString {
            appendLine("type=DAILY"); appendCommon(context)
            appendLine("uptime_ms=${SystemClock.elapsedRealtime()}")
        })
        prefs.edit().putString(KEY_DAILY, day).apply()
        return file
    }

    /** Compatibility for the non-launcher preview screen. Production manual reports use sendManualReport(). */
    fun createManualReport(context: Context, screen: String, syncState: String): File =
        write(context, "MANUAL_REPORT", buildString {
            appendLine("type=MANUAL"); appendCommon(context)
            appendLine("screen=${safe(screen)}")
            appendLine("sync_state=${safe(syncState)}")
            appendLine("pending_upload=true")
        })

    fun uploadAutomaticPending(context: Context, api: BetaApiClient) {
        val files = logDir(context).listFiles()?.filter { it.name.startsWith("CRASH_") || it.name.startsWith("ANDROID_DAILY_") }?.sortedBy { it.lastModified() }.orEmpty()
        uploadNext(api, files, 0)
    }

    fun pendingCount(context: Context): Int = logDir(context).listFiles()?.count { it.isFile } ?: 0

    fun sendManualReport(context: Context, api: BetaApiClient, screen: String, syncState: String, callback: (BetaApiClient.Result) -> Unit) {
        val file = write(context, "MANUAL_REPORT", buildString {
            appendLine("type=MANUAL"); appendCommon(context)
            appendLine("screen=${safe(screen)}")
            appendLine("sync_state=${safe(syncState)}")
            appendLine("uptime_ms=${SystemClock.elapsedRealtime()}")
            appendLine("memory_max_mb=${Runtime.getRuntime().maxMemory() / 1024 / 1024}")
            appendLine("memory_total_mb=${Runtime.getRuntime().totalMemory() / 1024 / 1024}")
            appendLine("memory_free_mb=${Runtime.getRuntime().freeMemory() / 1024 / 1024}")
        })
        uploadFile(api, file, "MANUAL") { r -> if (r.ok) file.delete(); callback(r) }
    }

    private fun uploadNext(api: BetaApiClient, files: List<File>, index: Int) {
        if (index >= files.size) return
        val f = files[index]
        val type = if (f.name.startsWith("CRASH_")) "CRASH" else "DAILY"
        uploadFile(api, f, type) { r ->
            if (r.ok) f.delete()
            if (r.ok || r.code != 401) uploadNext(api, files, index + 1)
        }
    }

    private fun uploadFile(api: BetaApiClient, file: File, type: String, callback: (BetaApiClient.Result) -> Unit) {
        val eventId = UUID.randomUUID().toString()
        val payload = JSONObject().put("text", runCatching { file.readText().take(60000) }.getOrDefault("LOG_READ_FAILED")).put("file_name", file.name)
        api.call("diagnostic_log", JSONObject()
  .put("event_id", eventId)
  .put("log_type", type)
  .put("channel", BuildConfig.CHANNEL)
  .put("app_version", BuildConfig.VERSION_NAME)
  .put("payload", payload)) { result ->
  val ack = result.json?.optString("ack_event_id").orEmpty()
  if (result.ok && ack == eventId) callback(result)
  else callback(BetaApiClient.Result(false, if(result.code>0)result.code else 502, result.json, result.error ?: "LOG_ACK_MISMATCH"))
        }
    }

    private fun StringBuilder.appendCommon(context: Context) {
        appendLine("timestamp=${SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(Date())}")
        appendLine("package=${context.packageName}")
        appendLine("version=${BuildConfig.VERSION_NAME}")
        appendLine("channel=${BuildConfig.CHANNEL}")
        appendLine("manufacturer=${safe(Build.MANUFACTURER)}")
        appendLine("model=${safe(Build.MODEL)}")
        appendLine("android=${safe(Build.VERSION.RELEASE)}")
        appendLine("api=${Build.VERSION.SDK_INT}")
        appendLine("device=${safe(Build.DEVICE)}")
    }

    private fun logDir(context: Context) = File(context.filesDir, "diagnostic_logs").apply { mkdirs() }
    private fun write(context: Context, prefix: String, content: String): File {
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(Date())
        return File(logDir(context), "${prefix}_${stamp}.log").apply { writeText(content) }
    }
    private fun safe(value: String?): String = value.orEmpty().replace("\n", " ").replace("\r", " ").take(300)
}
