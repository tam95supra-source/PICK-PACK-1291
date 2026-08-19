package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL

/**
 * Background catch-up invoked by WorkManager after FCM/network/outbox wake.
 * FCM is only an invalidation: this class re-reads authoritative revisions, refreshes changed day
 * snapshots, and rebuilds the persistent master cache only when a master namespace revision moved.
 */
object M2BackgroundSync {
    private val masterNamespaces = listOf("employees", "catalogs", "pda", "user_pick", "pack_table", "user_pack")

    fun catchUp(context: Context): Boolean {
        val app = context.applicationContext
        val transport = M2ServiceTransport(app)
        val statusResult = transport.sync("sync_status", JSONObject())
        if (!statusResult.handled || !statusResult.ok || statusResult.json == null) return false
        val status = statusResult.json
        val store = OperationalDataStore(app)

        val dayRevisions = status.optJSONObject("day_revisions") ?: JSONObject()
        val dates = ArrayList<String>()
        val it = dayRevisions.keys()
        while (it.hasNext()) dates += it.next()
        val ordered = dates.sortedDescending().take(7)
        store.applyBusinessWindow(ordered, status.optLong("retention_epoch", store.authorityEpoch()))
        status.optJSONObject("authority")?.let(store::saveAuthority)
        store.putMeta("business_date", status.optString("business_date").ifBlank { ordered.firstOrNull().orEmpty() })
        store.putMeta("retention_floor", ordered.lastOrNull().orEmpty())

        for (date in ordered) {
            val remoteRevision = dayRevisions.optLong(date, 0L)
            if (store.revision(date) == remoteRevision) continue
            val day = transport.sync("sync_day", JSONObject().put("business_date", date))
            if (day.handled && day.ok) day.json?.optJSONObject("day")?.let(store::saveDay)
        }

        refreshMasterIfChanged(app, transport.discoverySnapshot())
        return true
    }

    private fun refreshMasterIfChanged(context: Context, discovery: JSONObject?) {
        val d = discovery ?: return
        if (d.optString("authority_mode") != "SERVICE_PRIMARY") return
        val base = d.optString("service_url").trimEnd('/')
        val token = context.getSharedPreferences("pp_m2_service_transport", Context.MODE_PRIVATE).getString("service_token", null).orEmpty()
        if (base.isBlank() || token.isBlank()) return
        val status = getJson("$base/v1/sync/status", token) ?: return
        val revisions = status.optJSONObject("master_revisions") ?: return
        val localRev = context.getSharedPreferences("pp_m2_master_revision", Context.MODE_PRIVATE)
        val changed = masterNamespaces.any { revisions.optLong(it, 0L) != localRev.getLong(it, -1L) }
        if (!changed) return

        val snapshot = JSONObject()
        val resources = JSONArray()
        var employees = JSONArray()
        var catalogs = JSONArray()
        var packTables = JSONArray()
        for (namespace in masterNamespaces) {
            val after = localRev.getLong(namespace, -1L).coerceAtLeast(0L)
            val url = "$base/v1/delta/master?namespace=${URLEncoder.encode(namespace, "UTF-8")}&after_revision=$after"
            val delta = getJson(url, token) ?: return
            val rows = delta.optJSONArray("rows") ?: JSONArray()
            when (namespace) {
                "employees" -> employees = JSONArray(rows.toString())
                "catalogs" -> catalogs = JSONArray(rows.toString())
                "pack_table" -> packTables = JSONArray(rows.toString())
                "pda", "user_pick", "user_pack" -> {
                    val type = when (namespace) { "pda" -> "PDA"; "user_pick" -> "USER_PICK"; else -> "USER_PACK" }
                    for (i in 0 until rows.length()) {
                        val row = rows.optJSONObject(i) ?: continue
                        resources.put(JSONObject(row.toString()).put("resource_type", type))
                    }
                }
            }
        }
        snapshot.put("employees", employees)
            .put("catalogs", catalogs)
            .put("resources", resources)
            .put("pack_tables", packTables)
            .put("master_revision", revisions.keys().asSequence().maxOfOrNull { revisions.optLong(it, 0L) } ?: 0L)
        MasterDataCache.saveSnapshot(context, snapshot)
        val edit = localRev.edit()
        masterNamespaces.forEach { edit.putLong(it, revisions.optLong(it, 0L)) }
        edit.apply()
    }

    private fun getJson(endpoint: String, bearer: String): JSONObject? {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(endpoint).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"; connectTimeout = 4_000; readTimeout = 8_000
                setRequestProperty("Accept", "application/json")
                setRequestProperty("Authorization", "Bearer $bearer")
            }
            if (conn.responseCode !in 200..299) return null
            val text = conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            JSONObject(text).takeIf { it.optBoolean("ok", false) }
        } catch (_: Throwable) { null } finally { conn?.disconnect() }
    }
}
