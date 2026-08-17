package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer
import java.util.concurrent.ConcurrentHashMap

object MasterDataCache {
    private const val PREFS = "pp1291_master_cache"
    private const val KEY_JSON = "snapshot"
    private const val KEY_REV = "revision"
    private const val KEY_AT = "saved_at"

    @Volatile private var memorySnapshot: JSONObject? = null
    @Volatile private var staffByMnv: Map<String, JSONObject> = emptyMap()
    @Volatile private var searchableStaff: List<Pair<String, JSONObject>> = emptyList()

    fun hydrate(context: Context) { snapshot(context) }

    @Synchronized
    fun save(context: Context, snapshot: JSONObject) {
        if (!snapshot.optBoolean("ok", false)) return
        val copy = JSONObject(snapshot.toString())
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_JSON, copy.toString())
            .putLong(KEY_REV, copy.optLong("master_revision", 0L))
            .putLong(KEY_AT, System.currentTimeMillis())
            .apply()
        install(copy)
    }

    fun snapshot(context: Context): JSONObject? {
        memorySnapshot?.let { return it }
        synchronized(this) {
            memorySnapshot?.let { return it }
            val raw = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_JSON, null) ?: return null
            val parsed = runCatching { JSONObject(raw) }.getOrNull() ?: return null
            install(parsed)
            return memorySnapshot
        }
    }

    private fun install(snapshot: JSONObject) {
        val byMnv = ConcurrentHashMap<String, JSONObject>()
        val searchable = ArrayList<Pair<String, JSONObject>>()
        val staff = snapshot.optJSONArray("staff") ?: JSONArray()
        for (i in 0 until staff.length()) {
            val e = staff.optJSONObject(i) ?: continue
            val mnv = e.optString("mnv").trim()
            if (mnv.isBlank()) continue
            byMnv[mnv] = e
            searchable += fold(mnv + " " + e.optString("full_name") + " " + e.optString("supplier") + " " + e.optString("main_position")) to e
        }
        staffByMnv = byMnv
        searchableStaff = searchable
        memorySnapshot = snapshot
    }

    fun revision(context: Context): Long = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_REV, 0L)
    fun savedAt(context: Context): Long = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_AT, 0L)

    fun staffCount(context: Context): Int {
        snapshot(context)
        return staffByMnv.size
    }

    fun employee(context: Context, mnv: String): JSONObject? {
        snapshot(context)
        return staffByMnv[mnv.trim()]?.let { JSONObject(it.toString()) }
    }

    fun allStaff(context: Context, limit: Int = 200): JSONArray {
        snapshot(context)
        val out = JSONArray()
        searchableStaff.take(limit).forEach { out.put(JSONObject(it.second.toString())) }
        return out
    }

    fun searchStaff(context: Context, query: String, limit: Int = 80): JSONArray {
        snapshot(context)
        val out = JSONArray()
        val q = fold(query)
        if (q.isBlank()) return allStaff(context, limit)
        for ((key, e) in searchableStaff) {
            if (key.contains(q)) {
                out.put(JSONObject(e.toString()))
                if (out.length() >= limit) break
            }
        }
        return out
    }

    private fun fold(v: String): String = Normalizer.normalize(v, Normalizer.Form.NFD)
        .replace(Regex("\\p{Mn}+"), "").uppercase().trim()
}
