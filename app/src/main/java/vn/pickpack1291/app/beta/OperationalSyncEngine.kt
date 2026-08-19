package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Revision-driven synchronizer for the exact Service-provided seven-business-session window N..N-6.
 *
 * The Service business sequence is authoritative. No calendar-day subtraction is used to invent
 * N-1/N-2 dates. The local store prunes only day snapshots; durable pending mutations are separate
 * and survive retention changes/upgrades.
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
        if (businessDate.isBlank()) return
        val revisions = LinkedHashMap<String, Long>()
        val keys = dayRevisions.keys()
        while (keys.hasNext()) {
            val date = keys.next().trim()
            if (date.isNotBlank()) revisions[date] = dayRevisions.optLong(date, 0L)
        }
        // Contract lock: PDA operational cache is the latest seven business sessions, never more.
        val exactWindow = revisions.entries
            .sortedByDescending { it.key }
            .take(7)
            .associateTo(LinkedHashMap()) { it.key to it.value }
        if (exactWindow.isEmpty()) return
        val canonicalBusinessDate = if (businessDate in exactWindow) businessDate else exactWindow.keys.first()
        val canonicalFloor = exactWindow.keys.last()
        val manifest = Manifest(canonicalBusinessDate, canonicalFloor, retentionEpoch, exactWindow)
        synchronized(lock) {
            if (inFlight) {
                pending = manifest
                return
            }
            inFlight = true
        }
        SYNC_EXECUTOR.execute { process(manifest) }
    }

    private fun process(manifest: Manifest) {
        try {
            store.applyBusinessWindow(manifest.revisions.keys.toList(), manifest.retentionEpoch)
            store.putMeta("business_date", manifest.businessDate)
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
                // Use the first two actual Service business dates, not calendar today-minus-one.
                val hot = manifest.revisions.keys.sortedDescending().take(2).filter { it in missingOrChanged }
                syncDayQueue(hot, linkedSetOf()) { changed ->
                    val stillMissing = manifest.revisions
                        .filter { (date, rev) -> store.revision(date) != rev }
                        .keys
                        .sortedDescending()
                    if (stillMissing.isEmpty()) finish() else syncBootstrap(stillMissing, changed)
                }
                return
            }

            if (missingOrChanged.size <= 2) {
                syncDayQueue(missingOrChanged, linkedSetOf()) { finish() }
            } else {
                syncBootstrap(missingOrChanged, linkedSetOf())
            }
        } catch (_: Throwable) {
            // Event/reconnect/manual triggers retry later; never crash the operational UI.
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
        SyncDirectionTracker.beginDownload()
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
                syncDayQueue(dates.drop(1), changed, done)
            } catch (_: Throwable) {
                syncDayQueue(dates.drop(1), changed, done)
            } finally {
                SyncDirectionTracker.endDownload()
            }
        }
    }

    private fun syncBootstrap(
        dates: List<String>,
        changed: LinkedHashSet<String>,
    ) {
        if (dates.isEmpty()) { finish(); return }
        val payload = JSONObject().put("dates", JSONArray().apply { dates.take(7).forEach { put(it) } })
        SyncDirectionTracker.beginDownload()
        api.call("sync_bootstrap", payload) { result ->
            try {
                if (result.ok && result.json != null) {
                    val array = result.json.optJSONArray("days") ?: JSONArray()
                    val snapshots = ArrayList<JSONObject>(array.length())
                    val synced = LinkedHashSet<String>()
                    for (i in 0 until array.length()) {
                        val day = array.optJSONObject(i) ?: continue
                        val date = day.optString("business_date")
                        if (date in dates) {
                            snapshots += day
                            synced += date
                        }
                    }
                    store.saveDays(snapshots)
                    changed += synced
                    if (synced.isNotEmpty()) listener(synced)
                }
                finish()
            } catch (_: Throwable) {
                finish()
            } finally {
                SyncDirectionTracker.endDownload()
            }
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

    companion object {
        private val SYNC_EXECUTOR = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "pp-operational-sync").apply { isDaemon = true }
        }
    }
}
