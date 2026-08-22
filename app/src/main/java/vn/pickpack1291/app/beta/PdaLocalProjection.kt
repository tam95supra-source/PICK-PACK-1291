package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Device-local projection used by hot PDA screens.
 *
 * Visible state is the last confirmed Service snapshot plus durable LOCAL_PENDING mutations from
 * this PDA. D1/fenced Google authority remains canonical; rejected/review events are not applied to
 * the overlay. Exclusive allocations are explicitly marked provisional until authoritative ack.
 */
object PdaLocalProjection {
    // S25_LOCAL_LABOR_OVERLAY: session + labor context is rendered without waiting for network.
    fun employeeContext(context: Context, mnvRaw: String): JSONObject? {
        val mnv = mnvRaw.trim()
        if (mnv.isBlank()) return null
        val employee = MasterDataCache.employee(context, mnv) ?: return null
        val store = OperationalDataStore(context.applicationContext)
        val businessDate = store.businessDate() // S45_BETA40_OWNER_FIXES
        val day = store.loadDay(businessDate)
        if(day==null){
            // S29_OWNER_LOCALFIRST_HISTORY: employee master is enough for immediate scan UX.
            // Session state remains fenced until a canonical day snapshot arrives.
            return JSONObject()
                .put("ok",true)
                .put("source","PDA_SQLITE_WARMING")
                .put("business_date",businessDate)
                .put("day_revision",0L)
                .put("employee",employee)
                .put("state","UNKNOWN_WARMING")
                .put("session",JSONObject.NULL)
                .put("active_labor",JSONObject.NULL)
                .put("session_known",false)
                .put("reconciliation_state","CACHE_WARMING")
                .put("provisional",false)
        }
        val sessions = day.optJSONArray("sessions") ?: JSONArray()
        var session: JSONObject? = null
        for (i in 0 until sessions.length()) {
            val candidate = sessions.optJSONObject(i) ?: continue
            if (candidate.optString("mnv") == mnv) { session = JSONObject(candidate.toString()); break }
        }
        var state = when (session?.optString("state")?.uppercase()) {
            "ACTIVE" -> "ACTIVE"
            "ENDED" -> "ENDED"
            else -> "NOT_ENTERED"
        }
        val labor = day?.optJSONArray("labor") ?: JSONArray()
        var activeLabor: JSONObject? = null
        for (i in 0 until labor.length()) {
            val item = labor.optJSONObject(i) ?: continue
            if (item.optString("mnv") != mnv) continue
            val open = item.optString("state").uppercase() in setOf("OPEN", "ACTIVE") || item.optString("end_at").isBlank()
            if (open) activeLabor = JSONObject(item.toString())
        }
        var reconciliationState = "CONFIRMED"
        var provisionalExclusive = false
        for (item in store.projectionMutations(500)) {
            val body = item.body
            val payload = body.optJSONObject("payload") ?: body
            val eventDate = payload.optString("business_date").ifBlank { body.optString("business_date") }
            if (eventDate.isNotBlank() && eventDate != businessDate) continue
            if (payload.optString("mnv") != mnv) continue
            val action = body.optString("action").ifBlank { payload.optString("action") }
            when (action) {
                "enter" -> {
                    session = (session ?: JSONObject()).apply {
                        put("mnv", mnv); put("state", "ACTIVE")
                        copyIfPresent(payload, this, "shift", "work_choice", "pda_serial", "user_pick", "pack_table", "user_pack", "resource_note")
                        if(payload.has("pda_status_at_enter")) put("pda_enter_status",payload.optString("pda_status_at_enter"))
                    }
                    state = "ACTIVE"
                }
                "exit" -> {
                    session = (session ?: JSONObject()).apply {
                        put("mnv",mnv);put("state","ENDED")
                        if(payload.has("pda_exit_status"))put("pda_exit_status",payload.optString("pda_exit_status"))
                    }
                    state = "ENDED"
                }
                "resource_change" -> {
                    session = (session ?: JSONObject()).apply {
                        put("mnv", mnv)
                        copyIfPresent(payload, this, "work_choice", "pda_serial", "user_pick", "pack_table", "user_pack")
                    }
                }
                "labor_start" -> {
                    activeLabor = JSONObject().apply {
                        put("mnv", mnv); put("state", "OPEN")
                        copyIfPresent(payload, this, "labor_type", "time_marker", "note", "deduct_staff", "shift")
                    }
                }
                "labor_finish" -> activeLabor = null
            }
            reconciliationState = "LOCAL_PENDING"
            provisionalExclusive = provisionalExclusive || item.exclusive
        }
        return JSONObject()
            .put("ok", true)
            .put("source", "PDA_SQLITE")
            .put("business_date", day?.optString("business_date", businessDate) ?: businessDate)
            .put("day_revision", day?.optLong("day_revision", 0L) ?: 0L)
            .put("employee", employee)
            .put("state", state)
            .put("session", session ?: JSONObject.NULL)
            .put("active_labor", activeLabor ?: JSONObject.NULL)
            .put("session_known", true)
            .put("reconciliation_state", reconciliationState)
            .put("provisional", provisionalExclusive)
    }

    fun resourceOptions(context: Context, mnvRaw: String): JSONObject {
        // S45_BETA40_OWNER_FIXES: N is authoritative for the active UI; returned users are re-issuable, active users stay blocked.
        val mnv=mnvRaw.trim();val raw=MasterDataCache.resourceOptions(context);val store=OperationalDataStore(context.applicationContext);val date=store.businessDate()
        val byMnv=LinkedHashMap<String,JSONObject>();val usedPicks=LinkedHashSet<String>();val usedPackUsers=LinkedHashSet<String>()
        val day=store.loadDay(date);val sessions=day?.optJSONArray("sessions")?:JSONArray()
        for(i in 0 until sessions.length()){
            val src=sessions.optJSONObject(i)?:continue;val who=src.optString("mnv").trim();if(who.isBlank())continue
            val copy=JSONObject(src.toString());byMnv[who]=copy
            copy.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let(usedPicks::add)
            copy.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let(usedPackUsers::add)
        }
        for(item in store.projectionMutations(1000)){
            val body=item.body;val payload=body.optJSONObject("payload")?:body
            val eventDate=payload.optString("business_date").ifBlank{body.optString("business_date")}
            if(eventDate.isNotBlank()&&eventDate!=date)continue
            val who=payload.optString("mnv").trim();if(who.isBlank())continue
            val action=body.optString("action").ifBlank{payload.optString("action")}
            val cur=byMnv.getOrPut(who){JSONObject().put("mnv",who).put("state","NOT_ENTERED")}
            when(action){
                "enter"->{cur.put("state","ACTIVE");for(k in listOf("shift","work_choice","pda_serial","user_pick","pack_table","user_pack"))if(payload.has(k))cur.put(k,payload.opt(k));payload.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let(usedPicks::add);payload.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let(usedPackUsers::add)}
                "resource_change"->{for(k in listOf("work_choice","pda_serial","user_pick","pack_table","user_pack"))if(payload.has(k))cur.put(k,payload.opt(k));payload.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let(usedPicks::add);payload.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let(usedPackUsers::add)}
                "exit"->cur.put("state","ENDED")
            }
        }
        val busyPdas=LinkedHashSet<String>();val busyPicks=LinkedHashSet<String>();val busyTables=LinkedHashSet<String>();val busyPackUsers=LinkedHashSet<String>()
        for((who,ses) in byMnv){
            if(who==mnv||!ses.optString("state").equals("ACTIVE",true))continue
            ses.optString("pda_serial").trim().takeIf{it.isNotBlank()}?.let(busyPdas::add)
            ses.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let(busyPicks::add)
            ses.optString("pack_table").trim().takeIf{it.isNotBlank()}?.let(busyTables::add)
            ses.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let(busyPackUsers::add)
        }
        val current=byMnv[mnv]
        val pdas=JSONArray();val sourcePdas=raw.optJSONArray("pdas")?:JSONArray()
        for(i in 0 until sourcePdas.length()){val x=sourcePdas.optJSONObject(i)?:continue;val id=x.optString("serial").trim();if(id.isNotBlank()&&(id !in busyPdas||id==current?.optString("pda_serial")))pdas.put(JSONObject(x.toString()))}
        val normalPicks=JSONArray();val reissuePicks=JSONArray();val sourcePicks=raw.optJSONArray("user_picks")?:JSONArray()
        for(i in 0 until sourcePicks.length()){val id=sourcePicks.optString(i).trim();if(id.isBlank())continue;val isCurrent=id==current?.optString("user_pick");when{isCurrent->normalPicks.put(id);id in busyPicks->Unit;id in usedPicks->reissuePicks.put(JSONObject().put("id",id).put("busy",false).put("used_today",true).put("duplicate_user",true).put("note","TRÙNG USER"));else->normalPicks.put(id)}}
        val normalPacks=JSONArray();val reissuePacks=JSONArray();val sourcePacks=raw.optJSONArray("pack_tables")?:JSONArray()
        for(i in 0 until sourcePacks.length()){val x=sourcePacks.optJSONObject(i)?:continue;val table=x.optString("table").trim();val user=x.optString("user_pack").trim();if(table.isBlank()||user.isBlank())continue;val isCurrent=table==current?.optString("pack_table")&&user==current?.optString("user_pack");when{isCurrent->normalPacks.put(JSONObject(x.toString()).put("duplicate_user",false));table in busyTables||user in busyPackUsers->Unit;user in usedPackUsers->reissuePacks.put(JSONObject(x.toString()).put("duplicate_user",true).put("note","TRÙNG USER"));else->normalPacks.put(JSONObject(x.toString()).put("duplicate_user",false))}}
        return JSONObject().put("ok",true).put("source","PDA_LOCAL_MASTER").put("business_date",date).put("pdas",pdas).put("pda_statuses",raw.optJSONArray("pda_statuses")?:JSONArray()).put("user_picks",normalPicks).put("user_picks_reissue",reissuePicks).put("pack_tables",normalPacks).put("pack_tables_reissue",reissuePacks).put("current",current?:JSONObject.NULL).put("master_revision",raw.optLong("master_revision",0L))
    }

    private fun copyIfPresent(from: JSONObject, to: JSONObject, vararg keys: String) {
        for (key in keys) if (from.has(key)) to.put(key, from.opt(key))
    }
}
