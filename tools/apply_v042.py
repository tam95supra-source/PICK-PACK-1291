import pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]

def read(p):
    return (ROOT / p).read_text(encoding='utf-8')

def write(p, s):
    q = ROOT / p
    q.parent.mkdir(parents=True, exist_ok=True)
    q.write_text(s, encoding='utf-8')

def must(s, old, new, label):
    if old not in s:
        raise SystemExit('missing replacement: ' + label)
    return s.replace(old, new, 1)

def rx(s, pattern, repl, label):
    out, n = re.subn(pattern, repl, s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f'{label}: replacements={n}')
    return out

# Exact owner-provided artwork already lives at drawable/app_icon.jpg.
# Use that bitmap directly as adaptive foreground with no redesign/inset.
p = 'app/src/main/res/drawable/app_icon_foreground.xml'
s = read(p)
s = s.replace('android:inset="14%"', 'android:inset="0%"')
write(p, s)

p = 'app/build.gradle.kts'
s = read(p)
s = must(s, 'versionCode = 6', 'versionCode = 7', 'beta versionCode')
s = must(s, 'versionName = "0.4.1-beta.1"', 'versionName = "0.4.2-beta.1"', 'beta versionName')
write(p, s)

cache = '''package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer
import java.util.concurrent.ConcurrentHashMap

object MasterDataCache {
    private const val PREFS = "pp1291_master_cache"
    private const val KEY_JSON = "snapshot"
    private const val KEY_REV = "revision"
    private const val KEY_AT = "saved_at"

    @Volatile private var memorySnapshot: JSONObject? = null
    @Volatile private var staffByMnv: Map<String, JSONObject> = emptyMap()
    @Volatile private var searchableStaff: List<Pair<String, JSONObject>> = emptyList()

    fun hydrate(context: Context) { snapshot(context) }

    @Synchronized
    fun save(context: Context, snapshot: JSONObject) {
        if (!snapshot.optBoolean("ok", false)) return
        val copy = JSONObject(snapshot.toString())
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_JSON, copy.toString())
            .putLong(KEY_REV, copy.optLong("master_revision", 0L))
            .putLong(KEY_AT, System.currentTimeMillis())
            .apply()
        install(copy)
    }

    fun snapshot(context: Context): JSONObject? {
        memorySnapshot?.let { return it }
        synchronized(this) {
            memorySnapshot?.let { return it }
            val raw = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_JSON, null) ?: return null
            val parsed = runCatching { JSONObject(raw) }.getOrNull() ?: return null
            install(parsed)
            return memorySnapshot
        }
    }

    private fun install(snapshot: JSONObject) {
        val byMnv = ConcurrentHashMap<String, JSONObject>()
        val searchable = ArrayList<Pair<String, JSONObject>>()
        val staff = snapshot.optJSONArray("staff") ?: JSONArray()
        for (i in 0 until staff.length()) {
            val e = staff.optJSONObject(i) ?: continue
            val mnv = e.optString("mnv").trim()
            if (mnv.isBlank()) continue
            byMnv[mnv] = e
            searchable += fold(mnv + " " + e.optString("full_name") + " " + e.optString("supplier") + " " + e.optString("main_position")) to e
        }
        staffByMnv = byMnv
        searchableStaff = searchable
        memorySnapshot = snapshot
    }

    fun revision(context: Context): Long = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_REV, 0L)
    fun savedAt(context: Context): Long = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_AT, 0L)

    fun staffCount(context: Context): Int {
        snapshot(context)
        return staffByMnv.size
    }

    fun employee(context: Context, mnv: String): JSONObject? {
        snapshot(context)
        return staffByMnv[mnv.trim()]?.let { JSONObject(it.toString()) }
    }

    fun allStaff(context: Context, limit: Int = 200): JSONArray {
        snapshot(context)
        val out = JSONArray()
        searchableStaff.take(limit).forEach { out.put(JSONObject(it.second.toString())) }
        return out
    }

    fun searchStaff(context: Context, query: String, limit: Int = 80): JSONArray {
        snapshot(context)
        val out = JSONArray()
        val q = fold(query)
        if (q.isBlank()) return allStaff(context, limit)
        for ((key, e) in searchableStaff) {
            if (key.contains(q)) {
                out.put(JSONObject(e.toString()))
                if (out.length() >= limit) break
            }
        }
        return out
    }

    private fun fold(v: String): String = Normalizer.normalize(v, Normalizer.Form.NFD)
        .replace(Regex("\\p{Mn}+"), "").uppercase().trim()
}
'''
write('app/src/main/java/vn/pickpack1291/app/beta/MasterDataCache.kt', cache)

p = 'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt'
s = read(p)
s = must(s, 'LocalLogManager.createDailyIfNeeded(this)\n        login()', 'LocalLogManager.createDailyIfNeeded(this)\n        MasterDataCache.hydrate(this)\n        login()', 'hydrate cache')
s = s.replace('body.addView(txt("App tự kiểm tra phiên bản mới khi mở/foreground.", 9.5f, muted, false).center())\n', '')

dashboard = '''    private fun dashboard() {
        currentScreen = "DASHBOARD"
        liveEmployeeMnv = ""
        val root = column(bg)
        root.addView(appBar("Trang chủ", false))
        val body = column(bg).apply { setPadding(dp(14), dp(15), dp(14), dp(54)) }
        body.addView(cardRow(
            tile("▣", "QUÉT QR NHÂN SỰ", blue) { employeeScan() },
            tile("⌕", "DANH SÁCH NHÂN SỰ", Color.rgb(58, 91, 183)) { openModule("STAFF") }
        ))
        if (accountRole == "ADMIN" || accountRole == "SUPERADMIN") {
            body.addView(cardRow(
                tile("◉", "CÔNG NHẬT", green) { openModule("LABOR") },
                tile("☷", "THEO DÕI CA", Color.rgb(91, 73, 183)) { openModule("LISTS") }
            ))
        } else {
            body.addView(fullCard("☷", "THEO DÕI CA", Color.rgb(91, 73, 183), dp(72)) { openModule("LISTS") })
        }
        body.addView(cardRow(
            tile("▥", "BÁO CÁO", teal) { openModule("REPORT") },
            tile("⚙", "CÀI ĐẶT", navy) { openModule("SETTINGS") }
        ))
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setScreen(root)
        refreshStatus()
    }

'''
s = rx(s, r'    private fun dashboard\(\) \{.*?\n    \}\n\n    private fun openModule', dashboard + '    private fun openModule', 'dashboard')
s = s.replace('body.addView(check, matchWrap()); body.addView(gap(12)); body.addView(info("Google Sheet xác định CHƯA VÀO / ĐANG TRONG PHIÊN / ĐÃ HẾT PHIÊN. Không còn nút VÀO/RA tách rời."))', 'body.addView(check, matchWrap())')
s = s.replace(';body.addView(gap(10));body.addView(info("Phiên hợp lệ đã kết thúc. Không cho VÀO lại cùng ngày bằng luồng thường."))', '')
old = '''    private fun loadEmployee(mnv: String, button: Button? = null) {
        api.call("employee_context", JSONObject().put("mnv", mnv)) { result -> runOnUiThread {'''
new = '''    private fun loadEmployee(mnv: String, button: Button? = null) {
        val cached = MasterDataCache.employee(this, mnv)
        if (cached != null && currentScreen == "SCAN") renderCachedEmployee(cached)
        api.call("employee_context", JSONObject().put("mnv", mnv)) { result -> runOnUiThread {'''
s = must(s, old, new, 'cached employee preview')
cached = '''    private fun renderCachedEmployee(e: JSONObject) {
        currentScreen = "EMPLOYEE_LOADING"
        val root=column(bg)
        root.addView(appBar("QUÉT QR NHÂN SỰ", true))
        val body=column(bg).apply{setPadding(dp(16),dp(14),dp(16),dp(58))}
        body.addView(employeeCard(e))
        body.addView(gap(10))
        body.addView(status("ĐANG KIỂM TRA PHIÊN...", blue, Color.rgb(237,244,255)))
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f))
        setScreen(root)
    }

'''
s = must(s, '    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {', cached + '    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {', 'cached renderer')
write(p, s)

p = 'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s = read(p)
s = s.replace('import android.text.InputType\n', 'import android.text.InputType\nimport android.text.Editable\nimport android.text.TextWatcher\n')
s = must(s, 'when(module){"LABOR"->laborHome();"RESOURCES"->resourceHome();"REPORT"->reportScreen();"SETTINGS"->settingsScreen();else->listsScreen()}', '''when(module){
            "LABOR"->laborHome()
            "RESOURCES"->resourceHome()
            "REPORT"->reportScreen()
            "SETTINGS"->settingsScreen()
            "STAFF"->staffScreen()
            else->listsScreen()
        }''', 'STAFF module')
s = s.replace('body.addView(txt("Quét/nhập MNV để bắt đầu hoặc kết thúc công nhật.",10.5f,muted,false));body.addView(gap(9))', 'body.addView(txt("Scan để bắt đầu hoặc kết thúc công nhật.",10.5f,muted,false));body.addView(gap(9))')
s = s.replace('val root=baseRoot("TÀI NGUYÊN");val body=body();body.addView(txt("Đổi vị trí/PDA/User Pick/Bàn Pack theo transaction khóa Google Sheet. Conflict không làm mất tài nguyên cũ.",10.5f,muted,false));body.addView(gap(9));val mnv=', 'val root=baseRoot("TÀI NGUYÊN");val body=body();val mnv=')
s = s.replace('body.addView(info("Công nhật chỉ thao tác khi nhân sự đang có phiên ACTIVE."));body.addView(gap(10));', '')
old = '''val note=input("Ghi chú (tùy chọn)",false);body.addView(labelled("Thông tin công nhật",typeSpinner));body.addView(gap(8));body.addView(labelled("Mốc thời gian",markerSpinner));body.addView(gap(8));body.addView(note,matchWrap());body.addView(gap(9));val start=primary("BẮT ĐẦU CÔNG NHẬT",green){};start.setOnClickListener{start.isEnabled=false;start.text="ĐANG GHI...";api.call("labor_start",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("labor_type",typeSpinner.selectedItem.toString()).put("time_marker",markerSpinner.selectedItem.toString()).put("note",note.text.toString()))'''
new = '''val note=input("Ghi chú (tùy chọn)",false);body.addView(labelled("Thông tin công nhật",typeSpinner));body.addView(gap(8));body.addView(labelled("Mốc thời gian",markerSpinner));body.addView(gap(8));val fixed=foldLocal(e.optString("main_position")).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val deduct=CheckBox(this).apply{text="Khấu trừ nhân sự";isChecked=false;isEnabled=!fixed;setTextColor(if(fixed)muted else ink);textSize=11f};body.addView(deduct,matchWrap());body.addView(gap(6));body.addView(note,matchWrap());body.addView(gap(9));val start=primary("BẮT ĐẦU CÔNG NHẬT",green){};start.setOnClickListener{start.isEnabled=false;start.text="ĐANG GHI...";api.call("labor_start",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("labor_type",typeSpinner.selectedItem.toString()).put("time_marker",markerSpinner.selectedItem.toString()).put("deduct_staff",deduct.isChecked&&!fixed).put("note",note.text.toString()))'''
s = must(s, old, new, 'labor deduction checkbox')
staff = '''    private fun staffScreen(){
        screenState = "STAFF"
        val root=baseRoot("DANH SÁCH NHÂN SỰ")
        val body=body()
        val q=input("Tìm MNV / họ tên",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH}
        body.addView(q,matchWrap());body.addView(gap(8))
        val box=column(bg);body.addView(box,matchWrap())
        fun render(query:String){
            box.removeAllViews()
            val a=MasterDataCache.searchStaff(this,query,100)
            for(i in 0 until a.length()){
                val e=a.optJSONObject(i)?:continue
                box.addView(listCard("${e.optString("mnv")} • ${e.optString("full_name")}","${dash(e.optString("main_position"))} • ${dash(e.optString("supplier"))}\\nNgày vào: ${dash(e.optString("start_date"))}"));box.addView(gap(6))
            }
            if(a.length()==0)box.addView(info("Không có kết quả."))
        }
        q.addTextChangedListener(object:TextWatcher{
            override fun beforeTextChanged(v:CharSequence?,start:Int,count:Int,after:Int)=Unit
            override fun onTextChanged(v:CharSequence?,start:Int,before:Int,count:Int){render(v?.toString().orEmpty())}
            override fun afterTextChanged(v:Editable?)=Unit
        })
        render("")
        attach(root,body)
        q.requestFocus()
    }

'''
s = must(s, '    private fun listsScreen(){', staff + '    private fun listsScreen(){', 'staff screen')
report = '''    private fun reportScreen(){
        screenState = "REPORT"
        val root=baseRoot("BÁO CÁO");val body=body()
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày"));body.addView(labelled("Phạm vi báo cáo",period));body.addView(gap(10))
        val box=column(bg);body.addView(box,matchWrap());box.addView(txt("Đang tải...",10.5f,muted,false))
        api.call("report_daily"){r->runOnUiThread{
            box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Không tải được báo cáo"));return@runOnUiThread}
            val rootJson=r.json?:JSONObject()
            fun render(){
                box.removeAllViews();val key=when(period.selectedItemPosition){0->"ca1_hc";1->"ca2";else->"all"};val p=rootJson.optJSONObject("reports")?.optJSONObject(key)?:JSONObject()
                box.addView(reportGrid("NGUỒN LỰC",p.optJSONObject("manpower"),"Vị trí","position"));box.addView(gap(10));box.addView(reportGrid("THÂM NIÊN",p.optJSONObject("tenure"),"Thâm niên","label"))
                if(isAdmin()){box.addView(gap(10));box.addView(supportGrid(rootJson.optJSONObject("support"))}
            }
            period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){render()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};render()
        }}
        attach(root,body)
    }

'''
s = rx(s, r'    private fun reportScreen\(\)\{.*?\n    \}\n\n    private fun settingsScreen', report + '    private fun settingsScreen', 'report screen')
helpers = '''    private fun reportGrid(title:String,data:JSONObject?,firstTitle:String,rowKey:String):View{
        val wrap=column(surface).apply{setPadding(dp(5),dp(7),dp(5),dp(7));background=outlineBg(surface,8)};wrap.addView(txt(title,12f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(6))})
        if(data==null){wrap.addView(txt("Chưa có dữ liệu",10f,muted,false));return wrap}
        val cols=jsonStrings(data.optJSONArray("columns"));val rows=data.optJSONArray("rows")?:JSONArray();val table=TableLayout(this).apply{isStretchAllColumns=true;isShrinkAllColumns=true}
        fun cell(v:String,bold:Boolean=false,header:Boolean=false)=TextView(this).apply{text=v;textSize=if(header)8.2f else 8.5f;setTextColor(if(header)navy else ink);typeface=if(bold)Typeface.DEFAULT_BOLD else Typeface.DEFAULT;gravity=Gravity.CENTER;setPadding(dp(2),dp(5),dp(2),dp(5));maxLines=3;background=GradientDrawable().apply{setColor(if(header)Color.rgb(232,241,246) else Color.WHITE);setStroke(dp(1),line)}}
        val hr=TableRow(this);hr.addView(cell(firstTitle,true,true));cols.forEach{hr.addView(cell(it,true,true))};hr.addView(cell("Tổng",true,true));table.addView(hr)
        for(i in 0 until rows.length()){val row=rows.optJSONObject(i)?:continue;val tr=TableRow(this);tr.addView(cell(row.optString(rowKey),true));val counts=row.optJSONObject("counts")?:JSONObject();cols.forEach{c->val n=counts.optInt(c);tr.addView(cell(if(n==0)"" else n.toString()))};val total=row.optInt("total");tr.addView(cell(if(total==0)"" else total.toString(),true));table.addView(tr)}
        val totals=data.optJSONObject("totals");if(totals!=null){val tr=TableRow(this);tr.addView(cell("Tổng",true,true));cols.forEach{c->val n=totals.optInt(c);tr.addView(cell(if(n==0)"" else n.toString(),true,true))};val total=data.optInt("total");tr.addView(cell(if(total==0)"" else total.toString(),true,true));table.addView(tr)}
        wrap.addView(table,matchWrap());return wrap
    }

    private fun supportGrid(data:JSONObject?):View{
        val wrap=column(surface).apply{setPadding(dp(5),dp(7),dp(5),dp(7));background=outlineBg(surface,8)};wrap.addView(txt("NHÂN SỰ ĐI HỖ TRỢ",12f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(6))})
        val table=TableLayout(this).apply{isStretchAllColumns=true;isShrinkAllColumns=true}
        fun cell(v:String,bold:Boolean=false,header:Boolean=false)=TextView(this).apply{text=v;textSize=8.8f;setTextColor(if(header)navy else ink);typeface=if(bold)Typeface.DEFAULT_BOLD else Typeface.DEFAULT;gravity=Gravity.CENTER;setPadding(dp(3),dp(5),dp(3),dp(5));maxLines=3;background=GradientDrawable().apply{setColor(if(header)Color.rgb(232,241,246) else Color.WHITE);setStroke(dp(1),line)}}
        val h=TableRow(this);h.addView(cell("Thông tin công nhật",true,true));h.addView(cell("Số lượng",true,true));h.addView(cell("Khấu trừ",true,true));table.addView(h)
        val rows=data?.optJSONArray("rows")?:JSONArray();for(i in 0 until rows.length()){val x=rows.optJSONObject(i)?:continue;val tr=TableRow(this);tr.addView(cell(x.optString("labor_type"),true));val q=x.optInt("quantity");val d=x.optInt("deduction");tr.addView(cell(if(q==0)"" else q.toString()));tr.addView(cell(if(d==0)"" else d.toString(),d>0));table.addView(tr)}
        wrap.addView(table,matchWrap());return wrap
    }

'''
s = must(s, '    private fun settingsScreen(){', helpers + '    private fun settingsScreen(){', 'report helpers')
s = s.replace('private fun dash(v:String)=v.takeIf{it.isNotBlank()&&it!="null"}?:"—"', 'private fun foldLocal(v:String)=java.text.Normalizer.normalize(v,java.text.Normalizer.Form.NFD).replace(Regex("\\\\p{Mn}+"),"").uppercase().trim()\n    private fun dash(v:String)=v.takeIf{it.isNotBlank()&&it!="null"}?:"—"')
write(p, s)

p = 'google-apps-script/PICK_PACK_API.gs'
s = read(p)
s = must(s, "api_version:'0.4.1'", "api_version:'0.4.2'", 'API version')
old = '''function ppLaborObj_(r) {
  return {mnv:r['Mã nhân viên']||'',business_date:ppBusinessIso_(),labor_type:r['Thông tin công nhật']||'',start_at:ppIsoFromVisible_(r['Thời gian bắt đầu']),end_at:ppIsoFromVisible_(r['Thời gian kết thúc']),time_marker:r['Mốc thời gian']||'',state:ppLaborState_(r),note:r['Ghi chú']||'',updated_at:ppIsoFromVisible_(r['Thời gian cập nhật'])};
}'''
new = '''function ppLaborObj_(r) {
  return {mnv:r['Mã nhân viên']||'',business_date:ppBusinessIso_(),labor_type:r['Thông tin công nhật']||'',start_at:ppIsoFromVisible_(r['Thời gian bắt đầu']),end_at:ppIsoFromVisible_(r['Thời gian kết thúc']),time_marker:r['Mốc thời gian']||'',state:ppLaborState_(r),note:r['Ghi chú']||'',deduct_staff:ppFold_(r['Khấu trừ nhân sự'])==='CO',updated_at:ppIsoFromVisible_(r['Thời gian cập nhật'])};
}'''
s = must(s, old, new, 'labor object')
old = "  const mnv=String(body.mnv||'').trim(),eventId=String(body.event_id||'').trim(),type=String(body.labor_type||'').trim(),marker=String(body.time_marker||'Trong ngày').trim(),note=String(body.note||'').trim(); if(!mnv||!eventId||!type)return {ok:false,error:'LABOR_FIELDS_INVALID'}; if(ppEventExists_(eventId))return {ok:true,idempotent:true};"
new = "  const mnv=String(body.mnv||'').trim(),eventId=String(body.event_id||'').trim(),type=String(body.labor_type||'').trim(),marker=String(body.time_marker||'Trong ngày').trim(),note=String(body.note||'').trim(); let deduct=body.deduct_staff===true||ppFold_(body.deduct_staff)==='CO'; if(!mnv||!eventId||!type)return {ok:false,error:'LABOR_FIELDS_INVALID'}; if(ppEventExists_(eventId))return {ok:true,idempotent:true};"
s = must(s, old, new, 'labor deduction parse')
old = "  const e=ppLookupStaff_(mnv)||s.employee_snapshot; ppEnsureOperationalHeaders_(); ppSheet_(PP.LABOR).appendRow([ppBusinessVisible_(),s.shift,mnv,e.full_name,e.phone,e.supplier,e.department,e.site,e.warehouse,e.main_position,ppWorkLabel_(s.work_choice),type,ppNowVisible_(),'',marker,'Đang làm',note,auth.login_id,ppNowVisible_(),eventId,'',ppRevision_()+1]); const rev=ppBumpRevision_();"
new = "  const e=ppLookupStaff_(mnv)||s.employee_snapshot; const fixed=ppFold_(e.main_position).indexOf('KEO HANG')>=0||ppFold_(e.main_position).indexOf('TO TRUONG')>=0; if(fixed)deduct=false; ppEnsureOperationalHeaders_(); ppSheet_(PP.LABOR).appendRow([ppBusinessVisible_(),s.shift,mnv,e.full_name,e.phone,e.supplier,e.department,e.site,e.warehouse,e.main_position,ppWorkLabel_(s.work_choice),type,ppNowVisible_(),'',marker,'Đang làm',note,auth.login_id,ppNowVisible_(),eventId,'',ppRevision_()+1,deduct?'Có':'Không']); const rev=ppBumpRevision_();"
s = must(s, old, new, 'labor deduction append')
report = '''function ppSupplierCode_(v) {
  const f=ppFold_(v);
  if(f==='NGUON LUC VIET')return 'NLV'; if(f==='HOA ANH DAO')return 'HAD'; if(f==='VIET WORK')return 'VW'; if(f==='MAN POWER')return 'MP'; if(f==='MEGA LINK')return 'MGL'; if(f==='HA GIA PHAT')return 'HGP'; if(f==='INHOUSE')return 'IH'; return '';
}
function ppReportPosition_(e) {
  const p=ppFold_(e.main_position),d=ppFold_(e.department);
  if(p==='PICK')return 'Picker'; if(p==='PACK')return 'Packer'; if(p==='TRUONG NHOM')return 'Trưởng nhóm'; if(p==='CHUYEN VIEN')return 'Chuyên viên'; if(p==='TO TRUONG')return 'Tổ trưởng'; if(p==='KEO HANG')return 'Kéo hàng'; if(p==='5S')return '5S'; if(p==='PHUC LONG')return 'Phúc Long';
  if(p.indexOf('DIEU PHOI')>=0){if(d.indexOf('PICK PACK')>=0)return 'Điều phối khu pack';if(d.indexOf('GIAO VAN')>=0||d.indexOf('OUTBOUND')>=0)return 'Điều phối khu chờ xuất';return 'Điều phối';}
  return e.main_position||'Khác';
}
function ppTenureDays_(startDate) {
  if(!startDate)return 99999;
  try{const d=Utilities.parseDate(String(startDate),PP.TZ,'dd/MM/yyyy');const now=Utilities.parseDate(ppBusinessVisible_(),PP.TZ,'dd/MM/yyyy');return Math.floor((now.getTime()-d.getTime())/86400000);}catch(_){return 99999;}
}
function ppReportMatrix_(sessions) {
  const supplierOrder=['IH','NLV','VW','MP','HGP','MGL','HAD'];const positionOrder=['Trưởng nhóm','Chuyên viên','Tổ trưởng','Điều phối khu pack','Điều phối khu chờ xuất','Điều phối','Kéo hàng','5S','Picker','Packer','Phúc Long'];const rows={},totals={};supplierOrder.forEach(function(c){totals[c]=0;});
  sessions.forEach(function(x){const e=ppLookupStaff_(x.mnv)||x.employee_snapshot||{},c=ppSupplierCode_(e.supplier);if(!c)return;const pos=ppReportPosition_(e);if(!rows[pos]){rows[pos]={position:pos,counts:{},total:0};supplierOrder.forEach(function(k){rows[pos].counts[k]=0;});}rows[pos].counts[c]++;rows[pos].total++;totals[c]++;});
  const active=supplierOrder.filter(function(c){return totals[c]>0;});const list=Object.keys(rows).map(function(k){return rows[k];}).filter(function(r){return r.total>0;});list.sort(function(a,b){const ia=positionOrder.indexOf(a.position),ib=positionOrder.indexOf(b.position);return (ia<0?999:ia)-(ib<0?999:ib)||a.position.localeCompare(b.position);});return {columns:active,rows:list,totals:totals,total:list.reduce(function(n,r){return n+r.total;},0)};
}
function ppTenureMatrix_(sessions) {
  const supplierOrder=['IH','NLV','VW','MP','HGP','MGL','HAD'],totals={};supplierOrder.forEach(function(c){totals[c]=0;});const rows=[{label:'Nhân sự mới ≤ 30 ngày',counts:{},total:0},{label:'Nhân sự cũ > 30 ngày',counts:{},total:0}];rows.forEach(function(r){supplierOrder.forEach(function(c){r.counts[c]=0;});});sessions.forEach(function(x){const e=ppLookupStaff_(x.mnv)||x.employee_snapshot||{},c=ppSupplierCode_(e.supplier);if(!c)return;const ix=ppTenureDays_(e.start_date)<=30?0:1;rows[ix].counts[c]++;rows[ix].total++;totals[c]++;});const active=supplierOrder.filter(function(c){return totals[c]>0;});return {columns:active,rows:rows,totals:totals,total:rows[0].total+rows[1].total};
}
function ppReportPeriod_(sessions,mode) {let items=sessions;if(mode==='ca1_hc')items=sessions.filter(function(x){return x.shift==='Ca 1'||x.shift==='Ca HC';});else if(mode==='ca2')items=sessions.filter(function(x){return x.shift==='Ca 2';});return {manpower:ppReportMatrix_(items),tenure:ppTenureMatrix_(items)};}
function ppReportDaily_() {
  const sm=ppSessionMap_(ppBusinessVisible_()),sessions=Object.keys(sm).map(function(k){return sm[k];});const laborRows=ppLaborRows_().filter(function(r){return r['Ngày']===ppBusinessVisible_();});const supportMap={};laborRows.forEach(function(r){const type=r['Thông tin công nhật']||'Khác';if(!supportMap[type])supportMap[type]={labor_type:type,quantity:0,deduction:0};supportMap[type].quantity++;if(ppFold_(r['Khấu trừ nhân sự'])==='CO')supportMap[type].deduction++;});const support=Object.keys(supportMap).map(function(k){return supportMap[k];}).sort(function(a,b){return b.quantity-a.quantity||a.labor_type.localeCompare(b.labor_type);});return {ok:true,business_date:ppBusinessIso_(),report_version:'0.4.2',reports:{ca1_hc:ppReportPeriod_(sessions,'ca1_hc'),ca2:ppReportPeriod_(sessions,'ca2'),all:ppReportPeriod_(sessions,'all')},support:{rows:support,total:support.reduce(function(n,x){return n+x.quantity;},0),deduction_total:support.reduce(function(n,x){return n+x.deduction;},0)}};
}'''
s = rx(s, r'function ppReportDaily_\(\) \{.*?\n\}\nfunction ppStaffSearch_', report + '\nfunction ppStaffSearch_', 'report backend')
old = "const lb=ppSheet_(PP.LABOR); if(lb.getRange(1,20).getValue()!=='Event ID')lb.getRange(1,20,1,3).setValues([['Event ID','Finish Event ID','App revision']]);"
new = "const lb=ppSheet_(PP.LABOR); if(lb.getRange(1,20).getValue()!=='Event ID')lb.getRange(1,20,1,3).setValues([['Event ID','Finish Event ID','App revision']]); if(lb.getRange(1,23).getValue()!=='Khấu trừ nhân sự')lb.getRange(1,23).setValue('Khấu trừ nhân sự');"
s = must(s, old, new, 'labor W header')
write(p, s)

print('v0.4.2 patch complete')
