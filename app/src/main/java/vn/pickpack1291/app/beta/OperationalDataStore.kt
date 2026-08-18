package vn.pickpack1291.app.beta

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
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
 * Google Sheets remains authoritative. Each cached row is a complete immutable snapshot for one
 * business date at a server day_revision. Replacing one date is atomic, so report/history readers
 * never observe a half-updated day.
 */
class OperationalDataStore(context: Context) : SQLiteOpenHelper(
    context.applicationContext,
    DB_NAME,
    null,
    DB_VERSION,
) {
    private val appContext = context.applicationContext
    private val memory = ConcurrentHashMap<String, JSONObject>()

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

    @Synchronized
    fun saveDay(snapshot: JSONObject) {
        val date = snapshot.optString("business_date").trim()
        if (date.isBlank()) return
        val revision = snapshot.optLong("day_revision", 0L)
        val copy = JSONObject(snapshot.toString())
        val values = ContentValues().apply {
            put("business_date", date)
            put("day_revision", revision)
            put("snapshot_json", copy.toString())
            put("saved_at", System.currentTimeMillis())
        }
        writableDatabase.beginTransaction()
        try {
            writableDatabase.insertWithOnConflict("day_snapshot", null, values, SQLiteDatabase.CONFLICT_REPLACE)
            writableDatabase.setTransactionSuccessful()
        } finally {
            writableDatabase.endTransaction()
        }
        memory[date] = copy
    }

    @Synchronized
    fun saveDays(days: Iterable<JSONObject>) {
        val copies = days.mapNotNull { day ->
            val date = day.optString("business_date").trim()
            if (date.isBlank()) null else date to JSONObject(day.toString())
        }
        if (copies.isEmpty()) return
        val now = System.currentTimeMillis()
        val db = writableDatabase
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
        copies.forEach { (date, copy) -> memory[date] = copy }
    }

    fun loadDay(date: String): JSONObject? {
        memory[date]?.let { return JSONObject(it.toString()) }
        readableDatabase.query(
            "day_snapshot",
            arrayOf("snapshot_json"),
            "business_date=?",
            arrayOf(date),
            null,
            null,
            null,
            "1",
        ).use { c ->
            if (!c.moveToFirst()) return null
            val parsed = runCatching { JSONObject(c.getString(0)) }.getOrNull() ?: return null
            memory[date] = parsed
            return JSONObject(parsed.toString())
        }
    }

    fun availableDates(): List<String> {
        val out = ArrayList<String>()
        readableDatabase.query(
            "day_snapshot",
            arrayOf("business_date"),
            null,
            null,
            null,
            null,
            "business_date DESC",
        ).use { c -> while (c.moveToNext()) out += c.getString(0) }
        return out
    }

    fun revisions(): Map<String, Long> {
        val out = LinkedHashMap<String, Long>()
        readableDatabase.query(
            "day_snapshot",
            arrayOf("business_date", "day_revision"),
            null,
            null,
            null,
            null,
            "business_date DESC",
        ).use { c -> while (c.moveToNext()) out[c.getString(0)] = c.getLong(1) }
        return out
    }

    fun revision(date: String): Long = revisions()[date] ?: 0L

    @Synchronized
    fun dropBefore(retentionFloor: String) {
        if (retentionFloor.isBlank()) return
        writableDatabase.delete("day_snapshot", "business_date < ?", arrayOf(retentionFloor))
        memory.keys.filter { it < retentionFloor }.forEach { memory.remove(it) }
    }

    @Synchronized
    fun dropDatesNotIn(remoteDates: Set<String>, retentionFloor: String) {
        dropBefore(retentionFloor)
        val local = availableDates()
        val db = writableDatabase
        db.beginTransaction()
        try {
            local.filter { it >= retentionFloor && it !in remoteDates }.forEach { date ->
                db.delete("day_snapshot", "business_date=?", arrayOf(date))
                memory.remove(date)
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun putMeta(key: String, value: String) {
        val values = ContentValues().apply { put("meta_key", key); put("meta_value", value) }
        writableDatabase.insertWithOnConflict("sync_meta", null, values, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun meta(key: String): String? {
        readableDatabase.query("sync_meta", arrayOf("meta_value"), "meta_key=?", arrayOf(key), null, null, null, "1").use { c ->
            return if (c.moveToFirst()) c.getString(0) else null
        }
    }

    fun businessDate(): String = isoDate(Date())

    fun previousBusinessDate(): String = isoDate(Date(System.currentTimeMillis() - 86_400_000L))

    private fun isoDate(date: Date): String = SimpleDateFormat("yyyy-MM-dd", Locale.US).apply {
        timeZone = TimeZone.getTimeZone(TZ)
    }.format(date)

    companion object {
        private const val DB_NAME = "pp_operational_45d.db"
        private const val DB_VERSION = 1
        private const val TZ = "Asia/Bangkok"
    }
}
