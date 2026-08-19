package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Device-local projection used by hot PDA screens.
 *
 * D1 remains canonical. This projection renders the latest confirmed local snapshot immediately;
 * Service reconciliation and the durable pending overlay converge it across devices.
 */
object PdaLocalProjection {
    fun employeeContext(context: Context, mnvRaw: String): JSONObject? {
        val mnv = mnvRaw.trim()
        if (mnv.isBlank()) return null
        val employee = MasterDataCache.employee(context, mnv) ?: return null
        val store = OperationalDataStore(context.applicationContext)
        val businessDate = store.latestBusinessDate()
        val day = store.loadDay(businessDate) ?: return null
        val sessions = day.optJSONArray("sessions") ?: JSONArray()
        var session: JSONObject? = null
        for (i in 0 until sessions.length()) {
            val candidate = sessions.optJSONObject(i) ?: continue
            if (candidate.optString("mnv") == mnv) { session = JSONObject(candidate.toString()); break }
        }
        val state = when (session?.optString("state")?.uppercase()) {
            "ACTIVE" -> "ACTIVE"
            "ENDED" -> "ENDED"
            else -> "NOT_ENTERED"
        }
        return JSONObject()
            .put("ok", true)
            .put("source", "PDA_SQLITE")
            .put("business_date", day.optString("business_date", businessDate))
            .put("day_revision", day.optLong("day_revision", 0L))
            .put("employee", employee)
            .put("state", state)
            .put("session", session ?: JSONObject.NULL)
    }

    fun resourceOptions(context: Context, mnvRaw: String): JSONObject {
        val mnv = mnvRaw.trim()
        val raw = MasterDataCache.resourceOptions(context)
        val store = OperationalDataStore(context.applicationContext)
        val day = store.loadDay(store.latestBusinessDate())
        val sessions = day?.optJSONArray("sessions") ?: JSONArray()

        val busyPdas = HashSet<String>()
        val busyPackTables = HashSet<String>()
        val usedPicks = HashSet<String>()
        val usedPackUsers = HashSet<String>()
        for (i in 0 until sessions.length()) {
            val s = sessions.optJSONObject(i) ?: continue
            if (s.optString("mnv") == mnv) continue
            val active = s.optString("state").equals("ACTIVE", true)
            val pda = s.optString("pda_serial").trim()
            val pick = s.optString("user_pick").trim()
            val table = s.optString("pack_table").trim()
            val packUser = s.optString("user_pack").trim()
            if (active && pda.isNotBlank()) busyPdas += pda
            if (active && table.isNotBlank()) busyPackTables += table
            if (pick.isNotBlank()) usedPicks += pick
            if (packUser.isNotBlank()) usedPackUsers += packUser
        }

        val pdas = JSONArray()
        val sourcePdas = raw.optJSONArray("pdas") ?: JSONArray()
        for (i in 0 until sourcePdas.length()) {
            val p = sourcePdas.optJSONObject(i) ?: continue
            if (p.optString("serial") !in busyPdas) pdas.put(JSONObject(p.toString()))
        }

        val picks = JSONArray()
        val sourcePicks = raw.optJSONArray("user_picks") ?: JSONArray()
        for (i in 0 until sourcePicks.length()) {
            val value = sourcePicks.optString(i).trim()
            if (value.isNotBlank() && value !in usedPicks) picks.put(value)
        }

        val packs = JSONArray()
        val sourcePacks = raw.optJSONArray("pack_tables") ?: JSONArray()
        for (i in 0 until sourcePacks.length()) {
            val p = sourcePacks.optJSONObject(i) ?: continue
            val table = p.optString("table").trim()
            val user = p.optString("user_pack").trim()
            if (table.isNotBlank() && user.isNotBlank() && table !in busyPackTables && user !in usedPackUsers) {
                packs.put(JSONObject(p.toString()))
            }
        }

        return JSONObject()
            .put("ok", true)
            .put("source", "PDA_LOCAL_MASTER")
            .put("pdas", pdas)
            .put("user_picks", picks)
            .put("pack_tables", packs)
            .put("master_revision", raw.optLong("master_revision", 0L))
    }
}
