#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt'
OPS = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
WORKER = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/M2OutboxWorker.kt'
MARK = 'S32_LOCAL_HISTORY_FLUSH_FIX'

# ---------------------------------------------------------------------------
# 1) Durable local History ledger. It is intentionally independent from the
#    retry outbox so a rejected/reviewed/confirmed local action remains visible
#    even after outbox retention/pruning. Event ID is the immutable merge key.
# ---------------------------------------------------------------------------
s = STORE.read_text(encoding='utf-8')
if MARK not in s:
    s = s.replace(
        'class OperationalDataStore(context: Context) {\n',
        'class OperationalDataStore(context: Context) {\n    // S32_LOCAL_HISTORY_FLUSH_FIX: persistent local event ledger + canonical merge support.\n',
        1,
    )

    start = s.find('    fun enqueueMutation(event: JSONObject, exclusive: Boolean) = withDbLock {')
    end = s.find('    fun pendingMutations(limit: Int = 100): List<PendingMutation> = withDbLock {', start)
    if start < 0 or end < 0:
        raise SystemExit('S32 enqueue anchors missing')
    enqueue = '''    fun enqueueMutation(event: JSONObject, exclusive: Boolean) = withDbLock {\n        val eventId = event.optString("event_id").trim()\n        require(eventId.isNotBlank()) { "EVENT_ID_REQUIRED" }\n        val now = System.currentTimeMillis()\n        val outboxValues = ContentValues().apply {\n            put("event_id", eventId)\n            put("body_json", event.toString())\n            put("exclusive", if (exclusive) 1 else 0)\n            put("status", "LOCAL_PENDING")\n            put("attempt_count", 0)\n            put("next_attempt_at", now)\n            put("queued_at", now)\n            put("updated_at", now)\n        }\n        val historyValues = ContentValues().apply {\n            put("event_id", eventId)\n            put("body_json", event.toString())\n            put("status", "LOCAL_PENDING")\n            put("last_error", "")\n            put("queued_at", now)\n            put("updated_at", now)\n        }\n        val db = writableDb()\n        db.beginTransaction()\n        try {\n            db.insertWithOnConflict("mutation_outbox", null, outboxValues, SQLiteDatabase.CONFLICT_IGNORE)\n            db.insertWithOnConflict("local_history", null, historyValues, SQLiteDatabase.CONFLICT_IGNORE)\n            db.setTransactionSuccessful()\n        } finally { db.endTransaction() }\n    }\n\n'''
    s = s[:start] + enqueue + s[end:]

    synced_anchor = '    fun markMutationSynced(eventId: String) = markMutationResolved(eventId, "CONFIRMED", "")\n'
    pos = s.find(synced_anchor)
    if pos < 0:
        raise SystemExit('S32 markMutationSynced anchor missing')
    local_history = '''    /** Persistent local actions, including pending/retry/rejected/reviewed rows. */\n    fun localHistory(limit: Int = 500): List<JSONObject> = withDbLock {\n        val out = ArrayList<JSONObject>()\n        readableDb().query(\n            "local_history",\n            arrayOf("event_id", "body_json", "status", "last_error", "queued_at", "updated_at"),\n            null, null, null, null, "queued_at DESC", limit.coerceIn(1, 2000).toString(),\n        ).use { c ->\n            while (c.moveToNext()) {\n                val body = runCatching { JSONObject(c.getString(1)) }.getOrNull() ?: JSONObject()\n                out += JSONObject()\n                    .put("event_id", c.getString(0))\n                    .put("body", body)\n                    .put("status", c.getString(2))\n                    .put("error", c.getString(3) ?: "")\n                    .put("queued_at", c.getLong(4))\n                    .put("updated_at", c.getLong(5))\n            }\n        }\n        out\n    }\n\n'''
    s = s[:pos] + local_history + s[pos:]

    start = s.find('    private fun markMutationResolved(eventId: String, status: String, error: String) = withDbLock {')
    end = s.find('    fun markMutationRetry(eventId: String, error: String, delayMs: Long) = withDbLock {', start)
    if start < 0 or end < 0:
        raise SystemExit('S32 resolved anchors missing')
    resolved = '''    private fun markMutationResolved(eventId: String, status: String, error: String) = withDbLock {\n        val now = System.currentTimeMillis()\n        val db = writableDb()\n        db.beginTransaction()\n        try {\n            db.execSQL(\n                "UPDATE mutation_outbox SET status=?,last_error=?,updated_at=? WHERE event_id=?",\n                arrayOf(status, error.take(1200), now, eventId),\n            )\n            db.execSQL(\n                "UPDATE local_history SET status=?,last_error=?,updated_at=? WHERE event_id=?",\n                arrayOf(status, error.take(1200), now, eventId),\n            )\n            db.setTransactionSuccessful()\n        } finally { db.endTransaction() }\n    }\n\n'''
    s = s[:start] + resolved + s[end:]

    start = s.find('    fun markMutationRetry(eventId: String, error: String, delayMs: Long) = withDbLock {')
    end = s.find('    /** Compatibility mapping: old CONFLICT becomes the owner-visible REVIEW_REQUIRED state. */', start)
    if start < 0 or end < 0:
        raise SystemExit('S32 retry anchors missing')
    retry = '''    fun markMutationRetry(eventId: String, error: String, delayMs: Long) = withDbLock {\n        val now = System.currentTimeMillis()\n        val db = writableDb()\n        db.beginTransaction()\n        try {\n            db.execSQL(\n                "UPDATE mutation_outbox SET status='RETRY',attempt_count=attempt_count+1,next_attempt_at=?,last_error=?,updated_at=? WHERE event_id=?",\n                arrayOf(now + delayMs.coerceIn(1_000L, 15 * 60_000L), error.take(600), now, eventId),\n            )\n            db.execSQL(\n                "UPDATE local_history SET status='RETRY',last_error=?,updated_at=? WHERE event_id=?",\n                arrayOf(error.take(1200), now, eventId),\n            )\n            db.setTransactionSuccessful()\n        } finally { db.endTransaction() }\n    }\n\n'''
    s = s[:start] + retry + s[end:]

    old = '        override fun onCreate(db: SQLiteDatabase) { createV1(db); createV2(db) }\n'
    if old not in s:
        raise SystemExit('S32 onCreate anchor missing')
    s = s.replace(old, '        override fun onCreate(db: SQLiteDatabase) { createV1(db); createV2(db); createV3(db) }\n', 1)

    old = '''        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {\n            // Never drop day_snapshot or mutation_outbox during an installed-Beta upgrade.\n            if (oldVersion < 2) createV2(db)\n        }\n'''
    if old not in s:
        raise SystemExit('S32 onUpgrade anchor missing')
    new = '''        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {\n            // Never drop day_snapshot, mutation_outbox, or local_history during an installed-Beta upgrade.\n            if (oldVersion < 2) createV2(db)\n            if (oldVersion < 3) createV3(db)\n        }\n'''
    s = s.replace(old, new, 1)

    companion_pos = s.find('\n    companion object {')
    if companion_pos < 0:
        raise SystemExit('S32 companion anchor missing')
    helper_close = s.rfind('\n    }', 0, companion_pos)
    if helper_close < 0:
        raise SystemExit('S32 DbHelper close anchor missing')
    create_v3 = '''\n        private fun createV3(db: SQLiteDatabase) {\n            db.execSQL("""CREATE TABLE IF NOT EXISTS local_history(\n                event_id TEXT PRIMARY KEY NOT NULL,\n                body_json TEXT NOT NULL,\n                status TEXT NOT NULL,\n                last_error TEXT,\n                queued_at INTEGER NOT NULL,\n                updated_at INTEGER NOT NULL\n            )""".trimIndent())\n            db.execSQL("CREATE INDEX IF NOT EXISTS idx_local_history_queued ON local_history(queued_at DESC)")\n            // Preserve all already-existing outbox rows when upgrading Beta27 -> Beta28.\n            db.execSQL("""INSERT OR IGNORE INTO local_history(event_id,body_json,status,last_error,queued_at,updated_at)\n                SELECT event_id,body_json,status,COALESCE(last_error,''),queued_at,updated_at FROM mutation_outbox\n            """.trimIndent())\n        }\n'''
    s = s[:helper_close] + create_v3 + s[helper_close:]

    if 'private const val DB_VERSION = 2' not in s:
        raise SystemExit('S32 DB_VERSION anchor missing')
    s = s.replace('private const val DB_VERSION = 2', 'private const val DB_VERSION = 3', 1)
    STORE.write_text(s, encoding='utf-8')

# ---------------------------------------------------------------------------
# 2) History UI = canonical local snapshots UNION durable local history,
#    deduped by immutable Event ID. Local rejected/reviewed rows never vanish.
# ---------------------------------------------------------------------------
s = OPS.read_text(encoding='utf-8')
if MARK not in s:
    hs = s.find('    private fun historyScreen(){')
    he = s.find('    private fun formatRate(', hs)
    if hs < 0 or he < 0:
        # Some generated variants place syncScreen immediately after history.
        he = s.find('    private fun syncScreen(){', hs)
    if hs < 0 or he < 0:
        raise SystemExit('S32 History anchors missing')
    history = r'''    // S32_LOCAL_HISTORY_FLUSH_FIX: History is local-first and never depends on remote ACK to exist.
    private fun historyScreen(){
        module="HISTORY";screenState="HISTORY";historyDetailMnv="";historyDetailName=""
        val root=baseRoot("LỊCH SỬ");val body=body();val box=column(bg)
        fun friendly(type:String,label:String):String=when(type.uppercase()){
            "ATTENDANCE_ENTER","ENTER"->"Vào ca";"ATTENDANCE_EXIT","EXIT"->"Ra ca";"RESOURCE_CHANGE"->"Đổi tài nguyên";
            "LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"ADMIN_AUDIT"->"Thao tác quản trị";
            "MASTER_STAFF_UPSERT"->"Cập nhật nhân sự";"MASTER_STAFF_DELETE"->"Xóa nhân sự";"ACCOUNT_UPSERT"->"Tạo / sửa tài khoản";
            "ACCOUNT_STATUS"->"Đổi trạng thái tài khoản";"ACCOUNT_EMAIL"->"Đổi email tài khoản";"ACCOUNT_PASSWORD"->"Đổi mật khẩu";
            "FALLBACK_RECONCILED_DUPLICATE"->"Đối soát dữ liệu dự phòng";else->label.ifBlank{type.ifBlank{"Thao tác"}}
        }
        fun eventTypeForAction(action:String):String=when(action){
            "enter"->"ATTENDANCE_ENTER";"exit"->"ATTENDANCE_EXIT";"resource_change"->"RESOURCE_CHANGE";
            "labor_start"->"LABOR_START";"labor_finish"->"LABOR_FINISH";"admin_audit"->"ADMIN_AUDIT";else->action.uppercase()
        }
        fun statusLabel(status:String):String=when(status){
            "LOCAL_PENDING","PENDING","OFFLINE_PROVISIONAL"->"Chờ đồng bộ";"RETRY"->"Chờ gửi lại";"CONFIRMED"->"Đã đồng bộ";
            "REJECTED"->"Bị từ chối";"REVIEW_REQUIRED","CONFLICT"->"Cần kiểm tra";else->status.ifBlank{"Đã đồng bộ"}
        }
        val dates=operationalStore.availableDates().take(7)
        val merged=LinkedHashMap<String,JSONObject>()
        for(date in dates){
            val day=operationalStore.loadDay(date)?:continue
            val events=day.optJSONArray("events")?:JSONArray()
            for(i in 0 until events.length()){
                val e=events.optJSONObject(i)?:continue
                val copy=JSONObject(e.toString()).put("cache_business_date",date).put("history_source","CANONICAL_CACHE")
                val id=copy.optString("event_id").ifBlank{"canonical:$date:$i:${copy.optString("at_iso").ifBlank{copy.optString("at")}}"}
                merged[id]=copy
            }
        }
        val localRows=operationalStore.localHistory(1000)
        for(local in localRows){
            val eventId=local.optString("event_id")
            if(eventId.isBlank())continue
            val bodyJson=local.optJSONObject("body")?:JSONObject()
            val payload=bodyJson.optJSONObject("payload")?:bodyJson
            val existing=merged[eventId]
            if(existing!=null){
                existing.put("local_status",local.optString("status"))
                    .put("local_error",local.optString("error"))
                    .put("local_queued_at",local.optLong("queued_at",0L))
                continue
            }
            val action=bodyJson.optString("action")
            val detailParts=mutableListOf<String>()
            listOf("shift","work_choice","pda_serial","user_pick","pack_table","user_pack","labor_type","time_marker").forEach{key->
                val v=payload.optString(key).trim();if(v.isNotBlank())detailParts.add("$key=$v")
            }
            val localItem=JSONObject()
                .put("event_id",eventId)
                .put("event_type",eventTypeForAction(action))
                .put("label",friendly(eventTypeForAction(action),action))
                .put("mnv",payload.optString("mnv").ifBlank{bodyJson.optString("target_id")})
                .put("full_name",payload.optString("full_name").ifBlank{bodyJson.optString("target_label")})
                .put("actor",payload.optString("actor").ifBlank{payload.optString("login_id")}.ifBlank{"Thiết bị này"})
                .put("detail",bodyJson.optString("detail").ifBlank{detailParts.joinToString(" • ")})
                .put("history_source","LOCAL_PDA")
                .put("local_status",local.optString("status"))
                .put("local_error",local.optString("error"))
                .put("local_queued_at",local.optLong("queued_at",0L))
            merged[eventId]=localItem
        }
        val all=merged.values.toMutableList()
        all.sortByDescending{e->
            val localAt=e.optLong("local_queued_at",0L)
            if(localAt>0L)localAt else runCatching{java.time.Instant.parse(e.optString("at_iso").ifBlank{e.optString("at")}).toEpochMilli()}.getOrDefault(0L)
        }
        val top=row(bg)
        top.addView(metric("Thao tác",all.size.toString(),navy),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)})
        top.addView(metric("Local PDA",localRows.size.toString(),teal),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)})
        body.addView(top,matchWrap());body.addView(gap(6))
        body.addView(info("Lịch sử hợp nhất ngay dữ liệu local-first trên PDA với snapshot canonical Service/Google theo Event ID. Pending, bị từ chối hoặc cần kiểm tra vẫn được lưu và hiển thị; không cần chờ đồng bộ để xuất hiện."));body.addView(gap(8))
        if(all.isEmpty())box.addView(info("Chưa có lịch sử trong bộ nhớ PDA. Hệ thống vẫn đối chiếu snapshot nền khi có mạng."))
        val limit=kotlin.math.min(all.size,500)
        for(i in 0 until limit){
            val e=all[i];val mnv=e.optString("mnv");val name=e.optString("full_name");val actor=e.optString("actor").ifBlank{"Hệ thống"}
            val label=friendly(e.optString("event_type"),e.optString("label"));val detail=e.optString("detail").trim();val date=e.optString("cache_business_date")
            val localAt=e.optLong("local_queued_at",0L);val at=if(localAt>0L)java.text.SimpleDateFormat("dd/MM HH:mm:ss",java.util.Locale("vi","VN")).format(java.util.Date(localAt)) else formatIso(e.optString("at_iso").ifBlank{e.optString("at")})
            val seq=e.optLong("authority_seq",0L);val localStatus=e.optString("local_status");val localError=e.optString("local_error").trim()
            val title=if(mnv.isNotBlank())"$label • $mnv${if(name.isBlank())"" else " • $name"}" else label
            val sub=buildString{
                append("$at • Người thực hiện: $actor")
                if(localStatus.isNotBlank())append("\nTrạng thái: ${statusLabel(localStatus)}")
                if(localError.isNotBlank())append("\nKết quả/ lỗi: ${localError.take(220)}")
                if(detail.isNotBlank())append("\nChi tiết: $detail")
                if(date.isNotBlank())append("\nPhiên dữ liệu: $date")
                if(seq>0)append(" • revision $seq")
                append("\nEvent ID: ${e.optString("event_id")}")
            }
            box.addView(listCard(title,sub));box.addView(gap(5))
        }
        body.addView(box,matchWrap())
        foregroundSync.requestSync()
        attach(root,body)
    }

'''
    s = s[:hs] + history + s[he:]
    OPS.write_text(s, encoding='utf-8')

# ---------------------------------------------------------------------------
# 3) Separate mutation flush from snapshot catch-up. A new mutation may replace
#    a backoff-delayed flush job immediately; catch-up remains coalesced and can
#    never hold the business outbox hostage.
# ---------------------------------------------------------------------------
worker = r'''package vn.pickpack1291.app.beta

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/** S32_LOCAL_HISTORY_FLUSH_FIX: mutation flush is independent from canonical catch-up. */
class M2OutboxFlushWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {
    override fun doWork(): Result = try {
        if (M2ServiceTransport(applicationContext).flushOutbox()) Result.success() else Result.retry()
    } catch (_: Throwable) { Result.retry() }
}

/** Snapshot/master reconciliation is useful but must never gate local mutation delivery. */
class M2CatchUpWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {
    override fun doWork(): Result = try {
        val caughtUp = M2BackgroundSync.catchUp(applicationContext)
        M2PushRegistration.flush(applicationContext)
        if (caughtUp) Result.success() else Result.retry()
    } catch (_: Throwable) { Result.retry() }
}

object M2WorkScheduler {
    private const val FLUSH_UNIQUE = "pick-pack-1291-m2-outbox-flush"
    private const val CATCHUP_UNIQUE = "pick-pack-1291-m2-catchup"

    fun schedule(context: Context) {
        val app = context.applicationContext
        val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        // REPLACE only the flush job: a newly queued Event ID must not sit behind stale backoff.
        // Event IDs are immutable/idempotent, so a replacement cannot create a second business event.
        val flush = OneTimeWorkRequestBuilder<M2OutboxFlushWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(app).enqueueUniqueWork(FLUSH_UNIQUE, ExistingWorkPolicy.REPLACE, flush)

        // Catch-up is coalesced separately. Its retry/backoff is no longer coupled to outbox delivery.
        val catchUp = OneTimeWorkRequestBuilder<M2CatchUpWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(app).enqueueUniqueWork(CATCHUP_UNIQUE, ExistingWorkPolicy.KEEP, catchUp)
    }
}

object M2ConnectivityMonitor {
    private val started = AtomicBoolean(false)
    fun start(context: Context) {
        if (!started.compareAndSet(false, true)) return
        val app = context.applicationContext
        val cm = app.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        runCatching {
            cm.registerDefaultNetworkCallback(object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) { M2WorkScheduler.schedule(app) }
            })
        }.onFailure { started.set(false) }
    }
}
'''
WORKER.write_text(worker, encoding='utf-8')

# Contract guards: fail the build transform rather than silently shipping a partial S32.
store = STORE.read_text(encoding='utf-8')
ops = OPS.read_text(encoding='utf-8')
w = WORKER.read_text(encoding='utf-8')
assert MARK in store and 'CREATE TABLE IF NOT EXISTS local_history' in store and 'fun localHistory(' in store
assert MARK in ops and 'operationalStore.localHistory(1000)' in ops and 'Event ID:' in ops
assert MARK in w and 'class M2OutboxFlushWorker' in w and 'class M2CatchUpWorker' in w
assert 'ExistingWorkPolicy.REPLACE' in w and 'flushed && caughtUp' not in w
print('Applied S32 durable local History + independent immediate outbox flush')
