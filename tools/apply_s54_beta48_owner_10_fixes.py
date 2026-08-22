#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
TRANSPORT = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt"
STORE = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt"
LOGS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/LocalLogManager.kt"
MARK = "S54_BETA48_OWNER_10_FIXES"


def replace_once(src: str, old: str, new: str, name: str) -> str:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"S54 {name} anchor mismatch: {n}")
    return src.replace(old, new, 1)


def replace_at_least_once(src: str, old: str, new: str, name: str) -> str:
    n = src.count(old)
    if n < 1:
        raise SystemExit(f"S54 {name} anchor missing")
    return src.replace(old, new)

# ----- OperationsActivity: owner UI/business fixes -----
s = OPS.read_text(encoding="utf-8")
if MARK not in s:
    # History must be a calendar rolling window ending at the current +07 day, including an empty new day.
    s = replace_once(
        s,
        'var selectedDate=operationalStore.latestBusinessDate().ifBlank{operationalStore.businessDate()};var filter="ALL";var pageSize=60;var query=""',
        'var selectedDate=operationalStore.businessDate();var filter="ALL";var pageSize=60;var query=""',
        "history-current-day",
    )
    s = replace_once(
        s,
        'else for(d in operationalStore.availableDates()){if(out.size>=300)break;scanDate(d,needle,300,out)}',
        'else for(d in operationalStore.historyWindowDates()){if(out.size>=300)break;scanDate(d,needle,300,out)}',
        "history-rolling-search",
    )

    # User Pack by table is intentionally not restricted by the employee selected shift. Active leases still hide busy resources.
    s = s.replace('val selectedShift=shift.selectedItem.toString();', '')
    s = s.replace('if(p.optString("shift")!=selectedShift)continue;', '')
    s = s.replace('if(p.optString("shift")!=s.optString("shift"))continue;', '')
    if 'selectedShift=shift.selectedItem.toString()' in s or 'optString("shift")!=selectedShift' in s:
        raise SystemExit("S54 PACK shift filter still present")

    # Make both shift mappings explicit in the choice label when the source mapping provides a shift.
    s = s.replace('labels.add("$table • ${p.optString("user_pack")}")', 'labels.add("$table • ${p.optString("user_pack")} • ${p.optString("shift")}")')
    s = s.replace('labels.add("$t • ${p.optString("user_pack")}")', 'labels.add("$t • ${p.optString("user_pack")} • ${p.optString("shift")}")')

    # User-facing terminology.
    s = replace_at_least_once(s, 'Không dùng User Pick', 'Không dùng User hy1.outbound', "pick-label")

    # Remove explanatory OWNER/AI-style product copy; keep only consequential confirmation text.
    s = re.sub(r'\s*selectionBox\.addView\(info\("Quản trị cao nhất có thể chọn nhiều lịch sử, kể cả mục đang chờ đồng bộ\.[^"]*"\)\)', '', s, count=1)
    s = s.replace(
        'setMessage("Mục đã chọn sẽ được ẩn khỏi lịch sử. Nếu dữ liệu nghiệp vụ còn chờ đồng bộ, ứng dụng vẫn gửi dữ liệu đó lên Service trước rồi mới ghi dấu xóa. Nhật ký ai xóa, lúc nào và xóa gì vẫn được giữ.")',
        'setMessage("Xóa các mục lịch sử đã chọn?")',
    )

    # Global spacing: about 10% tighter without shrinking primary touch targets or font sizes.
    s = replace_once(
        s,
        'private fun body()=column(bg).apply{setPadding(dp(16),dp(15),dp(16),dp(92))}',
        'private fun body()=column(bg).apply{setPadding(dp(14),dp(13),dp(14),dp(83))}',
        "body-spacing",
    )
    s = replace_once(
        s,
        'private fun gap(h:Int)=Space(this).apply{layoutParams=size(1,dp(h))}',
        'private fun gap(h:Int)=Space(this).apply{layoutParams=size(1,dp(((h*9)+5)/10))}',
        "gap-spacing",
    )

    # Dedicated selected-PDA area. It updates immediately from the 5-digit field and shows the full serial.
    pda_anchor = '    private fun pdaInput('
    pos = s.find(pda_anchor)
    if pos < 0:
        raise SystemExit("S54 pdaInput function anchor missing")
    helper = r'''    // S54_BETA48_OWNER_10_FIXES: explicit selected PDA serial panel.
    private fun pdaSelectedPanel(pdas:JSONArray,field:AutoCompleteTextView):TextView{
        val panel=txt("SERI PDA ĐÃ CHỌN\nChưa chọn seri",11.2f,navy,true).apply{
            setPadding(dp(12),dp(9),dp(12),dp(9));background=outlineBg(Color.rgb(239,246,255),13)
        }
        fun update(){
            val serial=resolvePda(pdas,field.text?.toString().orEmpty())
            panel.text=if(serial.isNullOrBlank())"SERI PDA ĐÃ CHỌN\nChưa chọn seri" else "SERI PDA ĐÃ CHỌN\n$serial"
            panel.setTextColor(if(serial.isNullOrBlank())muted else navy)
        }
        field.addTextChangedListener(object:TextWatcher{
            override fun beforeTextChanged(v:CharSequence?,start:Int,count:Int,after:Int)=Unit
            override fun onTextChanged(v:CharSequence?,start:Int,before:Int,count:Int)=update()
            override fun afterTextChanged(v:Editable?)=Unit
        });update();return panel
    }

'''
    s = s[:pos] + helper + s[pos:]
    s = s.replace(
        'resourceBox.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));resourceBox.addView(gap(8));',
        'resourceBox.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));resourceBox.addView(gap(4));resourceBox.addView(pdaSelectedPanel(pdas,pdaField!!));resourceBox.addView(gap(8));',
    )
    s = s.replace(
        'box.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));box.addView(gap(8));',
        'box.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));box.addView(gap(4));box.addView(pdaSelectedPanel(pdas,pdaField!!));box.addView(gap(8));',
    )

    # Sync / device storage. Keep the details human-readable.
    s = replace_once(
        s,
        '"Dữ liệu chờ gửi" to pending.toString(),"Luồng trao đổi dữ liệu"',
        '"Dữ liệu chờ gửi" to pending.toString(),"Dung lượng cache" to humanBytes(operationalStore.storageBytes()),"Luồng trao đổi dữ liệu"',
        "sync-cache-size",
    )
    load_app_old = 'fun loadApp(){appBox.removeAllViews();appBox.addView(section("ỨNG DỤNG"));appBox.addView(details(listOf("Kênh phát hành" to if(BuildConfig.CHANNEL=="BETA")"Bản thử nghiệm" else "Bản ổn định","Phiên bản ứng dụng" to BuildConfig.VERSION_NAME,"Mã phiên bản" to BuildConfig.VERSION_CODE.toString())))}'
    load_app_new = 'fun loadApp(){appBox.removeAllViews();appBox.addView(section("ỨNG DỤNG"));val deviceName="${Build.MANUFACTURER} ${Build.MODEL}".trim();appBox.addView(details(listOf("Tên thiết bị" to deviceName,"Kênh phát hành" to if(BuildConfig.CHANNEL=="BETA")"Bản thử nghiệm" else "Bản ổn định","Phiên bản ứng dụng" to BuildConfig.VERSION_NAME,"Mã phiên bản" to BuildConfig.VERSION_CODE.toString())))}'
    s = replace_once(s, load_app_old, load_app_new, "sync-device-name")

    # Move the device-name presentation out of Settings. The old block is removed when present.
    s, removed = re.subn(
        r'\n\s*body\.addView\(section\("THIẾT BỊ"\)\).*?(?=\n\s*body\.addView\(section\("NHẬT KÝ"\)\))',
        '\n', s, count=1, flags=re.S,
    )
    # Log section gets useful local footprint metadata.
    log_marker = 'body.addView(section("NHẬT KÝ"))'
    if log_marker in s:
        s = s.replace(log_marker, log_marker + ';body.addView(details(listOf("Nhật ký trên thiết bị" to LocalLogManager.summary(this))))', 1)

    # Byte formatter used for cache/log display.
    human_anchor = '    private fun dash(v:String)='
    hp = s.find(human_anchor)
    if hp < 0:
        raise SystemExit("S54 humanBytes insertion anchor missing")
    human = '''    private fun humanBytes(bytes:Long):String=when{bytes<1024L->"$bytes B";bytes<1024L*1024L->String.format(java.util.Locale.US,"%.1f KB",bytes/1024.0);bytes<1024L*1024L*1024L->String.format(java.util.Locale.US,"%.1f MB",bytes/(1024.0*1024.0));else->String.format(java.util.Locale.US,"%.2f GB",bytes/(1024.0*1024.0*1024.0))}\n'''
    s = s[:hp] + human + s[hp:]

    # Add a source marker without exposing implementation detail in the UI.
    s = s.replace('class OperationsActivity : Activity() {', 'class OperationsActivity : Activity() {\n    // S54_BETA48_OWNER_10_FIXES', 1)
    OPS.write_text(s, encoding="utf-8")

# ----- M2ServiceTransport: wire APP/WEB presence and recover known stale-date rejections -----
t = TRANSPORT.read_text(encoding="utf-8")
if MARK not in t:
    t = replace_once(
        t,
        'val r = httpJson("$base/v1/legacy-sync", request, token)',
        'val r = if(action=="service_connections") httpGetJson("$base/v1/service/connections",token) else httpJson("$base/v1/legacy-sync", request, token)',
        "connections-route",
    )
    t = replace_once(
        t,
        'val items = store.pendingMutations(100)',
        'store.retryDateWindowRejects()\n        val items = store.pendingMutations(100)',
        "date-reject-requeue",
    )
    t = replace_once(
        t,
        'val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap")',
        'val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap", "service_connections")',
        "connections-action",
    )
    get_anchor = '    private fun validServiceUrl(raw: String): Boolean = runCatching {'
    gp = t.find(get_anchor)
    if gp < 0:
        raise SystemExit("S54 httpGetJson insertion anchor missing")
    get_fun = r'''    private fun httpGetJson(endpoint:String,bearer:String?):HttpResult{
        if(!validServiceUrl(endpoint.substringBefore("/v1/")))return HttpResult(false,-1,null,"SERVICE_URL_INVALID")
        var conn:HttpURLConnection?=null
        return try{
            conn=(URL(endpoint).openConnection() as HttpURLConnection).apply{
                requestMethod="GET";connectTimeout=3_000;readTimeout=5_000;instanceFollowRedirects=true
                setRequestProperty("Accept","application/json");setRequestProperty("User-Agent","PickPack1291-M2/${BuildConfig.VERSION_NAME}")
                if(!bearer.isNullOrBlank())setRequestProperty("Authorization","Bearer $bearer")
            }
            val code=conn.responseCode;val stream=if(code in 200..299)conn.inputStream else conn.errorStream
            val text=stream?.bufferedReader(Charsets.UTF_8)?.use{it.readText()}.orEmpty();val j=if(text.isBlank())JSONObject() else JSONObject(text)
            val ok=code in 200..299&&j.optBoolean("ok",false);val errObj=j.optJSONObject("error")
            HttpResult(ok,code,j,if(ok)null else errObj?.optString("code")?.takeIf{it.isNotBlank()}?:j.optString("error","HTTP_$code"))
        }finally{conn?.disconnect()}
    }

'''
    t = t[:gp] + get_fun + t[gp:]
    t = t.replace('class M2ServiceTransport(context: Context) {', 'class M2ServiceTransport(context: Context) {\n    // S54_BETA48_OWNER_10_FIXES', 1)
    TRANSPORT.write_text(t, encoding="utf-8")

# ----- OperationalDataStore: rolling calendar history, cache footprint, exact-ID requeue -----
d = STORE.read_text(encoding="utf-8")
if MARK not in d:
    d = replace_once(d, 'import java.util.Date\n', 'import java.util.Date\nimport java.util.Calendar\n', "calendar-import")
    d = replace_once(
        d,
        'class OperationalDataStore(context: Context) {\n    private val helper = helper(context.applicationContext)',
        'class OperationalDataStore(context: Context) {\n    // S54_BETA48_OWNER_10_FIXES\n    private val app = context.applicationContext\n    private val helper = helper(app)',
        "store-context",
    )
    dates_anchor = '''    fun revisions(): Map<String, Long> = withDbLock {'''
    dp = d.find(dates_anchor)
    if dp < 0:
        raise SystemExit("S54 historyWindowDates insertion anchor missing")
    dates_fun = '''    fun historyWindowDates():List<String>{\n        val cal=Calendar.getInstance(TimeZone.getTimeZone(TZ));val out=ArrayList<String>(7)\n        repeat(7){out+=isoDate(cal.time);cal.add(Calendar.DAY_OF_MONTH,-1)}\n        return out\n    }\n\n    fun storageBytes():Long{\n        val main=app.getDatabasePath(DB_NAME);val base=main.absolutePath\n        return listOf(main,java.io.File(base+"-wal"),java.io.File(base+"-shm"),java.io.File(base+"-journal")).filter{it.exists()}.sumOf{it.length()}\n    }\n\n'''
    d = d[:dp] + dates_fun + d[dp:]
    retry_anchor = '    fun markMutationSynced(eventId: String) = markMutationResolved(eventId, "CONFIRMED", "")\n'
    retry_fun = '''    fun retryDateWindowRejects():Int=withDbLock{\n        val db=writableDb();val now=System.currentTimeMillis();var count=0\n        db.rawQuery("SELECT COUNT(*) FROM mutation_outbox WHERE status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW'",null).use{c->if(c.moveToFirst())count=c.getInt(0)}\n        if(count>0)db.execSQL("UPDATE mutation_outbox SET status='RETRY',next_attempt_at=?,updated_at=? WHERE status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW'",arrayOf(now,now))\n        count\n    }\n\n'''
    d = replace_once(d, retry_anchor, retry_fun + retry_anchor, "date-retry-method")
    STORE.write_text(d, encoding="utf-8")

# ----- Local logs: useful count/size/latest metadata -----
l = LOGS.read_text(encoding="utf-8")
if MARK not in l:
    summary_anchor = '    fun pendingCount(context: Context): Int = logDir(context).listFiles()?.count { it.isFile } ?: 0\n'
    summary_fun = '''    // S54_BETA48_OWNER_10_FIXES\n    fun summary(context:Context):String{\n        val files=logDir(context).listFiles()?.filter{it.isFile}.orEmpty();val bytes=files.sumOf{it.length()};val latest=files.maxOfOrNull{it.lastModified()}?:0L\n        fun size(v:Long)=when{v<1024L->"$v B";v<1024L*1024L->String.format(Locale.US,"%.1f KB",v/1024.0);else->String.format(Locale.US,"%.1f MB",v/(1024.0*1024.0))}\n        val at=if(latest<=0L)"—" else SimpleDateFormat("HH:mm:ss dd/MM/yyyy",Locale.US).format(Date(latest))\n        return "${files.size} tệp • ${size(bytes)} • mới nhất $at"\n    }\n\n'''
    l = replace_once(l, summary_anchor, summary_anchor + '\n' + summary_fun, "log-summary")
    LOGS.write_text(l, encoding="utf-8")

print("Applied S54 Beta48 owner 10 fixes")
