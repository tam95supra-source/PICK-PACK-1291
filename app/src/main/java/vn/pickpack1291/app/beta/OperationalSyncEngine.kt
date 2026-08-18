package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Revision-driven foreground synchronizer for the 45-day local operational store.
 *
 * The UI never calls this class to load a screen. Foreground sync compares tiny server day
 * revisions, then atomically replaces only changed dates. On first bootstrap N/N-1 are fetched
 * first so the current operation/report screens become useful before the older immutable window.
 */
class OperationalSyncEngine(
    context: Context,
    private val api: BetaApiClient,
    private val store: OperationalDataStore,
    private val listener: (Set<String>) -> Unit,
) {
    private data class Manifest(
        val businessDate: String,
        val retentionFloor: String,
        val retentionEpoch: Long,
        val revisions: Map<String, Long>,
    )

    private val lock = Any()
    private var inFlight = false
    private var pending: Manifest? = null

    fun reconcile(
        businessDate: String,
        retentionFloor: String,
        retentionEpoch: Long,
        dayRevisions: JSONObject,
    ) {
        if (businessDate.isBlank() || retentionFloor.isBlank()) return
        val revisions = LinkedHashMap<String, Long>()
        val keys = dayRevisions.keys()
        while (keys.hasNext()) {
            val date = keys.next()
            if (date >= retentionFloor && date <= businessDate) revisions[date] = dayRevisions.optLong(date, 0L)
        }
        val manifest = Manifest(businessDate, retentionFloor, retentionEpoch, revisions)
        synchronized(lock) {
            if (inFlight) {
                // Keep only the newest manifest that arrived while a reconciliation is active.
                // The manifest currently being processed must never enqueue itself again.
                pending = manifest
                return
            }
            inFlight = true
        }
        // Never open/query SQLite from the main/UI thread. A shared single-thread executor also
        // serializes the initial local reconciliation across transient Activity recreation.
        SYNC_EXECUTOR.execute { process(manifest) }
    }

    private fun process(manifest: Manifest) {
        try {
            store.dropBefore(manifest.retentionFloor)
            store.dropDatesNotIn(manifest.revisions.keys, manifest.retentionFloor)
            store.putMeta("retention_floor", manifest.retentionFloor)
            store.putMeta("retention_epoch", manifest.retentionEpoch.toString())

            val local = store.revisions()
            val missingOrChanged = manifest.revisions
                .filter { (date, rev) -> local[date] != rev }
                .keys
                .sortedDescending()

            if (missingOrChanged.isEmpty()) {
                finish()
                return
            }

            val localEmpty = local.isEmpty()
            if (localEmpty) {
                val previous = previousDate(manifest.businessDate)
                val hot = listOf(manifest.businessDate, previous).filter { it in missingOrChanged }
                syncDayQueue(hot, linkedSetOf()) { changed ->
                    val stillMissing = manifest.revisions
                        .filter { (date, rev) -> store.revision(date) != rev }
                        .keys
                        .sortedDescending()
                    if (stillMissing.isEmpty()) finish()
                    else syncBootstrap(stillMissing, changed)
                }
                return
            }

            // Normal steady state only N/N-1 should mutate. Fetch those dates independently so all
            // foreground PDAs converge after one revision poll without retransmitting immutable days.
            if (missingOrChanged.size <= 2) {
                syncDayQueue(missingOrChanged, linkedSetOf()) { finish() }
            } else {
                syncBootstrap(missingOrChanged, linkedSetOf())
            }
        } catch (_: Throwable) {
            // Local cache failure must never crash the operational app. Leave revisions stale and
            // let the next foreground poll retry after the device/database becomes available.
            finish()
        }
    }

    private fun syncDayQueue(
        dates: List<String>,
        changed: LinkedHashSet<String>,
        done: (LinkedHashSet<String>) -> Unit,
    ) {
        if (dates.isEmpty()) { done(changed); return }
        val date = dates.first()
        api.call("sync_day", JSONObject().put("business_date", date)) { result ->
            try {
                if (result.ok && result.json != null) {
                    val day = result.json.optJSONObject("day")
                    if (day != null) {
                        store.saveDay(day)
                        changed += date
                        listener(setOf(date))
                    }
                }
            } catch (_: Throwable) {
                // Keep stale revision; next poll retries this date.
            }
            syncDayQueue(dates.drop(1), changed, done)
        }
    }

    private fun syncBootstrap(
        dates: List<String>,
        changed: LinkedHashSet<String>,
    ) {
        if (dates.isEmpty()) { finish(); return }
        val payload = JSONObject().put("dates", JSONArray().apply { dates.take(45).forEach { put(it) } })
        api.call("sync_bootstrap", payload) { result ->
            try {
                if (result.ok && result.json != null) {
                    val array = result.json.optJSONArray("days") ?: JSONArray()
                    val snapshots = ArrayList<JSONObject>(array.length())
                    val synced = LinkedHashSet<String>()
                    for (i in 0 until array.length()) {
                        val day = array.optJSONObject(i) ?: continue
                        snapshots += day
                        day.optString("business_date").takeIf { it.isNotBlank() }?.let { synced += it }
                    }
                    store.saveDays(snapshots)
                    changed += synced
                    if (synced.isNotEmpty()) listener(synced)
                }
            } catch (_: Throwable) {
                // Keep stale revisions; next poll retries the bootstrap.
            }
            finish()
        }
    }

    private fun finish() {
        val next: Manifest?
        synchronized(lock) {
            next = pending
            pending = null
            inFlight = false
        }
        if (next != null) reconcile(
            next.businessDate,
            next.retentionFloor,
            next.retentionEpoch,
            JSONObject().apply { next.revisions.forEach { (d, r) -> put(d, r) } },
        )
    }

    private fun previousDate(iso: String): String = runCatching {
        val f = java.time.format.DateTimeFormatter.ISO_LOCAL_DATE
        java.time.LocalDate.parse(iso, f).minusDays(1).format(f)
    }.getOrDefault(iso)

    companion object {
        private val SYNC_EXECUTOR = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "pp-operational-sync").apply { isDaemon = true }
        }
    }
}
