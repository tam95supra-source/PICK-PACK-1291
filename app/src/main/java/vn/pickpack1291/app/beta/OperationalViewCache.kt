package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Small device-side snapshot cache for read-only operational views.
 *
 * The server / Google Sheet remains authoritative. These snapshots are only used to render
 * immediately while the app revalidates in the background (stale-while-revalidate).
 */
object OperationalViewCache {
    private const val PREFS = "pp_operational_view_cache_v1"
    private const val TZ = "Asia/Bangkok"

    private fun businessDate(): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).apply {
        timeZone = TimeZone.getTimeZone(TZ)
    }.format(Date())

    private fun scopedKey(key: String): String = "${businessDate()}|$key"

    fun load(context: Context, key: String): JSONObject? {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(scopedKey(key), null) ?: return null
        return runCatching { JSONObject(raw) }.getOrNull()
    }

    fun save(context: Context, key: String, json: JSONObject) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(scopedKey(key), json.toString())
            .putLong(scopedKey("$key@at"), System.currentTimeMillis())
            .apply()
    }

    fun ageMs(context: Context, key: String): Long {
        val at = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getLong(scopedKey("$key@at"), 0L)
        return if (at <= 0L) Long.MAX_VALUE else (System.currentTimeMillis() - at).coerceAtLeast(0L)
    }

    fun detailKey(mnv: String): String = "history_shared:$mnv"
}
