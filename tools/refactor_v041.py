from pathlib import Path
import re


def write(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def replace(path, old, new, count=1):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if old not in s:
        raise SystemExit(f"missing literal in {path}: {old[:100]!r}")
    p.write_text(s.replace(old, new, count), encoding="utf-8")


def regex_replace(path, pattern, repl):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    ns, n = re.subn(pattern, repl, s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"pattern count {n} in {path}: {pattern[:100]}")
    p.write_text(ns, encoding="utf-8")


# ---------------- Google Apps Script: cached masters, shift-aware PACK, exact log folders ----------------
gas = "google-apps-script/PICK_PACK_API.gs"
replace(
    gas,
    "  RELEASES: 'https://api.github.com/repos/tam95supra-source/pick-pack-1291/releases?per_page=30'\n",
    "  RELEASES: 'https://api.github.com/repos/tam95supra-source/pick-pack-1291/releases?per_page=30',\n"
    "  LOG_MANUAL_FOLDER_ID: '1jSPHbj3csKiRNyHtTp87Ed10m2VyFxXU',\n"
    "  LOG_CRASH_FOLDER_ID: '1tfEaiyhOScH0ucJGSfSDXF1Qq4tkCl0n',\n"
    "  LOG_ANDROID_FOLDER_ID: '1AN_cEcbbdVO0dory_01hkJhQ1dhlO7Vb'\n",
)
replace(
    gas,
    "    if (action === 'master_options') return ppJson_(ppMasterOptions_(body));\n",
    "    if (action === 'master_options') return ppJson_(ppMasterOptions_(body));\n"
    "    if (action === 'master_snapshot') return ppJson_(ppMasterSnapshot_());\n",
)

master_block = r'''function ppMasterRevision_() {
  return Number(PropertiesService.getScriptProperties().getProperty('PP_MASTER_REVISION') || '1');
}
function ppBumpMasterRevision_() {
  const p=PropertiesService.getScriptProperties();
  const n=Number(p.getProperty('PP_MASTER_REVISION') || '1')+1;
  p.setProperty('PP_MASTER_REVISION',String(n));
  return n;
}
function onEdit(e) {
  try {
    if(!e || !e.range) return;
    const name=e.range.getSheet().getName();
    const masters=[PP.CATALOG,PP.STAFF,PP.PDA,PP.PICK,PP.TABLE,PP.PACK,PP.ADMIN];
    if(masters.indexOf(name)>=0){ ppBumpMasterRevision_(); ppBumpRevision_(); }
    else if(name===PP.RA || name===PP.LABOR){ ppBumpRevision_(); }
  } catch(err) { console.error('onEdit '+String(err)); }
}
function ppPackShift_(label,table) {
  const f=ppFold_(label);
  if(f.indexOf('CA 1-')===0) return 'Ca 1';
  if(f.indexOf('CA 2-')===0) return 'Ca 2';
  if(f.indexOf('HP-')===0 || ppFold_(table)==='HP') return 'Ca HC';
  return '';
}
function ppMasterSnapshotData_() {
  const rev=ppMasterRevision_(), cache=CacheService.getScriptCache(), key='PP_MASTER_V4_'+rev;
  const cached=cache.get(key);
  if(cached){ try { return JSON.parse(cached); } catch(_) {} }
  const staff=ppObjects_(PP.STAFF).map(function(r){return {
    mnv:r['Mã nhân viên']||'',full_name:r['Họ và tên']||'',phone:r['Số điện thoại']||'',main_position:r['Vị trí chính']||'',
    supplier:r['Nhà cung cấp']||'',department:r['Bộ phận']||'',site:r['Site']||'',warehouse:r['Kho']||'',start_date:r['Ngày bắt đầu làm việc']||'',note:r['Ghi chú']||''
  };}).filter(function(x){return !!x.mnv;});
  const pdas=ppObjects_(PP.PDA).filter(function(r){return ppAvailable_(r['Tình trạng']);}).map(function(r){return {serial:r['Seri PDA'],last5:r['5 số cuối Seri']||'',status:r['Tình trạng']||''};}).filter(function(x){return !!x.serial;});
  const userPicks=ppObjects_(PP.PICK).filter(function(r){return ppAvailable_(r['Tình trạng']);}).map(function(r){return r['User Pick'];}).filter(Boolean);
  const tables=ppObjects_(PP.TABLE).filter(function(r){return ppAvailable_(r['Tình trạng']);}).map(function(r){return r['Tên bàn pack'];}).filter(Boolean);
  const tableSet=new Set(tables), warnings=[], packs=[], seen={};
  ppObjects_(PP.PACK).filter(function(r){return ppAvailable_(r['Tình trạng']);}).forEach(function(r){
    const table=String(r['Tên bàn pack']||'').trim(), label=String(r['User pack']||'').trim(), userPack=String(r['User Pack']||'').trim();
    if(!table || !userPack) return;
    if(!tableSet.has(table)){ warnings.push('PACK_TABLE_MISSING:'+table+':'+label); return; }
    const shift=ppPackShift_(label,table); if(!shift){ warnings.push('PACK_SHIFT_UNKNOWN:'+table+':'+label); return; }
    const k=shift+'|'+userPack; if(seen[k]){ warnings.push('USER_PACK_DUPLICATE:'+k+':'+seen[k]+':'+table); return; }
    seen[k]=table; packs.push({table:table,label:label,user_pack:userPack,shift:shift});
  });
  const rows=ppObjects_(PP.CATALOG), labor=[], markers=[];
  rows.forEach(function(r){ const a=r['CÔNG NHẬT_Thông tin công nhật'],b=r['CÔNG NHẬT_Mốc thời gian']; if(a&&labor.indexOf(a)<0)labor.push(a);if(b&&markers.indexOf(b)<0)markers.push(b); });
  const out={master_revision:rev,staff:staff,pdas:pdas,user_picks:userPicks,pack_tables:tables,pack_bundles:packs,labor_types:labor,time_markers:markers,config_warnings:warnings};
  const raw=JSON.stringify(out); if(raw.length<95000) cache.put(key,raw,600);
  return out;
}
function ppMasterSnapshot_() { const s=ppMasterSnapshotData_(); return Object.assign({ok:true},s); }
function ppLookupStaff_(mnv) { return ppMasterSnapshotData_().staff.find(function(x){return String(x.mnv)===String(mnv);})||null; }
function ppMasterData_() { const s=ppMasterSnapshotData_(); return {pdas:s.pdas,userPicks:s.user_picks,packs:s.pack_bundles}; }
function ppCatalog_() { const s=ppMasterSnapshotData_(); return {labor_types:s.labor_types,time_markers:s.time_markers}; }

'''
regex_replace(gas, r"function ppLookupStaff_\(mnv\) \{.*?function ppRaRows_\(\) \{", master_block + "function ppRaRows_() {")

options_block = r'''function ppMasterOptions_(body) {
  const mnv=String(body.mnv||'').trim(), masters=ppMasterData_(), busy=ppBusyResources_(mnv), used=ppConsumption_(ppBusinessVisible_(),mnv), sessions=ppSessionMap_(ppBusinessVisible_());
  const catalog=ppCatalog_();
  return {ok:true,business_date:ppBusinessIso_(),master_revision:ppMasterRevision_(),
    pdas:masters.pdas.filter(function(x){return !busy.has('PDA|'+x.serial);}),
    user_picks:masters.userPicks.filter(function(x){return !busy.has('USER_PICK|'+x) && !used.picks.has(x);}),
    pack_tables:masters.packs.filter(function(x){return !busy.has('PACK_TABLE|'+x.table) && !busy.has('USER_PACK|'+x.user_pack) && !used.packs.has(x.user_pack);}),
    current:sessions[mnv]||null,labor_types:catalog.labor_types,time_markers:catalog.time_markers,config_warnings:ppMasterSnapshotData_().config_warnings};
}

function ppValidateResources_(mnv, choice, body, shift) {
  const masters=ppMasterData_(), busy=ppBusyResources_(mnv), used=ppConsumption_(ppBusinessVisible_(),mnv);
  let pda=null,userPick=null,packTable=null,userPack=null;
  if(choice==='PICK') {
    pda=String(body.pda_serial||'').trim()||null; userPick=String(body.user_pick||'').trim()||null;
    if(!pda || !masters.pdas.some(function(x){return x.serial===pda;})) throw new Error('PDA_INVALID');
    if(!userPick) throw new Error('USER_PICK_REQUIRED');
    if(busy.has('PDA|'+pda)) throw new Error('PP_RESOURCE_CONFLICT:PDA');
    if(masters.userPicks.indexOf(userPick)<0) throw new Error('USER_PICK_INVALID');
    if(busy.has('USER_PICK|'+userPick) || used.picks.has(userPick)) throw new Error('PP_USER_PICK_USED_TODAY');
  } else if(choice==='PACK') {
    packTable=String(body.pack_table||'').trim()||null;
    const bundle=masters.packs.find(function(x){return x.table===packTable && x.shift===shift;});
    if(!bundle) throw new Error('PACK_BUNDLE_INVALID:'+String(shift||''));
    userPack=bundle.user_pack;
    if(busy.has('PACK_TABLE|'+packTable) || busy.has('USER_PACK|'+userPack)) throw new Error('PP_RESOURCE_CONFLICT:PACK');
    if(used.packs.has(userPack)) throw new Error('PP_USER_PACK_USED_TODAY');
  }
  return {pda:pda,userPick:userPick,packTable:packTable,userPack:userPack};
}
'''
regex_replace(gas, r"function ppMasterOptions_\(body\) \{.*?\n\}\nfunction ppAppendRa_", options_block + "function ppAppendRa_")
replace(gas, "['Ca 1','Ca 2','HC'].indexOf(shift)", "['Ca 1','Ca 2','Ca HC'].indexOf(shift)")
replace(gas, "const res=ppValidateResources_(mnv,choice,body); const rev=ppAppendRa_(staff,shift,choice,res,'VÀO'", "const res=ppValidateResources_(mnv,choice,body,shift); const rev=ppAppendRa_(staff,shift,choice,res,'VÀO'")
replace(gas, "const res=ppValidateResources_(mnv,choice,body); const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const rev=ppAppendRa_", "const res=ppValidateResources_(mnv,choice,body,s.shift); const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const rev=ppAppendRa_")
replace(gas, "account:{login_id:a.login_id,role:a.role,display_name:a.display_name}", "account:{login_id:a.login_id,role:a.role,display_name:a.display_name,position:a.position||''}")
replace(gas, "ppBumpRevision_(); return {ok:true};\n}\nfunction ppAccountList_", "ppBumpRevision_(); ppBumpMasterRevision_(); return {ok:true};\n}\nfunction ppAccountList_", 1)
replace(gas, "  ppBumpRevision_(); return {ok:true};\n}\nfunction ppAccountStatus_", "  ppBumpRevision_(); ppBumpMasterRevision_(); return {ok:true};\n}\nfunction ppAccountStatus_", 1)
replace(gas, "ppBumpRevision_();return {ok:true};\n}\n\nfunction ppAuthenticate_", "ppBumpRevision_();ppBumpMasterRevision_();return {ok:true};\n}\n\nfunction ppAuthenticate_", 1)

end_block = r'''function ppSyncStatus_(){return {ok:true,business_date:ppBusinessIso_(),server_seq:ppRevision_(),master_revision:ppMasterRevision_(),last_event_at:ppNowIso_(),projection_pending:0,mode:'APP_GSHEET'};}
function ppDiagnosticLog_(auth,body) {
  const eventId=String(body.event_id||'').trim(); if(!eventId)return {ok:false,error:'EVENT_ID_REQUIRED'};
  const type=String(body.log_type||'').trim().toUpperCase();
  const map={MANUAL:{id:PP.LOG_MANUAL_FOLDER_ID,prefix:'manual'},CRASH:{id:PP.LOG_CRASH_FOLDER_ID,prefix:'crash'},DAILY:{id:PP.LOG_ANDROID_FOLDER_ID,prefix:'android-daily'}};
  const target=map[type]; if(!target)return {ok:false,error:'LOG_TYPE_INVALID'};
  const raw=JSON.stringify({event_id:eventId,log_type:type,at:ppNowIso_(),login_id:auth.login_id,role:auth.role,channel:body.channel||body._app_channel||'',app_version:body.app_version||body._app_version||'',payload:body.payload||{}});
  if(raw.length>80000)return {ok:false,error:'LOG_TOO_LARGE'};
  DriveApp.getFolderById(target.id).createFile(target.prefix+'-'+Utilities.formatDate(new Date(),PP.TZ,'yyyyMMdd-HHmmss')+'-'+eventId+'.json',raw,MimeType.PLAIN_TEXT);
  return {ok:true,ack_event_id:eventId,log_type:type};
}
function ppCleanError_(err){const m=String(err&&err.message||err||'UNKNOWN');const known=['PP_SESSION_ALREADY_ACTIVE','PP_SESSION_ALREADY_ENDED','PP_SESSION_NOT_ENTERED','PP_RESOURCE_CONFLICT','PP_USER_PICK_USED_TODAY','PP_USER_PACK_USED_TODAY','PP_LABOR_ALREADY_ACTIVE','PP_LABOR_NOT_ACTIVE','PDA_INVALID','PACK_TABLE_INVALID','PACK_BUNDLE_INVALID','USER_PICK_INVALID','USER_PICK_REQUIRED','BUSY_RETRY'];for(let i=0;i<known.length;i++)if(m.indexOf(known[i])>=0)return m.slice(m.indexOf(known[i]),m.indexOf(known[i])+220);return m.slice(0,220)||'SERVER_ERROR';}'''
regex_replace(gas, r"function ppSyncStatus_\(\).*?function ppCleanError_\(err\).*?\}", end_block)

# ---------------- Android local master cache ----------------
write(
    "app/src/main/java/vn/pickpack1291/app/beta/MasterDataCache.kt",
    r'''package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer

object MasterDataCache {
    private const val PREFS = "pp1291_master_cache"
    private const val KEY_JSON = "snapshot"
    private const val KEY_REV = "revision"
    private const val KEY_AT = "saved_at"

    fun save(context: Context, snapshot: JSONObject) {
        if (!snapshot.optBoolean("ok", false)) return
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_JSON, snapshot.toString())
            .putLong(KEY_REV, snapshot.optLong("master_revision", 0L))
            .putLong(KEY_AT, System.currentTimeMillis())
            .apply()
    }

    fun snapshot(context: Context): JSONObject? {
        val raw = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_JSON, null) ?: return null
        return runCatching { JSONObject(raw) }.getOrNull()
    }

    fun revision(context: Context): Long = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_REV, 0L)
    fun savedAt(context: Context): Long = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_AT, 0L)

    fun employee(context: Context, mnv: String): JSONObject? {
        val a = snapshot(context)?.optJSONArray("staff") ?: return null
        for (i in 0 until a.length()) {
            val e = a.optJSONObject(i) ?: continue
            if (e.optString("mnv") == mnv) return e
        }
        return null
    }

    fun searchStaff(context: Context, query: String, limit: Int = 60): JSONArray {
        val out = JSONArray()
        val q = fold(query)
        if (q.length < 2) return out
        val a = snapshot(context)?.optJSONArray("staff") ?: return out
        for (i in 0 until a.length()) {
            val e = a.optJSONObject(i) ?: continue
            if (fold(e.optString("mnv") + " " + e.optString("full_name")).contains(q)) {
                out.put(JSONObject(e.toString()))
                if (out.length() >= limit) break
            }
        }
        return out
    }

    private fun fold(v: String): String = Normalizer.normalize(v, Normalizer.Form.NFD)
        .replace(Regex("\\p{Mn}+"), "").uppercase().trim()
}
''',
)

# ---------------- Android edge swipe ----------------
write(
    "app/src/main/java/vn/pickpack1291/app/beta/EdgeSwipeBackLayout.kt",
    r'''package vn.pickpack1291.app.beta

import android.content.Context
import android.view.MotionEvent
import android.view.ViewConfiguration
import android.widget.FrameLayout
import kotlin.math.abs

class EdgeSwipeBackLayout(context: Context, private val onBackGesture: () -> Unit) : FrameLayout(context) {
    private val edge = 26f * resources.displayMetrics.density
    private val trigger = 84f * resources.displayMetrics.density
    private val slop = ViewConfiguration.get(context).scaledTouchSlop
    private var startX = 0f
    private var startY = 0f
    private var tracking = false
    private var intercepted = false

    override fun onInterceptTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> { startX = ev.x; startY = ev.y; tracking = startX <= edge; intercepted = false }
            MotionEvent.ACTION_MOVE -> if (tracking) {
                val dx = ev.x - startX; val dy = abs(ev.y - startY)
                if (dx > slop && dx > dy * 1.25f) { intercepted = true; return true }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> tracking = false
        }
        return false
    }

    override fun onTouchEvent(ev: MotionEvent): Boolean {
        if (!tracking && !intercepted) return super.onTouchEvent(ev)
        when (ev.actionMasked) {
            MotionEvent.ACTION_UP -> {
                val dx = ev.x - startX; val dy = abs(ev.y - startY)
                tracking = false; intercepted = false
                if (dx >= trigger && dx > dy * 1.25f) onBackGesture()
                return true
            }
            MotionEvent.ACTION_CANCEL -> { tracking = false; intercepted = false; return true }
        }
        return true
    }
}
''',
)

# ---------------- Android log routing ----------------
write(
    "app/src/main/java/vn/pickpack1291/app/beta/LocalLogManager.kt",
    r'''package vn.pickpack1291.app.beta

import android.content.Context
import android.os.Build
import android.os.SystemClock
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

object LocalLogManager {
    private const val PREFS = "pp1291_log_state"
    private const val KEY_DAILY = "last_daily_log"

    fun installCrashHandler(context: Context) {
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching {
                write(context, "CRASH", buildString {
                    appendLine("type=CRASH"); appendCommon(context)
                    appendLine("thread=${safe(thread.name)}")
                    appendLine("exception=${safe(error.javaClass.name)}")
                    appendLine("message=${safe(error.message)}")
                    appendLine("stacktrace="); appendLine(error.stackTraceToString().take(50000))
                })
            }
            previous?.uncaughtException(thread, error)
        }
    }

    fun createDailyIfNeeded(context: Context): File? {
        val day = SimpleDateFormat("yyyyMMdd", Locale.US).format(Date())
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY_DAILY, null) == day) return null
        val file = write(context, "ANDROID_DAILY", buildString {
            appendLine("type=DAILY"); appendCommon(context)
            appendLine("uptime_ms=${SystemClock.elapsedRealtime()}")
        })
        prefs.edit().putString(KEY_DAILY, day).apply()
        return file
    }

    fun uploadAutomaticPending(context: Context, api: BetaApiClient) {
        val files = logDir(context).listFiles()?.filter { it.name.startsWith("CRASH_") || it.name.startsWith("ANDROID_DAILY_") }?.sortedBy { it.lastModified() }.orEmpty()
        uploadNext(api, files, 0)
    }

    fun sendManualReport(context: Context, api: BetaApiClient, screen: String, syncState: String, callback: (BetaApiClient.Result) -> Unit) {
        val file = write(context, "MANUAL_REPORT", buildString {
            appendLine("type=MANUAL"); appendCommon(context)
            appendLine("screen=${safe(screen)}")
            appendLine("sync_state=${safe(syncState)}")
            appendLine("uptime_ms=${SystemClock.elapsedRealtime()}")
            appendLine("memory_max_mb=${Runtime.getRuntime().maxMemory() / 1024 / 1024}")
            appendLine("memory_total_mb=${Runtime.getRuntime().totalMemory() / 1024 / 1024}")
            appendLine("memory_free_mb=${Runtime.getRuntime().freeMemory() / 1024 / 1024}")
        })
        uploadFile(api, file, "MANUAL") { r -> if (r.ok) file.delete(); callback(r) }
    }

    private fun uploadNext(api: BetaApiClient, files: List<File>, index: Int) {
        if (index >= files.size) return
        val f = files[index]
        val type = if (f.name.startsWith("CRASH_")) "CRASH" else "DAILY"
        uploadFile(api, f, type) { r ->
            if (r.ok) f.delete()
            if (r.ok || r.code != 401) uploadNext(api, files, index + 1)
        }
    }

    private fun uploadFile(api: BetaApiClient, file: File, type: String, callback: (BetaApiClient.Result) -> Unit) {
        val payload = JSONObject().put("text", runCatching { file.readText().take(60000) }.getOrDefault("LOG_READ_FAILED")).put("file_name", file.name)
        api.call("diagnostic_log", JSONObject()
            .put("event_id", UUID.randomUUID().toString())
            .put("log_type", type)
            .put("channel", BuildConfig.CHANNEL)
            .put("app_version", BuildConfig.VERSION_NAME)
            .put("payload", payload), callback)
    }

    private fun StringBuilder.appendCommon(context: Context) {
        appendLine("timestamp=${SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(Date())}")
        appendLine("package=${context.packageName}")
        appendLine("version=${BuildConfig.VERSION_NAME}")
        appendLine("channel=${BuildConfig.CHANNEL}")
        appendLine("manufacturer=${safe(Build.MANUFACTURER)}")
        appendLine("model=${safe(Build.MODEL)}")
        appendLine("android=${safe(Build.VERSION.RELEASE)}")
        appendLine("api=${Build.VERSION.SDK_INT}")
        appendLine("device=${safe(Build.DEVICE)}")
    }

    private fun logDir(context: Context) = File(context.filesDir, "diagnostic_logs").apply { mkdirs() }
    private fun write(context: Context, prefix: String, content: String): File {
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(Date())
        return File(logDir(context), "${prefix}_${stamp}.log").apply { writeText(content) }
    }
    private fun safe(value: String?): String = value.orEmpty().replace("\n", " ").replace("\r", " ").take(300)
}
''',
)

# ---------------- Foreground sync revision split ----------------
fg_path = "app/src/main/java/vn/pickpack1291/app/beta/ForegroundSyncCoordinator.kt"
fg = Path(fg_path).read_text(encoding="utf-8")
fg = fg.replace("val changed: Boolean,\n        val error: String? = null,", "val changed: Boolean,\n        val masterRevision: Long,\n        val masterChanged: Boolean,\n        val error: String? = null,")
fg = fg.replace('private val cursorKey = "server_seq_${BuildConfig.CHANNEL}"\n', 'private val cursorKey = "server_seq_${BuildConfig.CHANNEL}"\n    private val masterCursorKey = "master_revision_${BuildConfig.CHANNEL}"\n')
fg = fg.replace("private var lastSeq = prefs.getLong(cursorKey, 0L)\n", "private var lastSeq = prefs.getLong(cursorKey, 0L)\n    private var lastMasterRevision = prefs.getLong(masterCursorKey, 0L)\n")
fg = fg.replace("val changed = seq != lastSeq\n                    if (changed) {", "val changed = seq != lastSeq\n                    val masterRevision = body.optLong(\"master_revision\", lastMasterRevision)\n                    val masterChanged = masterRevision != lastMasterRevision\n                    if (changed) {")
fg = fg.replace("                    } else {\n                        idlePolls", "                    }\n                    if (masterChanged) {\n                        lastMasterRevision = masterRevision\n                        prefs.edit().putLong(masterCursorKey, masterRevision).apply()\n                        idlePolls = 0\n                    } else if (!changed) {\n                        idlePolls")
fg = fg.replace("changed = changed,\n                            )", "changed = changed,\n                                masterRevision = masterRevision,\n                                masterChanged = masterChanged,\n                            )")
fg = fg.replace("changed = false,\n                            error =", "changed = false,\n                            masterRevision = lastMasterRevision,\n                            masterChanged = false,\n                            error =")
Path(fg_path).write_text(fg, encoding="utf-8")

# ---------------- Full beta UX ----------------
f = "app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt"
s = Path(f).read_text(encoding="utf-8")
s = s.replace("import android.text.InputType\n", "import android.text.InputType\nimport android.text.method.DigitsKeyListener\nimport android.view.KeyEvent\n")
s = s.replace('    private var accountRole = ""\n    private var syncText: TextView? = null\n', '    private var accountRole = ""\n    private var accountPosition = ""\n    private var syncText: TextView? = null\n    private var currentScreen = "LOGIN"\n')
s = s.replace("                if (status.changed && liveEmployeeMnv.isNotBlank()) loadEmployee(liveEmployeeMnv)\n", "                if (status.masterChanged) refreshMasterCache()\n                if (status.changed && liveEmployeeMnv.isNotBlank()) loadEmployee(liveEmployeeMnv)\n")
s = s.replace('        accountLogin = ""; accountName = ""; accountRole = ""\n', '        currentScreen = "LOGIN"\n        accountLogin = ""; accountName = ""; accountRole = ""; accountPosition = ""\n')
s = s.replace('                accountRole = a.optString("role", "USER")\n', '                accountRole = a.optString("role", "USER")\n                accountPosition = a.optString("position", "")\n')
s = s.replace("                dashboard()\n                foregroundSync.start()\n", "                refreshMasterCache()\n                LocalLogManager.uploadAutomaticPending(this@FullBetaActivity, api)\n                dashboard()\n                foregroundSync.start()\n")
s = s.replace('    private fun dashboard() {\n        liveEmployeeMnv = ""\n', '    private fun dashboard() {\n        currentScreen = "DASHBOARD"\n        liveEmployeeMnv = ""\n')
old_dash = '''        body.addView(fullCard("▣", "QUÉT QR NHÂN SỰ", blue, dp(88)) { employeeScan() })
        body.addView(gap(7))
        body.addView(cardRow(
            tile("◉", "CÔNG NHẬT", green) { openModule("LABOR") },
            tile("⌘", "TÀI NGUYÊN", orange) { openModule("RESOURCES") }
        ))
        body.addView(cardRow(
            tile("☷", "DANH SÁCH", Color.rgb(58, 91, 183)) { openModule("LISTS") },
            tile("▥", "BÁO CÁO", teal) { openModule("REPORT") }
        ))
        body.addView(gap(2))
        body.addView(fullCard("⚙", "CÀI ĐẶT", navy, dp(64)) { openModule("SETTINGS") })
        body.addView(gap(14))
        syncText = txt("●  Đang kiểm tra kết nối...", 10.5f, muted, false).apply { setPadding(dp(10), dp(9), dp(10), dp(9)); background = outlineBg(surface, 9) }
        body.addView(syncText, matchWrap())
'''
new_dash = '''        body.addView(fullCard("▣", "QUÉT QR NHÂN SỰ", blue, dp(94)) { employeeScan() })
        body.addView(gap(8))
        if (accountRole == "ADMIN" || accountRole == "SUPERADMIN") {
            body.addView(cardRow(
                tile("◉", "CÔNG NHẬT", green) { openModule("LABOR") },
                tile("☷", "THEO DÕI CA", Color.rgb(58, 91, 183)) { openModule("LISTS") }
            ))
        } else {
            body.addView(fullCard("☷", "THEO DÕI CA / DANH SÁCH", Color.rgb(58, 91, 183), dp(72)) { openModule("LISTS") })
        }
        body.addView(cardRow(
            tile("▥", "BÁO CÁO", teal) { openModule("REPORT") },
            tile("⚙", "CÀI ĐẶT", navy) { openModule("SETTINGS") }
        ))
        body.addView(gap(10))
        body.addView(info("Tài nguyên được cấp/đổi ngay trong phiên nhân sự. Master data được cache trên máy và chỉ làm mới khi Google Sheet thay đổi."))
'''
if old_dash not in s:
    raise SystemExit("dashboard block missing")
s = s.replace(old_dash, new_dash)
s = s.replace('putExtra("module", module); putExtra("login", accountLogin); putExtra("name", accountName); putExtra("role", accountRole); putExtra("mnv", mnv)', 'putExtra("module", module); putExtra("login", accountLogin); putExtra("name", accountName); putExtra("role", accountRole); putExtra("position", accountPosition); putExtra("mnv", mnv)')
s = s.replace('    private fun employeeScan() {\n        liveEmployeeMnv = ""\n', '    private fun employeeScan() {\n        currentScreen = "SCAN"\n        liveEmployeeMnv = ""\n')
s = s.replace('val mnv = input("Quét QR hoặc nhập MNV", false).apply { setSingleLine(true); imeOptions = EditorInfo.IME_ACTION_DONE }', 'val mnv = mnvInput("Quét QR hoặc nhập MNV")')
s = s.replace('check.setOnClickListener { submit() }; mnv.setOnEditorActionListener { _, id, _ -> if(id==EditorInfo.IME_ACTION_DONE){submit();true}else false }', 'check.setOnClickListener { submit() }; bindScannerEnter(mnv) { if (check.isEnabled) submit() }')
s = s.replace('    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {\n', '    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {\n        currentScreen = "EMPLOYEE"\n')
s = s.replace('body.addView(status("CHƯA VÀO CA", blue, Color.rgb(237,244,255)));body.addView(gap(10))\n        val shift=spinner(arrayOf("Ca 1","Ca 2","HC"));', 'body.addView(status("CHƯA VÀO CA", blue, Color.rgb(237,244,255)));body.addView(gap(10));body.addView(section("PHÂN CÔNG TRONG CA"));\n        val shift=spinner(arrayOf("Ca 1","Ca 2","Ca HC"));')
s = s.replace('val pdaValues=mutableListOf<String>();val pickValues=mutableListOf<String?>();val packValues=mutableListOf<String>();', 'val pdaValues=mutableListOf<String>();val pickValues=mutableListOf<String>();val packValues=mutableListOf<String>();')
s = s.replace('val pl=mutableListOf("Không dùng User Pick");pickValues.add(null);for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){pl.add(v);pickValues.add(v)}};pickSpinner=spinner(pl.toTypedArray());resourceBox.addView(labelled("User Pick (tùy chọn)",pickSpinner!!))', 'val pl=mutableListOf<String>();for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){pl.add(v);pickValues.add(v)}};pickSpinner=spinner((if(pl.isEmpty())listOf("Không có User Pick khả dụng")else pl).toTypedArray());resourceBox.addView(labelled("User Pick (bắt buộc)",pickSpinner!!))')
s = s.replace('"PACK"->{val labels=mutableListOf<String>();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;val table=p.optString("table");if(table.isNotBlank()){packValues.add(table);labels.add("$table • ${p.optString("user_pack")}")}};', '"PACK"->{val labels=mutableListOf<String>();val selectedShift=shift.selectedItem.toString();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=selectedShift)continue;val table=p.optString("table");if(table.isNotBlank()){packValues.add(table);labels.add("$table • ${p.optString("user_pack")}")}};')
s = s.replace('choice.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};rebuild();body.addView(gap(14))', 'choice.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};shift.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};rebuild();body.addView(gap(14))', 1)
s = s.replace('pickValues.getOrNull(pickSpinner?.selectedItemPosition?:0)?.let{payload.put("user_pick",it)}', 'if(pickValues.isEmpty()){showError("Không còn User Pick khả dụng.");return@setOnClickListener};payload.put("user_pick",pickValues[pickSpinner?.selectedItemPosition?:0])')
s = s.replace('syncText?.text="●  FULL BETA • Seq ${j.optLong("server_seq",0)} • chờ Sheet ACK: $p";syncText?.setTextColor(if(p==0)green else orange)', 'syncText?.text="● LIVE  R${j.optLong("server_seq",0)}";syncText?.setTextColor(green)')
old_appbar = 'private fun appBar(title:String,back:Boolean)=row(navy).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(9),dp(7),dp(10),dp(7));addView(txt(if(back)"‹" else "☰",if(back)31f else 22f,Color.WHITE,false).apply{gravity=Gravity.CENTER;if(back)setOnClickListener{dashboard()}},size(dp(42),dp(45)));addView(txt(title,17f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f));addView(column(navy).apply{gravity=Gravity.END;addView(txt(if(accountLogin.isBlank())BuildConfig.CHANNEL else accountLogin,10.5f,Color.WHITE,true).apply{gravity=Gravity.END});addView(txt(roleText(accountRole),8.5f,Color.rgb(218,229,248),false).apply{gravity=Gravity.END})})}'
new_appbar = 'private fun appBar(title:String,back:Boolean)=row(navy).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(9),dp(7),dp(10),dp(7));addView(txt(if(back)"‹" else "",if(back)31f else 22f,Color.WHITE,false).apply{gravity=Gravity.CENTER;if(back)setOnClickListener{navigateBack()}},size(dp(42),dp(45)));addView(txt(title,17f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f));syncText=txt("● SYNC",9.5f,Color.rgb(218,229,248),true).apply{gravity=Gravity.CENTER;setPadding(dp(8),dp(5),dp(8),dp(5))};addView(syncText,size(dp(86),dp(36)))}'
if old_appbar not in s:
    raise SystemExit("full appbar missing")
s = s.replace(old_appbar, new_appbar)
s = s.replace('    private fun input(hintValue:String,password:Boolean)=EditText(this).apply{', '    private fun section(title:String)=txt(title,10.5f,navy,true).apply{setPadding(0,dp(5),0,dp(6))}\n    private fun mnvInput(hintValue:String)=input(hintValue,false).apply{setSingleLine(true);inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");imeOptions=EditorInfo.IME_ACTION_DONE}\n    private fun bindScannerEnter(v:EditText, submit:()->Unit){v.setOnEditorActionListener{_,id,_->if(id==EditorInfo.IME_ACTION_DONE||id==EditorInfo.IME_ACTION_GO||id==EditorInfo.IME_ACTION_SEARCH){submit();true}else false};v.setOnKeyListener{_,key,event->if(key==KeyEvent.KEYCODE_ENTER&&event.action==KeyEvent.ACTION_UP){submit();true}else false}}\n    private fun input(hintValue:String,password:Boolean)=EditText(this).apply{')
s = s.replace('    private fun setScreen(content:View){setContentView(host(content))}\n', '    private fun setScreen(content:View){setContentView(host(content))}\n    private fun navigateBack(){when(currentScreen){"EMPLOYEE"->employeeScan();"SCAN"->dashboard();"DASHBOARD"->finish();else->dashboard()}}\n    private fun refreshMasterCache(){api.call("master_snapshot"){r->if(r.ok&&r.json!=null)MasterDataCache.save(applicationContext,r.json)}}\n')
s = s.replace('private fun host(content:View):View{val root=FrameLayout(this).apply{setBackgroundColor(bg)};', 'private fun host(content:View):View{val root=EdgeSwipeBackLayout(this){if(currentScreen!="LOGIN"&&currentScreen!="DASHBOARD")navigateBack()}.apply{setBackgroundColor(bg)};')
Path(f).write_text(s, encoding="utf-8")

# ---------------- Operations UX ----------------
f = "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
s = Path(f).read_text(encoding="utf-8")
s = s.replace("import android.text.InputType\n", "import android.text.InputType\nimport android.text.method.DigitsKeyListener\nimport android.view.KeyEvent\n")
s = s.replace('    private lateinit var role: String\n    private var initialMnv = ""\n', '    private lateinit var role: String\n    private var position = ""\n    private var initialMnv = ""\n    private var screenState = "ROOT"\n    private var syncText: TextView? = null\n')
s = s.replace('            override fun onStatus(status: ForegroundSyncCoordinator.Status) {\n                if (!status.connected || !status.changed) return\n', '            override fun onStatus(status: ForegroundSyncCoordinator.Status) {\n                syncText?.text = if(status.connected) "● LIVE  R${status.serverSeq}" else "● OFFLINE"\n                syncText?.setTextColor(if(status.connected) green else red)\n                if(status.masterChanged) refreshMasterCache()\n                if (!status.connected || !status.changed) return\n')
s = s.replace('        role = intent.getStringExtra("role") ?: "USER"\n', '        role = intent.getStringExtra("role") ?: "USER"\n        position = intent.getStringExtra("position") ?: ""\n')
s = s.replace('    private fun laborHome() {\n', '    private fun laborHome() {\n        screenState = "LABOR_HOME"\n')
s = s.replace('val mnv=input("MNV",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_DONE;setText(initialMnv)}', 'val mnv=mnvInput("MNV").apply{setText(initialMnv)}', 1)
s = s.replace('button.setOnClickListener{submit()};mnv.setOnEditorActionListener{_,id,_->if(id==EditorInfo.IME_ACTION_DONE){submit();true}else false};body.addView(button,matchWrap())', 'button.setOnClickListener{submit()};bindScannerEnter(mnv){if(button.isEnabled)submit()};body.addView(button,matchWrap())', 1)
s = s.replace('api.call("master_options",JSONObject().put("mnv",v)){m->runOnUiThread{if(handleAuth(m))return@runOnUiThread;showLaborContext(r.json?:JSONObject(),m.json?:JSONObject())}}', 'showLaborContext(r.json?:JSONObject(),MasterDataCache.snapshot(this@OperationsActivity)?:JSONObject())', 1)
s = s.replace('    private fun showLaborContext(ctx:JSONObject, masters:JSONObject){\n', '    private fun showLaborContext(ctx:JSONObject, masters:JSONObject){\n        screenState = "LABOR_CONTEXT"\n')
s = s.replace('    private fun resourceHome(){\n', '    private fun resourceHome(){\n        screenState = "RESOURCE_HOME"\n')
s = s.replace('val mnv=input("MNV",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_DONE;setText(initialMnv)}', 'val mnv=mnvInput("MNV").apply{setText(initialMnv)}', 1)
s = s.replace('button.setOnClickListener{submit()};mnv.setOnEditorActionListener{_,id,_->if(id==EditorInfo.IME_ACTION_DONE){submit();true}else false};body.addView(button,matchWrap())', 'button.setOnClickListener{submit()};bindScannerEnter(mnv){if(button.isEnabled)submit()};body.addView(button,matchWrap())', 1)
s = s.replace('    private fun showResourceEditor(ctx:JSONObject,masters:JSONObject){\n', '    private fun showResourceEditor(ctx:JSONObject,masters:JSONObject){\n        screenState = "RESOURCE_EDITOR"\n')
s = s.replace('val pdaVals=mutableListOf<String>();val pickVals=mutableListOf<String?>();val packVals=mutableListOf<String>();', 'val pdaVals=mutableListOf<String>();val pickVals=mutableListOf<String>();val packVals=mutableListOf<String>();')
s = s.replace('val pl=mutableListOf("Không dùng User Pick");pickVals.add(null);for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){pl.add(v);pickVals.add(v)}};pickSp=spinner(pl.toTypedArray());box.addView(labelled("User Pick",pickSp!!));', 'val pl=mutableListOf<String>();for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){pl.add(v);pickVals.add(v)}};pickSp=spinner((if(pl.isEmpty())listOf("Không có User Pick khả dụng")else pl).toTypedArray());box.addView(labelled("User Pick (bắt buộc)",pickSp!!));')
s = s.replace('"PACK"->{val labels=mutableListOf<String>();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;val t=p.optString("table");if(t.isNotBlank()){packVals.add(t);labels.add("$t • ${p.optString("user_pack")}")}};', '"PACK"->{val labels=mutableListOf<String>();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=s.optString("shift"))continue;val t=p.optString("table");if(t.isNotBlank()){packVals.add(t);labels.add("$t • ${p.optString("user_pack")}")}};')
s = s.replace('pickVals.getOrNull(pickSp?.selectedItemPosition?:0)?.let{p.put("user_pick",it)}', 'if(pickVals.isEmpty()){showError("Không còn User Pick khả dụng.");return@setOnClickListener};p.put("user_pick",pickVals[pickSp?.selectedItemPosition?:0])')
s = s.replace('    private fun listsScreen(){\n', '    private fun listsScreen(){\n        screenState = "LISTS"\n')
pattern = r'fun searchStaff\(\)\{val query=q\.text\.toString\(\)\.trim\(\);box\.removeAllViews\(\);if\(query\.length<2\).*?\}\}\}'
repl = '''fun searchStaff(){val query=q.text.toString().trim();box.removeAllViews();if(query.length<2){box.addView(info("Nhập ít nhất 2 ký tự để tìm nhân sự."));return};val a=MasterDataCache.searchStaff(this,query);for(i in 0 until a.length()){val e=a.optJSONObject(i)?:continue;box.addView(listCard("${e.optString("mnv")} • ${e.optString("full_name")}","${e.optString("main_position")} • ${e.optString("supplier")} • ${e.optString("department")}"));box.addView(gap(6))};if(a.length()==0)box.addView(info("Không có kết quả trong cache. Master data tự làm mới khi Sheet thay đổi."))}'''
s, n = re.subn(pattern, repl, s, count=1, flags=re.S)
if n != 1:
    raise SystemExit("staff search patch failed")
s = s.replace('    private fun reportScreen(){\n', '    private fun reportScreen(){\n        screenState = "REPORT"\n')
s = s.replace('    private fun settingsScreen(){\n', '    private fun settingsScreen(){\n        screenState = "SETTINGS"\n')
s = s.replace('body.addView(listCard("$name • ${roleText(role)}",login));', 'body.addView(listCard("$name • ${roleText(role)}","Tài khoản: $login${if(position.isBlank())"" else " • Vị trí: $position"}"));')
s = s.replace('sync.text="FULL BETA • Google Sheet rev ${j.optLong("server_seq")} • công nhật đang làm ${j.optInt("labor_active")}"', 'sync.text="Google Sheet rev ${j.optLong("server_seq")} • Master rev ${j.optLong("master_revision")} • cache máy rev ${MasterDataCache.revision(this@OperationsActivity)}"')
s, n = re.subn(
    r'    private fun sendDiagnostic\(\)\{.*?\n\n    private fun accountManager\(\)\{',
    '''    private fun sendDiagnostic(){LocalLogManager.sendManualReport(this,api,module,syncText?.text?.toString().orEmpty()){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không gửi được báo lỗi")else AlertDialog.Builder(this).setTitle("Đã gửi").setMessage("Báo lỗi thủ công đã được lưu đúng thư mục BÁO LỖI THỦ CÔNG.").setPositiveButton("OK",null).show()}}}\n\n    private fun accountManager(){\n        screenState = "ACCOUNT_MANAGER"''',
    s,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("diagnostic patch failed")
s = s.replace('    private fun simpleMessage(title:String,message:String){', '    private fun refreshMasterCache(){api.call("master_snapshot"){r->if(r.ok&&r.json!=null)MasterDataCache.save(applicationContext,r.json)}}\n    private fun navigateBack(){when(screenState){"LABOR_CONTEXT"->laborHome();"RESOURCE_EDITOR"->resourceHome();"ACCOUNT_MANAGER"->settingsScreen();else->finish()}}\n    private fun simpleMessage(title:String,message:String){')
old_app = 'private fun appBar(title:String)=row(navy).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(9),dp(7),dp(10),dp(7));addView(txt("‹",31f,Color.WHITE,false).apply{gravity=Gravity.CENTER;setOnClickListener{finish()}},size(dp(42),dp(45)));addView(txt(title,17f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f));addView(column(navy).apply{gravity=Gravity.END;addView(txt(login,10.5f,Color.WHITE,true).apply{gravity=Gravity.END});addView(txt(roleText(role),8.5f,Color.rgb(218,229,248),false).apply{gravity=Gravity.END})})}'
new_app = 'private fun appBar(title:String)=row(navy).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(9),dp(7),dp(10),dp(7));addView(txt("‹",31f,Color.WHITE,false).apply{gravity=Gravity.CENTER;setOnClickListener{navigateBack()}},size(dp(42),dp(45)));addView(txt(title,17f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f));syncText=txt("● SYNC",9.5f,Color.rgb(218,229,248),true).apply{gravity=Gravity.CENTER;setPadding(dp(8),dp(5),dp(8),dp(5))};addView(syncText,size(dp(86),dp(36)))}'
if old_app not in s:
    raise SystemExit("operations appbar missing")
s = s.replace(old_app, new_app)
s = s.replace('    private fun input(hintValue:String,password:Boolean)=EditText(this).apply{', '    private fun mnvInput(hintValue:String)=input(hintValue,false).apply{setSingleLine(true);inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");imeOptions=EditorInfo.IME_ACTION_DONE}\n    private fun bindScannerEnter(v:EditText, submit:()->Unit){v.setOnEditorActionListener{_,id,_->if(id==EditorInfo.IME_ACTION_DONE||id==EditorInfo.IME_ACTION_GO||id==EditorInfo.IME_ACTION_SEARCH){submit();true}else false};v.setOnKeyListener{_,key,event->if(key==KeyEvent.KEYCODE_ENTER&&event.action==KeyEvent.ACTION_UP){submit();true}else false}}\n    private fun input(hintValue:String,password:Boolean)=EditText(this).apply{')
s = s.replace('private fun host(content:View):View{val root=FrameLayout(this).apply{setBackgroundColor(bg)};', 'private fun host(content:View):View{val root=EdgeSwipeBackLayout(this){navigateBack()}.apply{setBackgroundColor(bg)};')
Path(f).write_text(s, encoding="utf-8")

# ---------------- Launcher icon using supplied artwork ----------------
manifest = "app/src/main/AndroidManifest.xml"
replace(manifest, 'android:icon="@drawable/app_icon"', 'android:icon="@mipmap/ic_launcher"')
replace(manifest, 'android:roundIcon="@drawable/app_icon"', 'android:roundIcon="@mipmap/ic_launcher_round"')
write(
    "app/src/main/res/drawable/app_icon_foreground.xml",
    '''<?xml version="1.0" encoding="utf-8"?>\n<inset xmlns:android="http://schemas.android.com/apk/res/android" android:inset="14%">\n    <bitmap android:src="@drawable/app_icon" android:gravity="fill" />\n</inset>\n''',
)
legacy = '''<?xml version="1.0" encoding="utf-8"?>\n<layer-list xmlns:android="http://schemas.android.com/apk/res/android">\n    <item android:drawable="@android:color/white" />\n    <item android:drawable="@drawable/app_icon_foreground" />\n</layer-list>\n'''
adaptive = '''<?xml version="1.0" encoding="utf-8"?>\n<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n    <background android:drawable="@android:color/white" />\n    <foreground android:drawable="@drawable/app_icon_foreground" />\n</adaptive-icon>\n'''
write("app/src/main/res/mipmap-anydpi/ic_launcher.xml", legacy)
write("app/src/main/res/mipmap-anydpi/ic_launcher_round.xml", legacy)
write("app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml", adaptive)
write("app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml", adaptive)

# ---------------- Version ----------------
gradle = "app/build.gradle.kts"
replace(gradle, "versionCode = 5", "versionCode = 6")
replace(gradle, 'versionName = "0.4.0-beta.1"', 'versionName = "0.4.1-beta.1"')

print("v0.4.1 source refactor applied")
