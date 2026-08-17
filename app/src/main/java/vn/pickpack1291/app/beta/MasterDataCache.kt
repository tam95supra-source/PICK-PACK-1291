package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer

object MasterDataCache {
    private const val PREFS = "pp1291_master_cache"
    private const val KEY_JSON = "snapshot"
    private const val KEY_REV = "revision"
    private const val KEY_AT = "saved_at"

    fun save(context: Context, snapshot: JSONObject) {
        if (!snapshot.optBoolean("ok", false)) return
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_JSON, snapshot.toString())
            .putLong(KEY_REV, snapshot.optLong("master_revision", 0L))
            .putLong(KEY_AT, System.currentTimeMillis())
            .apply()
    }

    fun snapshot(context: Context): JSONObject? {
        val raw = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_JSON, null) ?: return null
        return runCatching { JSONObject(raw) }.getOrNull()
    }

    fun revision(context: Context): Long = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_REV, 0L)
    fun savedAt(context: Context): Long = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_AT, 0L)

    fun employee(context: Context, mnv: String): JSONObject? {
        val a = snapshot(context)?.optJSONArray("staff") ?: return null
        for (i in 0 until a.length()) {
            val e = a.optJSONObject(i) ?: continue
            if (e.optString("mnv") == mnv) return e
        }
        return null
    }

    fun searchStaff(context: Context, query: String, limit: Int = 60): JSONArray {
        val out = JSONArray()
        val q = fold(query)
        if (q.length < 2) return out
        val a = snapshot(context)?.optJSONArray("staff") ?: return out
        for (i in 0 until a.length()) {
            val e = a.optJSONObject(i) ?: continue
            if (fold(e.optString("mnv") + " " + e.optString("full_name")).contains(q)) {
                out.put(JSONObject(e.toString()))
                if (out.length() >= limit) break
            }
        }
        return out
    }

    private fun fold(v: String): String = Normalizer.normalize(v, Normalizer.Form.NFD)
        .replace(Regex("\\p{Mn}+"), "").uppercase().trim()
}
