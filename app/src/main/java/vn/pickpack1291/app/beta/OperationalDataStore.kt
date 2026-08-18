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
 * Device-side operational snapshot store.
 *
 * Google Sheets remains authoritative. Every OperationalDataStore instance shares one process-wide
 * SQLiteOpenHelper/connection pool. This is required on Android 11 PDA builds: opening two helpers
 * for the same database can race while SQLite negotiates journal_mode and throw SQLITE_BUSY.
 *
 * Each cached row is a complete snapshot for one business date at a server day_revision. Replacing
 * one date is atomic, so report/history readers never observe a half-updated day.
 */
class OperationalDataStore(context: Context) {
    private val helper = helper(context.applicationContext)

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
        } finally {
            db.endTransaction()
        }
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
        } finally {
            db.endTransaction()
        }
        copies.forEach { (date, copy) -> MEMORY[date] = copy }
    }

    fun loadDay(date: String): JSONObject? {
        MEMORY[date]?.let { return JSONObject(it.toString()) }
        return withDbLock {
            readableDb().query(
                "day_snapshot",
                arrayOf("snapshot_json"),
                "business_date=?",
                arrayOf(date),
                null,
                null,
                null,
                "1",
            ).use { c ->
                if (!c.moveToFirst()) return@withDbLock null
                val parsed = runCatching { JSONObject(c.getString(0)) }.getOrNull() ?: return@withDbLock null
                MEMORY[date] = parsed
                JSONObject(parsed.toString())
            }
        }
    }

    fun availableDates(): List<String> = withDbLock {
        val out = ArrayList<String>()
        readableDb().query(
            "day_snapshot",
            arrayOf("business_date"),
            null,
            null,
            null,
            null,
            "business_date DESC",
        ).use { c -> while (c.moveToNext()) out += c.getString(0) }
        out
    }

    fun revisions(): Map<String, Long> = withDbLock {
        val out = LinkedHashMap<String, Long>()
        readableDb().query(
            "day_snapshot",
            arrayOf("business_date", "day_revision"),
            null,
            null,
            null,
            null,
            "business_date DESC",
        ).use { c -> while (c.moveToNext()) out[c.getString(0)] = c.getLong(1) }
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
        db.query(
            "day_snapshot",
            arrayOf("business_date"),
            null,
            null,
            null,
            null,
            "business_date DESC",
        ).use { c -> while (c.moveToNext()) local += c.getString(0) }

        db.beginTransaction()
        try {
            local.filter { it >= retentionFloor && it !in remoteDates }.forEach { date ->
                db.delete("day_snapshot", "business_date=?", arrayOf(date))
                MEMORY.remove(date)
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun putMeta(key: String, value: String) = withDbLock {
        val values = ContentValues().apply { put("meta_key", key); put("meta_value", value) }
        writableDb().insertWithOnConflict("sync_meta", null, values, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun meta(key: String): String? = withDbLock {
        readableDb().query("sync_meta", arrayOf("meta_value"), "meta_key=?", arrayOf(key), null, null, null, "1").use { c ->
            if (c.moveToFirst()) c.getString(0) else null
        }
    }

    fun businessDate(): String = isoDate(Date())

    fun previousBusinessDate(): String = isoDate(Date(System.currentTimeMillis() - 86_400_000L))

    private fun readableDb(): SQLiteDatabase = openWithRetry { helper.readableDatabase }
    private fun writableDb(): SQLiteDatabase = openWithRetry { helper.writableDatabase }

    private fun <T> openWithRetry(block: () -> T): T {
        var last: SQLiteDatabaseLockedException? = null
        repeat(4) { attempt ->
            try {
                return block()
            } catch (e: SQLiteDatabaseLockedException) {
                last = e
                if (attempt < 3) Thread.sleep((40L shl attempt).coerceAtMost(320L))
            }
        }
        throw last ?: IllegalStateException("SQLITE_OPEN_FAILED")
    }

    private fun isoDate(date: Date): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).apply {
        timeZone = TimeZone.getTimeZone(TZ)
    }.format(date)

    private class DbHelper(context: Context) : SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {
        init {
            // Explicitly keep one rollback-journal connection pool. Some Android 11 PDA SQLite builds
            // throw SQLITE_BUSY when multiple helpers negotiate PRAGMA journal_mode concurrently.
            setWriteAheadLoggingEnabled(false)
        }

        override fun onCreate(db: SQLiteDatabase) {
            db.execSQL(
                """CREATE TABLE day_snapshot(
                    business_date TEXT PRIMARY KEY NOT NULL,
                    day_revision INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    saved_at INTEGER NOT NULL
                )""".trimIndent()
            )
            db.execSQL("CREATE INDEX idx_day_snapshot_saved ON day_snapshot(saved_at)")
            db.execSQL(
                """CREATE TABLE sync_meta(
                    meta_key TEXT PRIMARY KEY NOT NULL,
                    meta_value TEXT NOT NULL
                )""".trimIndent()
            )
        }

        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
            db.execSQL("DROP TABLE IF EXISTS day_snapshot")
            db.execSQL("DROP TABLE IF EXISTS sync_meta")
            onCreate(db)
        }
    }

    companion object {
        private const val DB_NAME = "pp_operational_45d.db"
        private const val DB_VERSION = 1
        private const val TZ = "Asia/Bangkok"
        private val DB_LOCK = Any()
        private val MEMORY = ConcurrentHashMap<String, JSONObject>()
        @Volatile private var HELPER: DbHelper? = null

        private fun helper(context: Context): DbHelper = HELPER ?: synchronized(DB_LOCK) {
            HELPER ?: DbHelper(context.applicationContext).also { HELPER = it }
        }

        private inline fun <T> withDbLock(block: () -> T): T = synchronized(DB_LOCK) { block() }
    }
}
