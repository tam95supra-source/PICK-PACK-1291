package vn.pickpack1291.app.beta

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteDatabaseLockedException
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.ConcurrentHashMap

/**
 * Device-side operational store.
 *
 * M2 keeps the proven process-wide single SQLiteOpenHelper/rollback-journal safety from Beta17,
 * preserves all existing 45-day day snapshots, and adds a durable canonical mutation outbox plus
 * Service authority/checkpoint metadata. Database upgrade from v1 is additive and never drops the
 * Beta18 snapshot tables.
 */
class OperationalDataStore(context: Context) {
    private val helper = helper(context.applicationContext)

    data class PendingMutation(
        val eventId: String,
        val body: JSONObject,
        val exclusive: Boolean,
        val status: String,
        val attemptCount: Int,
        val queuedAt: Long,
    )

    fun saveDay(snapshot: JSONObject) = withDbLock {
        val date = snapshot.optString("business_date").trim()
        if (date.isBlank()) return@withDbLock
        val copy = JSONObject(snapshot.toString())
        val values = ContentValues().apply {
            put("business_date", date)
            put("day_revision", copy.optLong("day_revision", 0L))
            put("snapshot_json", copy.toString())
            put("saved_at", System.currentTimeMillis())
        }
        val db = writableDb()
        db.beginTransaction()
        try {
            db.insertWithOnConflict("day_snapshot", null, values, SQLiteDatabase.CONFLICT_REPLACE)
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
        MEMORY[date] = copy
    }

    fun saveDays(days: Iterable<JSONObject>) = withDbLock {
        val copies = days.mapNotNull { day ->
            val date = day.optString("business_date").trim()
            if (date.isBlank()) null else date to JSONObject(day.toString())
        }
        if (copies.isEmpty()) return@withDbLock
        val now = System.currentTimeMillis()
        val db = writableDb()
        db.beginTransaction()
        try {
            for ((date, copy) in copies) {
                val values = ContentValues().apply {
                    put("business_date", date)
                    put("day_revision", copy.optLong("day_revision", 0L))
                    put("snapshot_json", copy.toString())
                    put("saved_at", now)
                }
                db.insertWithOnConflict("day_snapshot", null, values, SQLiteDatabase.CONFLICT_REPLACE)
            }
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
        copies.forEach { (date, copy) -> MEMORY[date] = copy }
    }

    fun loadDay(date: String): JSONObject? {
        MEMORY[date]?.let { return JSONObject(it.toString()) }
        return withDbLock {
            readableDb().query("day_snapshot", arrayOf("snapshot_json"), "business_date=?", arrayOf(date), null, null, null, "1").use { c ->
                if (!c.moveToFirst()) return@withDbLock null
                val parsed = runCatching { JSONObject(c.getString(0)) }.getOrNull() ?: return@withDbLock null
                MEMORY[date] = parsed
                JSONObject(parsed.toString())
            }
        }
    }

    fun availableDates(): List<String> = withDbLock {
        val out = ArrayList<String>()
        readableDb().query("day_snapshot", arrayOf("business_date"), null, null, null, null, "business_date DESC").use { c -> while (c.moveToNext()) out += c.getString(0) }
        out
    }

    fun revisions(): Map<String, Long> = withDbLock {
        val out = LinkedHashMap<String, Long>()
        readableDb().query("day_snapshot", arrayOf("business_date", "day_revision"), null, null, null, null, "business_date DESC").use { c -> while (c.moveToNext()) out[c.getString(0)] = c.getLong(1) }
        out
    }

    fun revision(date: String): Long = revisions()[date] ?: 0L

    fun dropBefore(retentionFloor: String) = withDbLock {
        if (retentionFloor.isBlank()) return@withDbLock
        writableDb().delete("day_snapshot", "business_date < ?", arrayOf(retentionFloor))
        MEMORY.keys.filter { it < retentionFloor }.forEach { MEMORY.remove(it) }
    }

    fun dropDatesNotIn(remoteDates: Set<String>, retentionFloor: String) = withDbLock {
        if (retentionFloor.isBlank()) return@withDbLock
        val db = writableDb()
        db.delete("day_snapshot", "business_date < ?", arrayOf(retentionFloor))
        MEMORY.keys.filter { it < retentionFloor }.forEach { MEMORY.remove(it) }
        val local = ArrayList<String>()
        db.query("day_snapshot", arrayOf("business_date"), null, null, null, null, "business_date DESC").use { c -> while (c.moveToNext()) local += c.getString(0) }
        db.beginTransaction()
        try {
            local.filter { it >= retentionFloor && it !in remoteDates }.forEach { date -> db.delete("day_snapshot", "business_date=?", arrayOf(date)); MEMORY.remove(date) }
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }

    fun putMeta(key: String, value: String) = withDbLock {
        val values = ContentValues().apply { put("meta_key", key); put("meta_value", value) }
        writableDb().insertWithOnConflict("sync_meta", null, values, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun meta(key: String): String? = withDbLock {
        readableDb().query("sync_meta", arrayOf("meta_value"), "meta_key=?", arrayOf(key), null, null, null, "1").use { c -> if (c.moveToFirst()) c.getString(0) else null }
    }

    fun saveAuthority(authority: JSONObject) {
        putMeta("authority_epoch", authority.optLong("authority_epoch", 0L).toString())
        putMeta("authority_seq", authority.optLong("authority_seq", 0L).toString())
        putMeta("authority_mode", authority.optString("mode"))
        putMeta("service_generation", authority.optString("service_generation"))
    }

    fun authorityEpoch(): Long = meta("authority_epoch")?.toLongOrNull() ?: 0L
    fun authoritySeq(): Long = meta("authority_seq")?.toLongOrNull() ?: 0L
    fun authorityMode(): String = meta("authority_mode") ?: "OFFLINE_LOCAL"
    fun serviceGeneration(): String = meta("service_generation") ?: ""

    fun enqueueMutation(event: JSONObject, exclusive: Boolean) = withDbLock {
        val eventId = event.optString("event_id").trim()
        require(eventId.isNotBlank()) { "EVENT_ID_REQUIRED" }
        val now = System.currentTimeMillis()
        val values = ContentValues().apply {
            put("event_id", eventId)
            put("body_json", event.toString())
            put("exclusive", if (exclusive) 1 else 0)
            put("status", if (exclusive) "OFFLINE_PROVISIONAL" else "PENDING")
            put("attempt_count", 0)
            put("next_attempt_at", now)
            put("queued_at", now)
            put("updated_at", now)
        }
        writableDb().insertWithOnConflict("mutation_outbox", null, values, SQLiteDatabase.CONFLICT_IGNORE)
    }

    fun pendingMutations(limit: Int = 100): List<PendingMutation> = withDbLock {
        val out = ArrayList<PendingMutation>()
        val now = System.currentTimeMillis().toString()
        readableDb().query(
            "mutation_outbox",
            arrayOf("event_id", "body_json", "exclusive", "status", "attempt_count", "queued_at"),
            "status IN ('PENDING','RETRY','OFFLINE_PROVISIONAL') AND next_attempt_at <= ?",
            arrayOf(now), null, null, "queued_at ASC", limit.coerceIn(1, 500).toString(),
        ).use { c ->
            while (c.moveToNext()) {
                runCatching { JSONObject(c.getString(1)) }.getOrNull()?.let { body ->
                    out += PendingMutation(c.getString(0), body, c.getInt(2) == 1, c.getString(3), c.getInt(4), c.getLong(5))
                }
            }
        }
        out
    }

    fun markMutationSynced(eventId: String) = withDbLock { writableDb().delete("mutation_outbox", "event_id=?", arrayOf(eventId)) }

    fun markMutationRetry(eventId: String, error: String, delayMs: Long) = withDbLock {
        val now = System.currentTimeMillis()
        val v = ContentValues().apply {
            put("status", "RETRY")
            put("attempt_count", "attempt_count + 1")
            put("next_attempt_at", now + delayMs.coerceIn(1_000L, 15 * 60_000L))
            put("last_error", error.take(600))
            put("updated_at", now)
        }
        // ContentValues cannot express attempt_count + 1 as SQL; use one bound execSQL instead.
        writableDb().execSQL(
            "UPDATE mutation_outbox SET status='RETRY',attempt_count=attempt_count+1,next_attempt_at=?,last_error=?,updated_at=? WHERE event_id=?",
            arrayOf(now + delayMs.coerceIn(1_000L, 15 * 60_000L), error.take(600), now, eventId),
        )
    }

    fun markMutationConflict(eventId: String, error: String) = withDbLock {
        val now = System.currentTimeMillis()
        writableDb().execSQL("UPDATE mutation_outbox SET status='CONFLICT',last_error=?,updated_at=? WHERE event_id=?", arrayOf(error.take(1200), now, eventId))
    }

    fun pendingMutationCount(): Int = withDbLock {
        readableDb().rawQuery("SELECT COUNT(*) FROM mutation_outbox WHERE status IN ('PENDING','RETRY','OFFLINE_PROVISIONAL')", null).use { c -> if (c.moveToFirst()) c.getInt(0) else 0 }
    }

    fun conflicts(limit: Int = 100): List<JSONObject> = withDbLock {
        val out = ArrayList<JSONObject>()
        readableDb().query("mutation_outbox", arrayOf("event_id","body_json","last_error","updated_at"), "status='CONFLICT'", null, null, null, "updated_at DESC", limit.coerceIn(1,500).toString()).use { c ->
            while (c.moveToNext()) out += JSONObject().put("event_id",c.getString(0)).put("body",runCatching{JSONObject(c.getString(1))}.getOrNull()).put("error",c.getString(2)).put("updated_at",c.getLong(3))
        }
        out
    }

    fun businessDate(): String = isoDate(Date())
    fun previousBusinessDate(): String = isoDate(Date(System.currentTimeMillis() - 86_400_000L))

    private fun readableDb(): SQLiteDatabase = openWithRetry { helper.readableDatabase }
    private fun writableDb(): SQLiteDatabase = openWithRetry { helper.writableDatabase }

    private fun <T> openWithRetry(block: () -> T): T {
        var last: SQLiteDatabaseLockedException? = null
        repeat(4) { attempt ->
            try { return block() } catch (e: SQLiteDatabaseLockedException) {
                last = e
                if (attempt < 3) Thread.sleep((40L shl attempt).coerceAtMost(320L))
            }
        }
        throw last ?: IllegalStateException("SQLITE_OPEN_FAILED")
    }

    private fun isoDate(date: Date): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).apply { timeZone = TimeZone.getTimeZone(TZ) }.format(date)

    private class DbHelper(context: Context) : SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {
        init { setWriteAheadLoggingEnabled(false) }

        override fun onCreate(db: SQLiteDatabase) { createV1(db); createV2(db) }

        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
            // Owner-lock: never destroy the Beta18 45-day snapshot during Service migration.
            if (oldVersion < 2) createV2(db)
        }

        private fun createV1(db: SQLiteDatabase) {
            db.execSQL("""CREATE TABLE IF NOT EXISTS day_snapshot(
                business_date TEXT PRIMARY KEY NOT NULL,
                day_revision INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL,
                saved_at INTEGER NOT NULL
            )""".trimIndent())
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_day_snapshot_saved ON day_snapshot(saved_at)")
            db.execSQL("""CREATE TABLE IF NOT EXISTS sync_meta(
                meta_key TEXT PRIMARY KEY NOT NULL,
                meta_value TEXT NOT NULL
            )""".trimIndent())
        }

        private fun createV2(db: SQLiteDatabase) {
            db.execSQL("""CREATE TABLE IF NOT EXISTS mutation_outbox(
                event_id TEXT PRIMARY KEY NOT NULL,
                body_json TEXT NOT NULL,
                exclusive INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                next_attempt_at INTEGER NOT NULL,
                queued_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                last_error TEXT
            )""".trimIndent())
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_mutation_outbox_due ON mutation_outbox(status,next_attempt_at,queued_at)")
        }
    }

    companion object {
        private const val DB_NAME = "pp_operational_45d.db"
        private const val DB_VERSION = 2
        private const val TZ = "Asia/Bangkok"
        private val DB_LOCK = Any()
        private val MEMORY = ConcurrentHashMap<String, JSONObject>()
        @Volatile private var HELPER: DbHelper? = null
        private fun helper(context: Context): DbHelper = HELPER ?: synchronized(DB_LOCK) { HELPER ?: DbHelper(context.applicationContext).also { HELPER = it } }
        private inline fun <T> withDbLock(block: () -> T): T = synchronized(DB_LOCK) { block() }
    }
}
