#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STORE=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt'
PROJ=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/PdaLocalProjection.kt'
S25=ROOT/'tools/apply_s25_cache_sync_web_pda_fixes.py'
MARK='S27_PROJECTION_ACK_GAP'

s=STORE.read_text(encoding='utf-8')
if MARK not in s:
    anchor='''    fun pendingMutations(limit: Int = 100): List<PendingMutation> = withDbLock {\n'''
    pos=s.find(anchor)
    if pos<0: raise SystemExit('S27 pendingMutations anchor missing')
    next_anchor='''    fun markMutationSynced(eventId: String) = markMutationResolved(eventId, "CONFIRMED", "")\n'''
    end=s.find(next_anchor,pos)
    if end<0: raise SystemExit('S27 markMutationSynced anchor missing')
    insert='''    /**
     * S27_PROJECTION_ACK_GAP: visible local projection includes ordinary pending writes plus
     * CONFIRMED writes whose ACK is newer than the currently stored day snapshot. This closes the
     * ACK-to-next-snapshot gap without ever making a confirmed write eligible for network resend.
     * Once reconcile saves a snapshot after the ACK, the confirmed overlay disappears.
     */
    fun projectionMutations(limit: Int = 500): List<PendingMutation> = withDbLock {
        val out = ArrayList<PendingMutation>()
        val now = System.currentTimeMillis().toString()
        readableDb().query(
            "mutation_outbox",
            arrayOf("event_id", "body_json", "exclusive", "status", "attempt_count", "queued_at", "updated_at"),
            "(status IN ('LOCAL_PENDING','PENDING','RETRY','OFFLINE_PROVISIONAL') AND next_attempt_at <= ?) OR status='CONFIRMED'",
            arrayOf(now), null, null, "queued_at ASC", limit.coerceIn(1, 1000).toString(),
        ).use { c ->
            while (c.moveToNext()) {
                val body = runCatching { JSONObject(c.getString(1)) }.getOrNull() ?: continue
                val status = c.getString(3)
                if (status == "CONFIRMED") {
                    val payload = body.optJSONObject("payload") ?: body
                    val date = payload.optString("business_date").ifBlank { body.optString("business_date") }
                    if (date.isBlank()) continue
                    val ackAt = c.getLong(6)
                    val snapshotSavedAt = readableDb().query(
                        "day_snapshot", arrayOf("saved_at"), "business_date=?", arrayOf(date), null, null, null, "1"
                    ).use { sc -> if (sc.moveToFirst()) sc.getLong(0) else 0L }
                    if (snapshotSavedAt >= ackAt) continue
                }
                out += PendingMutation(c.getString(0), body, c.getInt(2) == 1, status, c.getInt(4), c.getLong(5))
            }
        }
        out
    }

'''
    s=s[:end]+insert+s[end:]
    STORE.write_text(s,encoding='utf-8')

# Make both committed source and build-generated S25 projection use projectionMutations.
p=PROJ.read_text(encoding='utf-8')
p=p.replace('store.pendingMutations(500)', 'store.projectionMutations(500)')
PROJ.write_text(p,encoding='utf-8')

p=S25.read_text(encoding='utf-8')
p=p.replace('store.pendingMutations(500)', 'store.projectionMutations(500)')
S25.write_text(p,encoding='utf-8')

print('Applied S27 projection ACK gap fix')
