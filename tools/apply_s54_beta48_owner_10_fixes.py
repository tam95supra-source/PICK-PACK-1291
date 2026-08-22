#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
TRANSPORT = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt"
STORE = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt"
LOGS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/LocalLogManager.kt"
MARK = "S54_BETA48_OWNER_10_FIXES"
DATE_ERR = "BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW"


def sub1(src: str, pattern: str, repl: str, name: str, flags: int = 0) -> str:
    out, n = re.subn(pattern, repl, src, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f"S54 {name} structural mismatch: {n}")
    return out


# ---------------------------------------------------------------------------
# OperationsActivity: owner-facing Beta48 behavior/UI
# ---------------------------------------------------------------------------
s = OPS.read_text(encoding="utf-8")
if MARK not in s:
    # History: current calendar day is always selected, even if it has no data yet.
    hs = s.find("    private fun historyScreen(){")
    he = s.find("\n    private fun ", hs + 20)
    if hs < 0 or he < 0:
        raise SystemExit("S54 historyScreen not found")
    hb = s[hs:he]
    hb = sub1(
        hb,
        r'(?:var|val)\s+selectedDate\s*=\s*[^;\n]+',
        'var selectedDate=operationalStore.businessDate()',
        "history-current-day",
    )
    hb = hb.replace("operationalStore.availableDates()", "operationalStore.historyWindowDates()")
    s = s[:hs] + hb + s[he:]

    # PACK: both shift mappings stay visible. Active leases are still enforced by Service options.
    s = s.replace("val selectedShift=shift.selectedItem.toString();", "")
    s = s.replace('if(p.optString("shift")!=selectedShift)continue;', "")
    s = s.replace('if(p.optString("shift")!=s.optString("shift"))continue;', "")
    if 'optString("shift")!=selectedShift' in s or 'optString("shift")!=s.optString("shift")' in s:
        raise SystemExit("S54 PACK shift filter remains")

    # Make shift identity visible in PACK choice labels when those exact label shapes exist.
    s = s.replace('labels.add("$table • ${p.optString("user_pack")}")', 'labels.add("$table • ${p.optString("user_pack")} • ${p.optString("shift")}")')
    s = s.replace('labels.add("$t • ${p.optString("user_pack")}")', 'labels.add("$t • ${p.optString("user_pack")} • ${p.optString("shift")}")')
    s = s.replace('labels.add("$table • $user")', 'labels.add("$table • $user • ${p.optString("shift")}")')
    s = s.replace('labels.add("$t • $u")', 'labels.add("$t • $u • ${p.optString("shift")}")')

    # Terminology and removal of internal/OWNER explanatory text.
    if "Không dùng User Pick" not in s:
        raise SystemExit("S54 User Pick label missing")
    s = s.replace("Không dùng User Pick", "Không dùng User hy1.outbound")
    s = re.sub(
        r'\s*selectionBox\.addView\(info\("Quản trị cao nhất có thể chọn nhiều lịch sử[^\"]*"\)\)',
        "",
        s,
        count=1,
    )
    s = s.replace(
        'setMessage("Mục đã chọn sẽ được ẩn khỏi lịch sử. Nếu dữ liệu nghiệp vụ còn chờ đồng bộ, ứng dụng vẫn gửi dữ liệu đó lên Service trước rồi mới ghi dấu xóa. Nhật ký ai xóa, lúc nào và xóa gì vẫn được giữ.")',
        'setMessage("Xóa các mục lịch sử đã chọn?")',
    )

    # Roughly 10% tighter global spacing, leaving touch targets/fonts unchanged.
    s = sub1(
        s,
        r'private fun body\(\)\s*=\s*column\(bg\)\.apply\{setPadding\(dp\(\d+\),dp\(\d+\),dp\(\d+\),dp\(\d+\)\)\}',
        'private fun body()=column(bg).apply{setPadding(dp(14),dp(13),dp(14),dp(83))}',
        "body-spacing",
    )
    s = sub1(
        s,
        r'private fun gap\(h:Int\)\s*=\s*Space\(this\)\.apply\{layoutParams=size\(1,dp\(h\)\)\}',
        'private fun gap(h:Int)=Space(this).apply{layoutParams=size(1,dp(((h*9)+5)/10))}',
        "gap-spacing",
    )

    # Selected PDA serial gets a dedicated highlighted panel.
    pda_pos = s.find("    private fun pdaInput(")
    if pda_pos < 0:
        raise SystemExit("S54 pdaInput not found")
    pda_helper = r'''    private fun pdaSelectedPanel(pdas:JSONArray,field:AutoCompleteTextView):TextView{
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
    s = s[:pda_pos] + pda_helper + s[pda_pos:]
    s = s.replace(
        'resourceBox.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));resourceBox.addView(gap(8));',
        'resourceBox.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));resourceBox.addView(gap(4));resourceBox.addView(pdaSelectedPanel(pdas,pdaField!!));resourceBox.addView(gap(8));',
    )
    s = s.replace(
        'box.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));box.addView(gap(8));',
        'box.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));box.addView(gap(4));box.addView(pdaSelectedPanel(pdas,pdaField!!));box.addView(gap(8));',
    )

    # Sync: cache footprint in "Trên thiết bị".
    s = sub1(
        s,
        r'"Dữ liệu chờ gửi"\s*to\s*pending\.toString\(\)\s*,\s*"Luồng trao đổi dữ liệu"',
        '"Dữ liệu chờ gửi" to pending.toString(),"Dung lượng cache" to humanBytes(operationalStore.storageBytes()),"Luồng trao đổi dữ liệu"',
        "sync-cache-size",
    )

    # Application section owns device name.
    la = s.find("        fun loadApp(){")
    lb = s.find("\n        fun load(){", la)
    if la < 0 or lb < 0:
        raise SystemExit("S54 loadApp boundaries not found")
    load_app = '''        fun loadApp(){appBox.removeAllViews();appBox.addView(section("ỨNG DỤNG"));val deviceName="${Build.MANUFACTURER} ${Build.MODEL}".trim();appBox.addView(details(listOf("Tên thiết bị" to deviceName,"Kênh phát hành" to if(BuildConfig.CHANNEL=="BETA")"Bản thử nghiệm" else "Bản ổn định","Phiên bản ứng dụng" to BuildConfig.VERSION_NAME,"Mã phiên bản" to BuildConfig.VERSION_CODE.toString())))}'''
    s = s[:la] + load_app + s[lb:]

    # Remove old standalone device-name settings block if present.
    s = re.sub(
        r'\n\s*body\.addView\(section\("THIẾT BỊ"\)\).*?(?=\n\s*body\.addView\(section\("NHẬT KÝ"\)\))',
        "\n",
        s,
        count=1,
        flags=re.S,
    )

    # Useful local log information.
    log_marker = 'body.addView(section("NHẬT KÝ"))'
    if log_marker in s:
        s = s.replace(log_marker, log_marker + ';body.addView(details(listOf("Nhật ký trên thiết bị" to LocalLogManager.summary(this))))', 1)

    # Human-readable byte formatter.
    hp = s.find("    private fun dash(v:String)=")
    if hp < 0:
        raise SystemExit("S54 dash helper not found")
    human = '    private fun humanBytes(bytes:Long):String=when{bytes<1024L->"$bytes B";bytes<1024L*1024L->String.format(java.util.Locale.US,"%.1f KB",bytes/1024.0);bytes<1024L*1024L*1024L->String.format(java.util.Locale.US,"%.1f MB",bytes/(1024.0*1024.0));else->String.format(java.util.Locale.US,"%.2f GB",bytes/(1024.0*1024.0*1024.0))}\n'
    s = s[:hp] + human + s[hp:]

    if "Quản trị cao nhất có thể chọn nhiều lịch sử" in s:
        raise SystemExit("S54 internal OWNER copy remains")
    if "Không dùng User Pick" in s:
        raise SystemExit("S54 legacy Pick label remains")

    s = s.replace("class OperationsActivity : Activity() {", "class OperationsActivity : Activity() {\n    // S54_BETA48_OWNER_10_FIXES", 1)
    OPS.write_text(s, encoding="utf-8")


# ---------------------------------------------------------------------------
# M2ServiceTransport: APP/WEB connection endpoint. Date recovery is Store-side.
# ---------------------------------------------------------------------------
t = TRANSPORT.read_text(encoding="utf-8")
if MARK not in t:
    t = sub1(
        t,
        r'val r\s*=\s*httpJson\("\$base/v1/legacy-sync",\s*request,\s*token\)',
        'val r = if(action=="service_connections") httpGetJson("$base/v1/service/connections",token) else httpJson("$base/v1/legacy-sync", request, token)',
        "connections-route",
    )
    t = sub1(
        t,
        r'val SYNC_ACTIONS\s*=\s*setOf\(([^)]*)\)',
        lambda m: m.group(0) if "service_connections" in m.group(1) else 'val SYNC_ACTIONS = setOf(' + m.group(1).rstrip() + ', "service_connections")',
        "connections-action",
    )
    ga = t.find("    private fun validServiceUrl(raw: String): Boolean = runCatching {")
    if ga < 0:
        raise SystemExit("S54 validServiceUrl anchor not found")
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
    t = t[:ga] + get_fun + t[ga:]
    t = sub1(
        t,
        r'class M2ServiceTransport\s*\(\s*context\s*:\s*Context\s*\)\s*\{',
        'class M2ServiceTransport(context: Context) {\n    // S54_BETA48_OWNER_10_FIXES\n    // retryDateWindowRejects is handled by durable OperationalDataStore selection.',
        "transport-marker",
    )
    TRANSPORT.write_text(t, encoding="utf-8")


# ---------------------------------------------------------------------------
# OperationalDataStore: rolling calendar, cache bytes, exact-ID legacy recovery
# ---------------------------------------------------------------------------
d = STORE.read_text(encoding="utf-8")
if MARK not in d:
    if "import java.util.Calendar" not in d:
        if "import java.util.Date\n" not in d:
            raise SystemExit("S54 Date import not found")
        d = d.replace("import java.util.Date\n", "import java.util.Date\nimport java.util.Calendar\n", 1)

    # Preserve immutable event bodies/IDs. Only the one obsolete backend-date rejection becomes due again.
    pending_old = '"status IN (\'LOCAL_PENDING\',\'PENDING\',\'RETRY\',\'OFFLINE_PROVISIONAL\') AND next_attempt_at <= ?"'
    pending_new = '"(status IN (\'LOCAL_PENDING\',\'PENDING\',\'RETRY\',\'OFFLINE_PROVISIONAL\') OR (status=\'REJECTED\' AND last_error=\'BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW\')) AND next_attempt_at <= ?"'
    if pending_old not in d:
        raise SystemExit("S54 pendingMutations selector not found")
    d = d.replace(pending_old, pending_new, 1)
    count_old = '"SELECT COUNT(*) FROM mutation_outbox WHERE status IN (\'LOCAL_PENDING\',\'PENDING\',\'RETRY\',\'OFFLINE_PROVISIONAL\')"'
    count_new = '"SELECT COUNT(*) FROM mutation_outbox WHERE status IN (\'LOCAL_PENDING\',\'PENDING\',\'RETRY\',\'OFFLINE_PROVISIONAL\') OR (status=\'REJECTED\' AND last_error=\'BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW\')"'
    if count_old not in d:
        raise SystemExit("S54 pendingMutationCount selector not found")
    d = d.replace(count_old, count_new, 1)

    # Add app context without assuming where S44 placed the helper field.
    d = sub1(
        d,
        r'class OperationalDataStore\s*\(\s*context\s*:\s*Context\s*\)\s*\{',
        'class OperationalDataStore(context: Context) {\n    // S54_BETA48_OWNER_10_FIXES\n    private val app = context.applicationContext',
        "store-marker",
    )

    dp = d.find("    fun revisions(")
    if dp < 0:
        raise SystemExit("S54 revisions function not found")
    dates_fun = '''    fun historyWindowDates():List<String>{
        val cal=Calendar.getInstance(TimeZone.getTimeZone(TZ));val out=ArrayList<String>(7)
        repeat(7){out+=isoDate(cal.time);cal.add(Calendar.DAY_OF_MONTH,-1)}
        return out
    }

    fun storageBytes():Long{
        val main=app.getDatabasePath(DB_NAME);val base=main.absolutePath
        return listOf(main,java.io.File(base+"-wal"),java.io.File(base+"-shm"),java.io.File(base+"-journal")).filter{it.exists()}.sumOf{it.length()}
    }

'''
    d = d[:dp] + dates_fun + d[dp:]

    rp = d.find("    fun markMutationSynced(")
    if rp < 0:
        raise SystemExit("S54 markMutationSynced function not found")
    retry_fun = '''    fun retryDateWindowRejects():Int=withDbLock{
        val db=writableDb();val now=System.currentTimeMillis();var count=0
        db.rawQuery("SELECT COUNT(*) FROM mutation_outbox WHERE status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW'",null).use{c->if(c.moveToFirst())count=c.getInt(0)}
        if(count>0)db.execSQL("UPDATE mutation_outbox SET status='RETRY',next_attempt_at=?,updated_at=? WHERE status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW'",arrayOf(now,now))
        count
    }

'''
    d = d[:rp] + retry_fun + d[rp:]
    STORE.write_text(d, encoding="utf-8")


# ---------------------------------------------------------------------------
# Local log metadata
# ---------------------------------------------------------------------------
l = LOGS.read_text(encoding="utf-8")
if MARK not in l:
    lp = l.find("    fun pendingCount(")
    if lp < 0:
        raise SystemExit("S54 pendingCount not found")
    le = l.find("\n", lp)
    if le < 0:
        raise SystemExit("S54 pendingCount line end not found")
    summary_fun = '''
    // S54_BETA48_OWNER_10_FIXES
    fun summary(context:Context):String{
        val files=logDir(context).listFiles()?.filter{it.isFile}.orEmpty();val bytes=files.sumOf{it.length()};val latest=files.maxOfOrNull{it.lastModified()}?:0L
        fun size(v:Long)=when{v<1024L->"$v B";v<1024L*1024L->String.format(Locale.US,"%.1f KB",v/1024.0);else->String.format(Locale.US,"%.1f MB",v/(1024.0*1024.0))}
        val at=if(latest<=0L)"—" else SimpleDateFormat("HH:mm:ss dd/MM/yyyy",Locale.US).format(Date(latest))
        return "${files.size} tệp • ${size(bytes)} • mới nhất $at"
    }
'''
    l = l[:le + 1] + summary_fun + l[le + 1:]
    LOGS.write_text(l, encoding="utf-8")

print("Applied direct structural S54 Beta48 owner 10 fixes")
