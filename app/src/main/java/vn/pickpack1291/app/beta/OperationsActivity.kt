package vn.pickpack1291.app.beta

import android.app.Activity
import android.app.AlertDialog
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.text.Editable
import android.text.TextWatcher
import android.text.method.DigitsKeyListener
import android.view.KeyEvent
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.inputmethod.EditorInfo
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID

class OperationsActivity : Activity() {
    private val navy:Int get()=ThemeManager.primaryDark(this)
    private val blue:Int get()=ThemeManager.primary(this)
    private val red = Color.rgb(218,45,53)
    private val green = Color.rgb(36,153,85)
    private val orange = Color.rgb(217,119,6)
    private val teal:Int get()=ThemeManager.primary(this)
    private val accent:Int get()=ThemeManager.accent(this)
    private val bg:Int get()=ThemeManager.background(this)
    private val surface = Color.WHITE
    private val ink = Color.rgb(24,44,42)
    private val muted = Color.rgb(100,116,139)
    private val line:Int get()=ThemeManager.line(this)
    private val api by lazy { BetaApiClient(applicationContext) }
    private val syncApi by lazy { BetaApiClient(applicationContext) }
    private val cacheApi by lazy { BetaApiClient(applicationContext) }

    private lateinit var module: String
    private lateinit var login: String
    private lateinit var name: String
    private lateinit var role: String
    private var position = ""
    private var email = ""
    private var initialMnv = ""
    private var screenState = "ROOT"
    private var networkStatusText: TextView? = null
    private var syncStatusText: TextView? = null
    private var serviceStatusText: TextView? = null
    private var lastConnected: Boolean? = null
    private var contentHost: FrameLayout? = null
    private var navHost: FrameLayout? = null
    private data class NavRefs(val cell:LinearLayout,val icon:ImageView,val label:TextView)
    private val navRefs=mutableMapOf<String,NavRefs>()
    private var liveEmployeeMnv=""
    private val foregroundSync by lazy {
        ForegroundSyncCoordinator(this, syncApi, object : ForegroundSyncCoordinator.Listener {
            override fun onStatus(status: ForegroundSyncCoordinator.Status) {
                UpdateManager.check(this@OperationsActivity)
                lastConnected = status.connected
                refreshHeaderConnection()
                if(status.masterChanged || status.masterRevision != MasterDataCache.revision(this@OperationsActivity)) refreshMasterCache()
                if (!status.connected || !status.changed) return
                if(module=="BUSINESS" && liveEmployeeMnv.isNotBlank()){ loadEmployee(liveEmployeeMnv); return }
                when (screenState) {
                    "LISTS" -> listsScreen()
                    "REPORT" -> reportScreen()
                }
            }

            override fun onAuthExpired() { api.clearSession(); finishAffinity() }
        })
    }

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.statusBarColor = ThemeManager.primaryDark(this)
        window.navigationBarColor = Color.WHITE
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        module = intent.getStringExtra("module") ?: "BUSINESS"
        login = intent.getStringExtra("login") ?: ""
        name = intent.getStringExtra("name") ?: login
        role = intent.getStringExtra("role") ?: "USER"
        position = intent.getStringExtra("position") ?: ""
        email = intent.getStringExtra("email") ?: api.restoredAccount()?.optString("email").orEmpty()
        initialMnv = intent.getStringExtra("mnv") ?: ""
        if (api.token == null) { finish(); return }
        when(module){
            "BUSINESS"->businessHome()
            "LABOR"->{module="BUSINESS";laborHome()}
            "RESOURCES"->{module="BUSINESS";resourceHome()}
            "REPORT"->{module="BUSINESS";reportScreen()}
            "LISTS"->{module="BUSINESS";listsScreen()}
            "SETTINGS"->settingsScreen()
            "STAFF"->staffScreen()
            "HISTORY"->historyScreen()
            "SYNC"->syncScreen()
            else->{module="BUSINESS";businessHome()}
        }
    }

    override fun onStart() {
        super.onStart()
        UpdateManager.check(this, force = true)
        if (api.token != null) foregroundSync.start()
    }

    override fun onStop() {
        foregroundSync.stop()
        super.onStop()
    }

    private fun isAdmin() = role == "ADMIN" || role == "SUPERADMIN"
    private fun isSuper() = role == "SUPERADMIN"

    private fun businessHome(){
        module="BUSINESS"
        screenState="BUSINESS"
        initialMnv=""
        liveEmployeeMnv=""
        val root=baseRoot("Nghiệp vụ")
        val body=body()
        body.addView(gap(3))
        val qrCard=businessCard(R.drawable.ic_pp_scan,"Quét QR nhân sự","Vào ca / ra ca"){ employeeScan() }
        val laborCard=businessCard(R.drawable.ic_pp_task,"Công nhật","Bắt đầu / hoàn thành"){ laborHome() }
        val reportCard=businessCard(R.drawable.ic_pp_report,"Báo cáo nhân sự","Theo ca / theo ngày"){ reportScreen() }
        val resourceCard=businessCard(R.drawable.ic_pp_resource,"Tài nguyên","PDA / Pick / Pack"){ resourceHome() }
        body.addView(businessRow(qrCard,laborCard))
        body.addView(gap(10))
        body.addView(businessRow(reportCard,resourceCard))
        attach(root,body)
    }

    private fun employeeScan() {
        screenState = "SCAN"; liveEmployeeMnv = ""
        val root=column(bg);root.addView(appBar("QUÉT QR NHÂN SỰ"))
        val body=column(bg).apply{setPadding(dp(16),dp(16),dp(16),dp(92))}
        val mnv=mnvInput("Quét QR hoặc nhập MNV")
        body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(6))
        var busy=false
        fun submit(){val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét MNV.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);mnv.postDelayed({busy=false},600)}
        bindScannerEnter(mnv){submit()}
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);mnv.requestFocus()
    }

    private fun loadEmployee(mnv: String, button: Button? = null) {
        val cached = MasterDataCache.employee(this, mnv)
        if (cached != null && screenState == "SCAN") renderCachedEmployee(cached)
        api.call("employee_context", JSONObject().put("mnv", mnv).put("include_options", false).put("include_labor", false)) { result -> runOnUiThread {
            button?.isEnabled=true; button?.text="KIỂM TRA"
            if(result.code==401){sessionExpired();return@runOnUiThread}
            if(!result.ok){showError(result.error ?: "Không kiểm tra được MNV");return@runOnUiThread}
            val ctx=result.json ?: JSONObject()
            if(ctx.optString("state")=="NOT_ENTERED") {
                val localOptions = MasterDataCache.resourceOptions(this@OperationsActivity)
                if (localOptions.optJSONArray("pdas") != null) {
                    renderEmployee(ctx, localOptions)
                } else {
                    api.call("master_options", JSONObject().put("mnv", mnv)) { masters -> runOnUiThread {
                        if(masters.code==401){sessionExpired();return@runOnUiThread}
                        renderEmployee(ctx, masters.json ?: JSONObject())
                    } }
                }
            } else renderEmployee(ctx, null)
        } }
    }

    private fun renderCachedEmployee(e: JSONObject) {
        screenState = "EMPLOYEE_LOADING"
        val root=column(bg)
        root.addView(appBar("QUÉT QR NHÂN SỰ"))
        val body=column(bg).apply{setPadding(dp(16),dp(14),dp(16),dp(58))}
        body.addView(employeeCard(e))
        body.addView(gap(10))
        body.addView(status("ĐANG KIỂM TRA PHIÊN...", blue, Color.rgb(237,244,255)))
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f))
        setScreen(root)
    }

    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {
        screenState = "EMPLOYEE"
        val e=ctx.optJSONObject("employee") ?: JSONObject(); val state=ctx.optString("state"); val mnv=e.optString("mnv")
        liveEmployeeMnv = mnv
        val root=column(bg); root.addView(appBar("QUÉT QR NHÂN SỰ")); val body=column(bg).apply{setPadding(dp(16),dp(14),dp(16),dp(58))}
        body.addView(primary("QUÉT / NHẬP MNV KHÁC", navy) { employeeScan() }, matchWrap());body.addView(gap(10));body.addView(employeeCard(e));body.addView(gap(11))
        when(state){
            "ACTIVE" -> renderActive(body, ctx)
            "ENDED" -> renderEnded(body, ctx)
            else -> renderEnter(body, ctx, masters ?: JSONObject())
        }
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root)
    }

    private fun renderActive(body: LinearLayout, ctx: JSONObject) {
        val s=ctx.optJSONObject("session") ?: JSONObject(); val mnv=s.optString("mnv")
        body.addView(status("ĐANG TRONG PHIÊN", green, Color.rgb(235,248,239)));body.addView(gap(8));body.addView(details(listOf(
            "Ca" to s.optString("shift"), "Vị trí trong ca" to s.optString("work_choice"), "Vào lúc" to formatIso(s.optString("enter_at")),
            "PDA" to dash(s.optString("pda_serial")), "User Pick" to dash(s.optString("user_pick")), "Bàn Pack" to dash(s.optString("pack_table")), "User Pack" to dash(s.optString("user_pack"))
        )));body.addView(gap(10))
        body.addView(primary("ĐỔI TÀI NGUYÊN / VỊ TRÍ", orange) { initialMnv=mnv; resourceHome() }, matchWrap());body.addView(gap(8))
        val exit=primary("RA CA", red) {}
        exit.setOnClickListener { AlertDialog.Builder(this).setTitle("Xác nhận RA CA").setMessage("Kết thúc phiên của MNV $mnv và trả tài nguyên đang giữ?").setNegativeButton("Hủy",null).setPositiveButton("RA CA"){_,_->
            exit.isEnabled=false;exit.text="ĐANG RA CA...";api.call("exit",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv)){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(!r.ok)showError(r.error?:"RA CA thất bại")else loadEmployee(mnv)}}
        }.show() }
        body.addView(exit, matchWrap())
    }

    private fun renderEnded(body: LinearLayout, ctx: JSONObject) {
        val s=ctx.optJSONObject("session") ?: JSONObject();body.addView(status("ĐÃ HẾT PHIÊN VÀO / RA HÔM NAY", red, Color.rgb(255,238,239)));body.addView(gap(8));body.addView(details(listOf("Ca" to s.optString("shift"),"Vị trí trong ca" to s.optString("work_choice"),"Vào lúc" to formatIso(s.optString("enter_at")),"Ra lúc" to formatIso(s.optString("exit_at")))))
    }

    private fun renderEnter(body: LinearLayout, ctx: JSONObject, masters: JSONObject) {
        val e=ctx.optJSONObject("employee") ?: JSONObject(); val mnv=e.optString("mnv")
        body.addView(status("CHƯA VÀO CA", teal, Color.rgb(232, 248, 245)));body.addView(gap(8));body.addView(section("PHÂN CÔNG TRONG CA"))
        val shift=spinner(catalogValues("VÀO - RA TRONG CA_Ca",listOf("Ca 1","Ca 2","Ca HC")).toTypedArray());val choice=spinner(arrayOf("KHÔNG","PICK","PACK"));when{e.optString("main_position").contains("Pick",true)->choice.setSelection(1);e.optString("main_position").contains("Pack",true)->choice.setSelection(2)}
        body.addView(labelled("Ca làm việc",shift));body.addView(gap(8));body.addView(labelled("Vị trí trong ca",choice));body.addView(gap(8))
        val resourceBox=column(bg);body.addView(resourceBox,matchWrap())
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray()
        val pickValues=mutableListOf<String>();val packValues=mutableListOf<String>();var pdaField:AutoCompleteTextView?=null;var pickSpinner:Spinner?=null;var packSpinner:Spinner?=null
        fun rebuild(){resourceBox.removeAllViews();pickValues.clear();packValues.clear();pdaField=null;pickSpinner=null;packSpinner=null;when(choice.selectedItem.toString()){
            "PICK"->{pdaField=pdaInput(pdas);resourceBox.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));resourceBox.addView(gap(8));val labels=mutableListOf("Không dùng User Pick");pickValues.add("");for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){labels.add(v);pickValues.add(v)}};pickSpinner=spinner(labels.toTypedArray());resourceBox.addView(labelled("User Pick (tùy chọn)",pickSpinner!!))}
            "PACK"->{val labels=mutableListOf<String>();val selectedShift=shift.selectedItem.toString();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=selectedShift)continue;val table=p.optString("table");if(table.isNotBlank()){packValues.add(table);labels.add("$table • ${p.optString("user_pack")}")}};packSpinner=spinner((if(labels.isEmpty())listOf("Không có bàn Pack khả dụng")else labels).toTypedArray());resourceBox.addView(labelled("Bàn Pack + User Pack",packSpinner!!))}
            else->Unit}}
        choice.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};shift.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};rebuild();body.addView(gap(12))
        val enter=primary("VÀO CA",teal){}
        enter.setOnClickListener{val work=choice.selectedItem.toString();val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv).put("shift",shift.selectedItem.toString()).put("work_choice",work);if(work=="PICK"){val serial=resolvePda(pdas,pdaField?.text?.toString().orEmpty());if(serial==null){showError("Nhập đúng 5 số cuối seri PDA và chọn PDA trong danh sách gợi ý.");return@setOnClickListener};payload.put("pda_serial",serial);val pick=pickValues.getOrNull(pickSpinner?.selectedItemPosition?:0).orEmpty();if(pick.isNotBlank())payload.put("user_pick",pick)};if(work=="PACK"){if(packValues.isEmpty()){showError("Không còn bàn Pack khả dụng.");return@setOnClickListener};payload.put("pack_table",packValues[packSpinner?.selectedItemPosition?:0])};enter.isEnabled=false;enter.text="ĐANG VÀO CA...";api.call("enter",payload){r->runOnUiThread{enter.isEnabled=true;enter.text="VÀO CA";if(!r.ok)showError(r.error?:"VÀO CA thất bại")else loadEmployee(mnv)}}}
        body.addView(enter,matchWrap())
    }

    private fun laborHome(){
        screenState="LABOR_HOME"
        if(!isAdmin()){simpleMessage("CÔNG NHẬT","Chức năng Công nhật dành cho ADMIN/SUPERADMIN theo phân quyền hiện tại.");return}
        val root=baseRoot("CÔNG NHẬT");val body=body()
        val mnv=mnvInput("MNV").apply{setText(initialMnv)};body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(5))
        var busy=false
        fun submit(){val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập MNV.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;api.call("employee_context",JSONObject().put("mnv",v).put("include_labor",true).put("include_options",false)){r->runOnUiThread{busy=false;if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không kiểm tra được MNV");return@runOnUiThread};showLaborContext(r.json?:JSONObject(),MasterDataCache.snapshot(this@OperationsActivity)?:JSONObject())}}}
        bindScannerEnter(mnv){submit()};if(initialMnv.isNotBlank())mnv.post{submit()};attach(root,body);mnv.requestFocus()
    }

    private fun showLaborContext(ctx:JSONObject, masters:JSONObject){
        screenState = "LABOR_CONTEXT"
        val e=ctx.optJSONObject("employee")?:JSONObject();val state=ctx.optString("state");val active=ctx.optJSONObject("active_labor");val root=baseRoot("CÔNG NHẬT");val body=body();body.addView(employeeCard(e));body.addView(gap(10))
        if(state!="ACTIVE"){body.addView(status(if(state=="ENDED")"MNV ĐÃ HẾT PHIÊN" else "MNV CHƯA VÀO CA",red,Color.rgb(255,238,239)));body.addView(gap(9));body.addView(primary("MNV KHÁC",navy){initialMnv="";laborHome()},matchWrap());attach(root,body);return}
        val s=ctx.optJSONObject("session")?:JSONObject();body.addView(details(listOf("Ca" to s.optString("shift"),"Vị trí" to workText(s.optString("work_choice")),"Vào lúc" to formatIso(s.optString("enter_at")))));body.addView(gap(10))
        if(active!=null){body.addView(status("ĐANG LÀM CÔNG NHẬT",green,Color.rgb(235,248,239)));body.addView(gap(8));body.addView(details(listOf("Nội dung" to active.optString("labor_type"),"Bắt đầu" to formatIso(active.optString("start_at")),"Mốc thời gian" to active.optString("time_marker"),"Ghi chú" to dash(active.optString("note")))));body.addView(gap(9));val note=input("Ghi chú khi kết thúc (tùy chọn)",false);body.addView(note,matchWrap());body.addView(gap(9));val finish=primary("HOÀN THÀNH CÔNG NHẬT",red){};finish.setOnClickListener{finish.isEnabled=false;finish.text="ĐANG GHI...";api.call("labor_finish",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("note",note.text.toString())){r->runOnUiThread{finish.isEnabled=true;finish.text="HOÀN THÀNH CÔNG NHẬT";if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không kết thúc được công nhật")else{initialMnv=e.optString("mnv");laborHome()}}}};body.addView(finish,matchWrap())
        }else{
            body.addView(status("CHƯA CÓ CÔNG NHẬT ĐANG LÀM",blue,Color.rgb(237,244,255)));body.addView(gap(9));val types=catalogValues("CÔNG NHẬT_Thông tin công nhật",jsonStrings(masters.optJSONArray("labor_types")));val markers=catalogValues("CÔNG NHẬT_Mốc thời gian",jsonStrings(masters.optJSONArray("time_markers")));val typeSpinner=spinner((if(types.isEmpty())listOf("Khác")else types).toTypedArray());val markerSpinner=spinner((if(markers.isEmpty())listOf("Trong ngày")else markers).toTypedArray());val note=input("Ghi chú (tùy chọn)",false);body.addView(labelled("Thông tin công nhật",typeSpinner));body.addView(gap(8));body.addView(labelled("Mốc thời gian",markerSpinner));body.addView(gap(8));val fixedMain=foldLocal(e.optString("main_position")).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val deduct=CheckBox(this).apply{text="Khấu trừ nhân sự";isChecked=false;setTextColor(ink);textSize=11f};fun updateDeduct(){val fixedLabor=foldLocal(typeSpinner.selectedItem?.toString().orEmpty()).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val blocked=fixedMain||fixedLabor;deduct.isEnabled=!blocked;if(blocked)deduct.isChecked=false;deduct.setTextColor(if(blocked)muted else ink)};typeSpinner.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){updateDeduct()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};updateDeduct();body.addView(deduct,matchWrap());body.addView(gap(6));body.addView(note,matchWrap());body.addView(gap(9));val start=primary("BẮT ĐẦU CÔNG NHẬT",green){};start.setOnClickListener{start.isEnabled=false;start.text="ĐANG GHI...";api.call("labor_start",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("labor_type",typeSpinner.selectedItem.toString()).put("time_marker",markerSpinner.selectedItem.toString()).put("deduct_staff",deduct.isChecked&&deduct.isEnabled).put("note",note.text.toString())){r->runOnUiThread{start.isEnabled=true;start.text="BẮT ĐẦU CÔNG NHẬT";if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không bắt đầu được công nhật")else{initialMnv=e.optString("mnv");laborHome()}}}};body.addView(start,matchWrap())
        }
        body.addView(gap(9));body.addView(primary("MNV KHÁC",navy){initialMnv="";laborHome()},matchWrap());attach(root,body)
    }

    private fun resourceHome(){
        screenState="RESOURCE_HOME"
        val root=baseRoot("TÀI NGUYÊN");val body=body()
        val mnv=mnvInput("MNV").apply{setText(initialMnv)};body.addView(labelled("Mã nhân viên",mnv));var busy=false
        fun submit(){val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập MNV.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;api.call("employee_context",JSONObject().put("mnv",v)){r->runOnUiThread{if(handleAuth(r)){busy=false;return@runOnUiThread};if(!r.ok){busy=false;showError(r.error?:"Không kiểm tra được MNV");return@runOnUiThread};if(r.json?.optString("state")!="ACTIVE"){busy=false;showError("MNV phải đang trong phiên ACTIVE.");return@runOnUiThread};api.call("master_options",JSONObject().put("mnv",v)){m->runOnUiThread{busy=false;if(handleAuth(m))return@runOnUiThread;showResourceEditor(r.json?:JSONObject(),m.json?:JSONObject())}}}}}
        bindScannerEnter(mnv){submit()};if(initialMnv.isNotBlank())mnv.post{submit()};attach(root,body);mnv.requestFocus()
    }

    private fun showResourceEditor(ctx:JSONObject,masters:JSONObject){
        screenState = "RESOURCE_EDITOR"
        val e=ctx.optJSONObject("employee")?:JSONObject();val s=ctx.optJSONObject("session")?:JSONObject();val root=baseRoot("TÀI NGUYÊN");val body=body();body.addView(employeeCard(e));body.addView(gap(8));body.addView(details(listOf("Hiện tại" to workText(s.optString("work_choice")),"PDA" to dash(s.optString("pda_serial")),"User Pick" to dash(s.optString("user_pick")),"Bàn Pack" to dash(s.optString("pack_table")),"User Pack" to dash(s.optString("user_pack")))));body.addView(gap(10))
        val choice=spinner(arrayOf("KHÔNG","PICK","PACK"));choice.setSelection(when(s.optString("work_choice")){"PICK"->1;"PACK"->2;else->0});body.addView(labelled("Vị trí trong ca mới",choice));body.addView(gap(8));val box=column(bg);body.addView(box,matchWrap())
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray();val pickVals=mutableListOf<String>();val packVals=mutableListOf<String>();var pdaField:AutoCompleteTextView?=null;var pickSp:Spinner?=null;var packSp:Spinner?=null
        fun rebuild(){box.removeAllViews();pickVals.clear();packVals.clear();pdaField=null;pickSp=null;packSp=null;when(choice.selectedItem.toString()){
            "PICK"->{pdaField=pdaInput(pdas,s.optString("pda_serial"));box.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));box.addView(gap(8));val labels=mutableListOf("Không dùng User Pick");pickVals.add("");for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){labels.add(v);pickVals.add(v)}};pickSp=spinner(labels.toTypedArray());box.addView(labelled("User Pick (tùy chọn)",pickSp!!));val current=s.optString("user_pick");if(current.isNotBlank()){val ix=pickVals.indexOf(current);if(ix>=0)pickSp!!.setSelection(ix)}}
            "PACK"->{val labels=mutableListOf<String>();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=s.optString("shift"))continue;val t=p.optString("table");if(t.isNotBlank()){packVals.add(t);labels.add("$t • ${p.optString("user_pack")}")}};packSp=spinner(labels.toTypedArray());box.addView(labelled("Bàn Pack + User Pack",packSp!!));selectByValue(packSp!!,packVals,s.optString("pack_table"))}
            else->Unit}}
        choice.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};rebuild();body.addView(gap(12));val save=primary("CẬP NHẬT TÀI NGUYÊN",orange){};save.setOnClickListener{val work=choice.selectedItem.toString();val p=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("work_choice",work);if(work=="PICK"){val serial=resolvePda(pdas,pdaField?.text?.toString().orEmpty());if(serial==null){showError("Nhập đúng 5 số cuối seri PDA và chọn PDA trong danh sách gợi ý.");return@setOnClickListener};p.put("pda_serial",serial);val pick=pickVals.getOrNull(pickSp?.selectedItemPosition?:0).orEmpty();if(pick.isNotBlank())p.put("user_pick",pick)};if(work=="PACK"){if(packVals.isEmpty()){showError("Không có bàn Pack khả dụng.");return@setOnClickListener};p.put("pack_table",packVals[packSp?.selectedItemPosition?:0])};save.isEnabled=false;save.text="ĐANG CẬP NHẬT...";api.call("resource_change",p){r->runOnUiThread{save.isEnabled=true;save.text="CẬP NHẬT TÀI NGUYÊN";if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không đổi được tài nguyên")else{initialMnv=e.optString("mnv");resourceHome()}}}};body.addView(save,matchWrap());body.addView(gap(8));body.addView(primary("MNV KHÁC",navy){initialMnv="";resourceHome()},matchWrap());attach(root,body)
    }

    private fun staffScreen(){
        module="STAFF"
        screenState="STAFF"
        val root=baseRoot("NHÂN SỰ")
        val body=body()
        val searchRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL}
        val q=input("Tìm mã nhân viên hoặc họ tên",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH}
        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(50),1f))
        if(isAdmin()){
            searchRow.addView(gap(8))
            searchRow.addView(iconActionButton(R.drawable.ic_pp_add,teal,"Thêm nhân sự"){staffEditor(null)},size(dp(50),dp(50)))
        }
        body.addView(searchRow,matchWrap())
        body.addView(gap(11))
        val box=column(bg)
        body.addView(box,matchWrap())
        var pageSize=60

        fun render(query:String){
            box.removeAllViews()
            val clean=query.trim()
            val limit=if(clean.isBlank()) pageSize else 180
            val arr=MasterDataCache.searchStaff(this,clean,limit)
            for(i in 0 until arr.length()){
                val employee=arr.optJSONObject(i) ?: continue
                val card=column(surface).apply{
                    setPadding(dp(14),dp(12),dp(12),dp(12))
                    background=outlineBg(surface,18)
                    elevation=dp(3).toFloat()
                    val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL}
                    top.addView(iconBubble(R.drawable.ic_pp_staff,teal),size(dp(40),dp(40)))
                    top.addView(column(surface).apply{
                        addView(txt(employee.optString("full_name"),13.4f,ink,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
                        addView(txt(employee.optString("mnv"),9.8f,muted,false))
                    },LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(9)})
                    if(isAdmin()){
                        top.addView(iconActionButton(R.drawable.ic_pp_edit,teal,"Sửa"){staffEditor(employee)},size(dp(38),dp(38)))
                        top.addView(Space(this@OperationsActivity),size(dp(5),1))
                        top.addView(iconActionButton(R.drawable.ic_pp_delete,red,"Xóa"){confirmDeleteStaff(employee)},size(dp(38),dp(38)))
                    }
                    addView(top,matchWrap())
                    addView(gap(8))
                    addView(txt(listOf(dash(employee.optString("main_position")),dash(employee.optString("department")),dash(employee.optString("supplier"))).joinToString("  •  "),9.7f,muted,false).apply{maxLines=2})
                }
                box.addView(card,matchWrap())
                box.addView(gap(8))
            }
            if(arr.length()==0) box.addView(info("Không có nhân sự phù hợp."))
            if(clean.isBlank() && arr.length()>=pageSize && pageSize<MasterDataCache.staffCount(this)){
                val more=primary("XEM THÊM",teal){pageSize+=60;render("")}.apply{textSize=10.5f}
                box.addView(more,matchWrap())
            }
        }
        q.addTextChangedListener(object:TextWatcher{
            override fun beforeTextChanged(v:CharSequence?,s:Int,c:Int,a:Int)=Unit
            override fun onTextChanged(v:CharSequence?,s:Int,b:Int,c:Int){render(v?.toString().orEmpty())}
            override fun afterTextChanged(v:Editable?)=Unit
        })
        q.setOnEditorActionListener{_,_,_->render(q.text.toString());true}
        render("")
        attach(root,body)
    }

    private fun staffEditor(existing:JSONObject?){
        if(!isAdmin()) return
        val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))}
        val mnv=input("Mã nhân viên",false).apply{setText(existing?.optString("mnv").orEmpty());isEnabled=existing==null}
        val full=input("Họ và tên",false).apply{setText(existing?.optString("full_name").orEmpty())}
        val phone=input("Số điện thoại",false).apply{setText(existing?.optString("phone").orEmpty())}
        val pos=catalogSpinner("DANH SÁCH NHÂN SỰ_Vị trí chính",existing?.optString("main_position").orEmpty(),true)
        val supplier=catalogSpinner("DANH SÁCH NHÂN SỰ_Nhà cung cấp",existing?.optString("supplier").orEmpty(),true)
        val department=catalogSpinner("DANH SÁCH NHÂN SỰ_Bộ phận",existing?.optString("department").orEmpty(),true)
        val site=catalogSpinner("DANH SÁCH NHÂN SỰ_Site",existing?.optString("site").orEmpty(),true)
        val warehouse=catalogSpinner("DANH SÁCH NHÂN SỰ_Kho",existing?.optString("warehouse").orEmpty(),true)
        val startDate=input("Ngày bắt đầu dd/MM/yyyy",false).apply{setText(existing?.optString("start_date").orEmpty())}
        val note=input("Ghi chú",false).apply{setText(existing?.optString("note").orEmpty())}
        fun addField(label:String,view:View){box.addView(txt(label,10.2f,ink,true));box.addView(gap(4));box.addView(view,matchWrap());box.addView(gap(8))}
        addField("Mã nhân viên",mnv);addField("Họ và tên",full);addField("Số điện thoại",phone)
        addField("Vị trí chính",pos);addField("Nhà cung cấp",supplier);addField("Bộ phận",department);addField("Site",site);addField("Kho",warehouse)
        addField("Ngày bắt đầu làm việc",startDate);addField("Ghi chú",note)
        val scroller=ScrollView(this).apply{addView(box)}
        AlertDialog.Builder(this)
            .setTitle(if(existing==null) "Thêm nhân sự" else "Sửa nhân sự")
            .setView(scroller)
            .setNegativeButton("Hủy",null)
            .setPositiveButton("LƯU"){_,_->
                val id=mnv.text.toString().trim();val nm=full.text.toString().trim()
                if(id.isBlank()||nm.isBlank()){TopNotice.show(this,"MNV và họ tên là bắt buộc.",TopNotice.Kind.ERROR);return@setPositiveButton}
                val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id).put("full_name",nm)
                    .put("phone",phone.text.toString()).put("main_position",catalogSelection(pos)).put("supplier",catalogSelection(supplier))
                    .put("department",catalogSelection(department)).put("site",catalogSelection(site)).put("warehouse",catalogSelection(warehouse))
                    .put("start_date",startDate.text.toString()).put("note",note.text.toString())
                api.call("staff_upsert",payload){result->runOnUiThread{
                    if(handleAuth(result))Unit else if(!result.ok)showError(result.error?:"Không lưu được nhân sự") else reloadMaster{TopNotice.show(this,"Đã lưu nhân sự.",TopNotice.Kind.SUCCESS);staffScreen()}
                }}
            }.show()
    }

    private fun confirmDeleteStaff(employee:JSONObject){
        AlertDialog.Builder(this)
            .setTitle("Xóa nhân sự?")
            .setMessage("Xóa ${employee.optString("mnv")} • ${employee.optString("full_name")}? Lịch sử nghiệp vụ đã phát sinh vẫn được giữ.")
            .setNegativeButton("KHÔNG",null)
            .setPositiveButton("CÓ") { _,_ ->
                val payload=JSONObject()
                    .put("event_id",UUID.randomUUID().toString())
                    .put("mnv",employee.optString("mnv"))
                api.call("staff_delete",payload) { result ->
                    runOnUiThread {
                        if(handleAuth(result)) {
                            Unit
                        } else if(!result.ok) {
                            showError(result.error ?: "Không xóa được nhân sự")
                        } else {
                            reloadMaster {
                                TopNotice.show(this,"Đã xóa nhân sự.",TopNotice.Kind.SUCCESS)
                                staffScreen()
                            }
                        }
                    }
                }
            }
            .show()
    }

    private fun reloadMaster(done:()->Unit){
        cacheApi.call("master_snapshot") { result ->
            runOnUiThread {
                if(result.ok && result.json!=null) MasterDataCache.save(this,result.json)
                done()
            }
        }
    }

    private fun listsScreen(){
        screenState = "LISTS"
        val root=baseRoot("DANH SÁCH");val body=body();val q=input("Tìm MNV / họ tên",false).apply{setSingleLine(true)};body.addView(q,matchWrap());body.addView(gap(8));val buttons=row(bg);val sessions=smallButton("PHIÊN HÔM NAY",blue);val labor=smallButton("CÔNG NHẬT",green);val staff=smallButton("NHÂN SỰ",navy);buttons.addView(sessions,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginEnd=dp(3)});buttons.addView(labor,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3);marginEnd=dp(3)});buttons.addView(staff,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3)});body.addView(buttons,matchWrap());body.addView(gap(9));val box=column(bg);body.addView(box,matchWrap())
        fun loadSessions(){box.removeAllViews();box.addView(txt("Đang tải...",10.5f,muted,false));api.call("list_sessions",JSONObject().put("query",q.text.toString())){r->runOnUiThread{box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Lỗi"));return@runOnUiThread};val a=r.json?.optJSONArray("items")?:JSONArray();if(a.length()==0)box.addView(info("Chưa có phiên phù hợp."));for(i in 0 until a.length()){val s=a.optJSONObject(i)?:continue;val e=s.optJSONObject("employee_snapshot")?:JSONObject();box.addView(listCard("${s.optString("mnv")} • ${e.optString("full_name")}","${s.optString("state")} • ${s.optString("shift")} • ${workText(s.optString("work_choice"))}\nPDA ${dash(s.optString("pda_serial"))} • Pick ${dash(s.optString("user_pick"))} • Pack ${dash(s.optString("pack_table"))}"));box.addView(gap(6))}}}}
        fun loadLabor(){box.removeAllViews();if(!isAdmin()){box.addView(info("Công nhật chỉ hiển thị cho ADMIN/SUPERADMIN."));return};api.call("list_labor"){r->runOnUiThread{box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Lỗi"));return@runOnUiThread};val a=r.json?.optJSONArray("items")?:JSONArray();if(a.length()==0)box.addView(info("Chưa có công nhật hôm nay."));for(i in 0 until a.length()){val l=a.optJSONObject(i)?:continue;val e=l.optJSONObject("employee_snapshot")?:JSONObject();box.addView(listCard("${l.optString("mnv")} • ${e.optString("full_name")}","${l.optString("state")} • ${l.optString("labor_type")}\n${formatIso(l.optString("start_at"))} → ${formatIso(l.optString("end_at"))}"));box.addView(gap(6))}}}}
        fun searchStaff(){val query=q.text.toString().trim();box.removeAllViews();if(query.length<2){box.addView(info("Nhập ít nhất 2 ký tự để tìm nhân sự."));return};val a=MasterDataCache.searchStaff(this,query);for(i in 0 until a.length()){val e=a.optJSONObject(i)?:continue;box.addView(listCard("${e.optString("mnv")} • ${e.optString("full_name")}","${e.optString("main_position")} • ${e.optString("supplier")} • ${e.optString("department")}"));box.addView(gap(6))};if(a.length()==0)box.addView(info("Không tìm thấy nhân sự phù hợp."))}
        sessions.setOnClickListener{loadSessions()};labor.setOnClickListener{loadLabor()};staff.setOnClickListener{searchStaff()};q.setOnEditorActionListener{_,_,_->searchStaff();true};loadSessions();attach(root,body)
    }

    private fun reportScreen(){
        screenState = "REPORT"
        val root=baseRoot("BÁO CÁO");val body=column(bg).apply{setPadding(dp(3),dp(6),dp(3),dp(42))}
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày"));body.addView(labelled("Phạm vi báo cáo",period));body.addView(gap(5))
        val box=column(bg);body.addView(box,matchWrap());box.addView(txt("Đang tải...",10.5f,muted,false))
        api.call("report_daily"){r->runOnUiThread{
            box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Không tải được báo cáo"));return@runOnUiThread}
            val rootJson=r.json?:JSONObject()
            fun render(){
                box.removeAllViews();val key=when(period.selectedItemPosition){0->"ca1_hc";1->"ca2";else->"all"};val p=rootJson.optJSONObject("reports")?.optJSONObject(key)?:JSONObject()
                box.addView(reportGrid("",p.optJSONObject("manpower"),"Vị trí","position"));box.addView(gap(4));box.addView(reportGrid("",p.optJSONObject("tenure"),"Thâm niên","label"))
                val support=p.optJSONObject("support");if(isAdmin() && (support?.optInt("total")?:0)>0){box.addView(gap(4));box.addView(supportGrid(support))}
            }
            period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){render()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};render()
        }}
        attach(root,body)
    }

    private fun reportGrid(title:String,data:JSONObject?,firstTitle:String,rowKey:String):View{
        val wrap=column(surface).apply{setPadding(dp(1),dp(2),dp(1),dp(2));setBackgroundColor(surface)};if(title.isNotBlank())wrap.addView(txt(title,11f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(3))})
        if(data==null){wrap.addView(txt("Chưa có dữ liệu",10f,muted,false));return wrap}
        val cols=jsonStrings(data.optJSONArray("columns"));val rows=data.optJSONArray("rows")?:JSONArray();val table=TableLayout(this).apply{isStretchAllColumns=true;isShrinkAllColumns=true}
        fun cell(v:String,bold:Boolean=false,header:Boolean=false)=TextView(this).apply{text=v;textSize=if(header)8.2f else 8.5f;setTextColor(if(header)navy else ink);typeface=if(bold)Typeface.DEFAULT_BOLD else Typeface.DEFAULT;gravity=Gravity.CENTER;setPadding(dp(1),dp(3),dp(1),dp(3));maxLines=3;background=GradientDrawable().apply{setColor(if(header)Color.rgb(232,241,246) else Color.WHITE)}}
        val hr=TableRow(this);hr.addView(cell(firstTitle,true,true));cols.forEach{hr.addView(cell(it,true,true))};hr.addView(cell("Tổng",true,true));table.addView(hr)
        for(i in 0 until rows.length()){val row=rows.optJSONObject(i)?:continue;val tr=TableRow(this);tr.addView(cell(row.optString(rowKey),true));val counts=row.optJSONObject("counts")?:JSONObject();cols.forEach{c->val n=counts.optInt(c);tr.addView(cell(if(n==0)"" else n.toString()))};val total=row.optInt("total");tr.addView(cell(if(total==0)"" else total.toString(),true));table.addView(tr)}
        val totals=data.optJSONObject("totals");if(totals!=null){val tr=TableRow(this);tr.addView(cell("Tổng",true,true));cols.forEach{c->val n=totals.optInt(c);tr.addView(cell(if(n==0)"" else n.toString(),true,true))};val total=data.optInt("total");tr.addView(cell(if(total==0)"" else total.toString(),true,true));table.addView(tr)}
        wrap.addView(table,matchWrap());return wrap
    }

    private fun supportGrid(data:JSONObject?):View{
        val wrap=column(surface).apply{setPadding(dp(1),dp(2),dp(1),dp(2));setBackgroundColor(surface)};wrap.addView(txt("NHÂN SỰ ĐI HỖ TRỢ",11f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(3))})
        val table=TableLayout(this).apply{isStretchAllColumns=true;isShrinkAllColumns=true}
        fun cell(v:String,bold:Boolean=false,header:Boolean=false)=TextView(this).apply{text=v;textSize=8.8f;setTextColor(if(header)navy else ink);typeface=if(bold)Typeface.DEFAULT_BOLD else Typeface.DEFAULT;gravity=Gravity.CENTER;setPadding(dp(1),dp(3),dp(1),dp(3));maxLines=3;background=GradientDrawable().apply{setColor(if(header)Color.rgb(232,241,246) else Color.WHITE)}}
        val h=TableRow(this);h.addView(cell("Thông tin công nhật",true,true));h.addView(cell("Số lượng",true,true));table.addView(h)
        val rows=data?.optJSONArray("rows")?:JSONArray();for(i in 0 until rows.length()){val x=rows.optJSONObject(i)?:continue;val tr=TableRow(this);tr.addView(cell(x.optString("labor_type"),true));val q=x.optInt("quantity");tr.addView(cell(if(q==0)"" else q.toString()));table.addView(tr)}
        wrap.addView(table,matchWrap());return wrap
    }

    private fun historyScreen(){
        module="HISTORY"
        screenState="HISTORY"
        val root=baseRoot("LỊCH SỬ")
        val body=body()
        val a=AppHistory.items(this)
        if(a.length()==0) body.addView(info("Chưa có lịch sử."))
        for(i in 0 until a.length()){
            val x=a.optJSONObject(i)?:continue
            val ok=x.optBoolean("synced")
            val at=java.text.SimpleDateFormat("dd/MM HH:mm:ss",java.util.Locale.US).format(java.util.Date(x.optLong("at")))
            val detail=x.optString("detail").trim()
            val sub="$at • ${if(ok)"Đã đồng bộ" else "Chưa đồng bộ"}${if(detail.isBlank())"" else " • $detail"}"
            body.addView(listCard(AppHistory.label(x.optString("action")),sub))
            body.addView(gap(6))
        }
        attach(root,body)
    }

    private fun syncScreen(){
        module="SYNC"
        screenState="SYNC"
        val root=baseRoot("ĐỒNG BỘ")
        val body=body()
        val state=info("Đang kiểm tra kết nối...")
        val detailsBox=column(bg)
        body.addView(state,matchWrap())
        body.addView(gap(8))
        body.addView(detailsBox,matchWrap())
        detailsBox.addView(details(listOf(
            "Mạng" to "Đang kiểm tra",
            "Dữ liệu chờ gửi" to LocalLogManager.pendingCount(this).toString(),
            "Phiên bản" to BuildConfig.VERSION_NAME,
            "Service" to "Chưa cấu hình"
        )))
        api.call("sync_status"){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            detailsBox.removeAllViews()
            if(r.ok){
                state.text="✓ Kết nối tốt"
                detailsBox.addView(details(listOf(
                    "Mạng" to "Tốt",
                    "Đồng bộ" to "Sẵn sàng",
                    "Dữ liệu chờ gửi" to LocalLogManager.pendingCount(this).toString(),
                    "Phiên bản" to BuildConfig.VERSION_NAME,
                    "Service" to "Chưa cấu hình"
                )))
            }else{
                state.text="! Mất kết nối"
                detailsBox.addView(info("Dữ liệu sẽ tự đồng bộ khi kết nối trở lại."))
            }
        }}
        attach(root,body)
    }

    private fun settingsScreen(){
        module="SETTINGS"
        screenState="SETTINGS"
        val root=baseRoot("CÀI ĐẶT")
        val body=body()
        body.addView(section("Tài khoản"))
        body.addView(listCard("$name • ${roleText(role)}","$login${if(position.isBlank())"" else "  •  $position"}\nMail: ${email.ifBlank{"Chưa cấu hình"}}"))
        body.addView(gap(7))
        val accountButtons=row(bg)
        val passBtn=primary("ĐỔI MẬT KHẨU",navy){changePasswordDialog()}.apply{textSize=9.6f;setSingleLine(true)}
        val mailBtn=primary("ĐỔI MAIL",teal){changeEmailDialog()}.apply{textSize=9.6f;setSingleLine(true)}
        accountButtons.addView(passBtn,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(3)})
        accountButtons.addView(mailBtn,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(3)})
        body.addView(accountButtons,matchWrap())
        if(isAdmin()){
            body.addView(gap(7))
            body.addView(primary("QUẢN LÝ TÀI KHOẢN",blue){accountManager()},matchWrap())
        }
        body.addView(section("Giao diện"))
        body.addView(themePicker(),matchWrap())
        body.addView(section("Cập nhật"))
        body.addView(info("${BuildConfig.CHANNEL} • ${BuildConfig.VERSION_NAME}\nTự động kiểm tra cập nhật: Bật"))
        body.addView(section("Nhật ký"))
        body.addView(primary("GỬI BÁO LỖI",teal){sendDiagnostic()},matchWrap())
        body.addView(section("Thiết bị"))
        body.addView(info("Android ${Build.VERSION.RELEASE} • ${Build.MANUFACTURER} ${Build.MODEL}"))
        body.addView(gap(14))
        body.addView(primary("ĐĂNG XUẤT",red){api.call("logout"){runOnUiThread{api.clearSession();finishAffinity()}}},matchWrap())
        attach(root,body)
    }
    private fun themePicker()=row(surface).apply{
        gravity=Gravity.CENTER
        setPadding(dp(5),dp(8),dp(5),dp(8))
        background=outlineBg(surface,14)
        val selected=ThemeManager.selectedIndex(this@OperationsActivity)
        ThemeManager.swatches().forEachIndexed{i,c->
            val holder=FrameLayout(this@OperationsActivity).apply{
                background=if(i==selected)GradientDrawable().apply{setColor(Color.TRANSPARENT);cornerRadius=dp(10).toFloat();setStroke(dp(2),navy)}else null
                setPadding(dp(3),dp(3),dp(3),dp(3))
                addView(TextView(this@OperationsActivity).apply{
                    text=if(i==selected)"✓" else ""
                    textSize=15f
                    setTextColor(Color.WHITE)
                    typeface=Typeface.DEFAULT_BOLD
                    gravity=Gravity.CENTER
                    background=round(c,8)
                },FrameLayout.LayoutParams(-1,-1))
                setOnClickListener{ThemeManager.select(this@OperationsActivity,i);window.statusBarColor=ThemeManager.primaryDark(this@OperationsActivity);settingsScreen()}
            }
            addView(holder,LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(2);marginEnd=dp(2)})
        }
    }
    private fun changePasswordDialog(){val box=column(surface).apply{setPadding(dp(8),0,dp(8),0)};val current=input("Mật khẩu hiện tại",true);val next=input("Mật khẩu mới (tối thiểu 8 ký tự)",true);val confirm=input("Nhập lại mật khẩu mới",true);box.addView(current);box.addView(gap(7));box.addView(next);box.addView(gap(7));box.addView(confirm);AlertDialog.Builder(this).setTitle("Đổi mật khẩu").setView(box).setNegativeButton("Hủy",null).setPositiveButton("CẬP NHẬT"){_,_->if(next.text.toString()!=confirm.text.toString()){showError("Mật khẩu xác nhận không khớp.");return@setPositiveButton};api.call("change_password",JSONObject().put("current_password",current.text.toString()).put("new_password",next.text.toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Đổi mật khẩu thất bại")else TopNotice.show(this,"Đã đổi mật khẩu.",TopNotice.Kind.SUCCESS)}}}.show()}
    private fun changeEmailDialog(){val value=input("Địa chỉ mail nhận reset mật khẩu",false).apply{setText(email)};AlertDialog.Builder(this).setTitle("Đổi mail").setView(value).setNegativeButton("Hủy",null).setPositiveButton("CẬP NHẬT"){_,_->val next=value.text.toString().trim();api.call("change_email",JSONObject().put("email",next)){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không đổi được mail")else{email=r.json?.optJSONObject("account")?.optString("email",next)?:next;TopNotice.show(this,"Đã cập nhật mail nhận reset.",TopNotice.Kind.SUCCESS);settingsScreen()}}}}.show()}
    private fun sendDiagnostic(){AlertDialog.Builder(this).setTitle("Gửi log thủ công?").setMessage("Gửi gói chẩn đoán hiện tại lên hệ thống?").setNegativeButton("NO",null).setPositiveButton("YES"){_,_->LocalLogManager.sendManualReport(this,api,module,connectionSummary()){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không gửi được báo lỗi")else TopNotice.show(this,"Đã gửi báo lỗi thành công.",TopNotice.Kind.SUCCESS)}}}.show()}

    private fun accountManager(){
        screenState = "ACCOUNT_MANAGER"
        val root=baseRoot("QUẢN LÝ TÀI KHOẢN");val body=body();body.addView(primary("TẠO TÀI KHOẢN",green){accountCreateDialog()},matchWrap());body.addView(gap(10));val box=column(bg);body.addView(box,matchWrap());api.call("account_list"){r->runOnUiThread{box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Lỗi"));return@runOnUiThread};val a=r.json?.optJSONArray("items")?:JSONArray();for(i in 0 until a.length()){val x=a.optJSONObject(i)?:continue;val card=column(surface).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,8);addView(txt("${x.optString("login_id")} • ${x.optString("display_name")}",13f,navy,true));addView(txt("${x.optString("role")} • ${x.optString("status")} • ${x.optString("email")}",10f,muted,false));if(x.optString("login_id")!=login){addView(gap(6));val newStatus=if(x.optString("status")=="ACTIVE")"DISABLED" else "ACTIVE";addView(smallButton(if(newStatus=="DISABLED")"VÔ HIỆU HÓA" else "KÍCH HOẠT",if(newStatus=="DISABLED")red else green).apply{setOnClickListener{api.call("account_status",JSONObject().put("login_id",x.optString("login_id")).put("status",newStatus)){rr->runOnUiThread{if(!rr.ok)showError(rr.error?:"Lỗi")else accountManager()}}}})}};box.addView(card,matchWrap());box.addView(gap(7))}}};attach(root,body)
    }

    private fun accountCreateDialog(){
        val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))}
        val loginInput=input("Tài khoản",false)
        val display=input("Tên hiển thị",false)
        val allowedPositions=if(isSuper())arrayOf("USER","ADMIN")else arrayOf("USER")
        val positionSp=spinner(allowedPositions)
        val mail=input("Mail nhận reset",false).apply{setText("tam95.supra@gmail.com")}
        val pass=input("Mật khẩu ban đầu (>=8 ký tự)",true)
        fun addField(label:String,view:View){box.addView(txt(label,10.2f,ink,true));box.addView(gap(4));box.addView(view,matchWrap());box.addView(gap(8))}
        addField("Tài khoản",loginInput);addField("Tên hiển thị",display);addField("Vị trí",positionSp);addField("Mail nhận reset",mail);addField("Mật khẩu ban đầu",pass)
        AlertDialog.Builder(this).setTitle("Tạo tài khoản").setView(ScrollView(this).apply{addView(box)}).setNegativeButton("Hủy",null).setPositiveButton("TẠO"){_,_->
            val fixedRole=positionSp.selectedItem.toString().uppercase()
            api.call("account_upsert",JSONObject().put("login_id",loginInput.text.toString().trim()).put("display_name",display.text.toString().trim()).put("position",fixedRole.lowercase()).put("email",mail.text.toString().trim()).put("role",fixedRole).put("password",pass.text.toString())){r->runOnUiThread{if(!r.ok)showError(r.error?:"Không tạo được tài khoản")else accountManager()}}
        }.show()
    }

    private fun refreshMasterCache(){cacheApi.call("master_snapshot"){r->if(r.ok&&r.json!=null)MasterDataCache.save(applicationContext,r.json)}}
    private fun navigateBack(){
        when(screenState){
            "LABOR_CONTEXT"->laborHome()
            "RESOURCE_EDITOR"->resourceHome()
            "ACCOUNT_MANAGER"->settingsScreen()
            "EMPLOYEE","EMPLOYEE_LOADING"->employeeScan()
            "SCAN","LABOR_HOME","RESOURCE_HOME","REPORT","LISTS"->businessHome()
            else->if(module!="BUSINESS"){module="BUSINESS";businessHome()}else finish()
        }
    }
    private fun simpleMessage(title:String,message:String){val root=baseRoot(title);val body=body();body.addView(info("ⓘ $message"));attach(root,body)}
    private fun baseRoot(title:String)=column(bg).apply{addView(appBar(title))}
    private fun body()=column(bg).apply{setPadding(dp(16),dp(15),dp(16),dp(92))}
    private fun attach(root:LinearLayout,body:LinearLayout){
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f))
        setScreen(root)
    }
    private fun setScreen(content:View){
        val frame=contentHost
        if(frame==null){setContentView(host(content));return}
        frame.removeAllViews()
        frame.addView(content,FrameLayout.LayoutParams(-1,-1))
        refreshBottomNav()
    }
    private fun isRootScreen()=screenState=="BUSINESS"||screenState=="STAFF"||screenState=="HISTORY"||screenState=="SYNC"||screenState=="SETTINGS"
    private fun connectionSummary():String{
        val network=when(lastConnected){true->"Tốt";false->"Mất kết nối";null->"Chưa kiểm tra"}
        val sync=when(lastConnected){true->"Sẵn sàng";false->"Đang chờ";null->"Chưa kiểm tra"}
        return "Mạng: $network | Đồng bộ: $sync | Service: Chưa cấu hình"
    }
    private fun refreshHeaderConnection(){
        networkStatusText?.text=when(lastConnected){true->"Tốt";false->"Mất";null->"—"}
        syncStatusText?.text=when(lastConnected){true->"Sẵn sàng";false->"Chờ";null->"—"}
        serviceStatusText?.text="Chưa dùng"
    }
    private fun headerStatusChip(iconRes:Int,label:String,valueView:TextView)=row(Color.TRANSPARENT).apply{
        gravity=Gravity.CENTER_VERTICAL
        setPadding(dp(8),dp(7),dp(8),dp(7))
        background=round(Color.argb(32,255,255,255),13)
        addView(ImageView(this@OperationsActivity).apply{setImageResource(iconRes);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(2),dp(2),dp(2),dp(2))},size(dp(24),dp(24)))
        addView(column(Color.TRANSPARENT).apply{
            addView(txt(label,7.8f,Color.argb(210,255,255,255),false).apply{maxLines=1})
            addView(valueView.apply{maxLines=1})
        },LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(5)})
    }
    private fun appBar(title:String)=column(Color.TRANSPARENT).apply{
        setPadding(dp(16),dp(12),dp(16),dp(13))
        background=gradient(navy,accent,0)
        val identity=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL}
        if(!isRootScreen()){
            identity.addView(ImageView(this@OperationsActivity).apply{setImageResource(R.drawable.ic_pp_back);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(7),dp(7),dp(7),dp(7));setOnClickListener{navigateBack()}},size(dp(36),dp(36)))
        }
        identity.addView(column(Color.TRANSPARENT).apply{
            addView(txt(name.ifBlank{login},16.2f,Color.WHITE,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
            addView(txt(position.ifBlank{roleText(role)},10.5f,Color.argb(225,255,255,255),false).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
            addView(txt(login,10f,Color.argb(210,255,255,255),false).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
        },LinearLayout.LayoutParams(0,-2,1f).apply{if(!isRootScreen())marginStart=dp(3)})
        addView(identity,matchWrap())
        addView(gap(11))
        val statuses=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER}
        val net=txt("—",9.2f,Color.WHITE,true);networkStatusText=net
        val syn=txt("—",9.2f,Color.WHITE,true);syncStatusText=syn
        val svc=txt("Chưa dùng",9.2f,Color.WHITE,true);serviceStatusText=svc
        statuses.addView(headerStatusChip(R.drawable.ic_pp_network,"Mạng",net),LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(4)})
        statuses.addView(headerStatusChip(R.drawable.ic_pp_sync,"Đồng bộ",syn),LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(2);marginEnd=dp(2)})
        statuses.addView(headerStatusChip(R.drawable.ic_pp_service,"Service",svc),LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(4)})
        addView(statuses,matchWrap())
        refreshHeaderConnection()
        if(!isRootScreen() && title.isNotBlank()){
            addView(gap(10))
            addView(txt(title,15f,Color.WHITE,true).apply{setPadding(dp(1),0,0,0);maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
        }
    }
    private fun activeTab()=when(module){"STAFF"->"STAFF";"HISTORY"->"HISTORY";"SYNC"->"SYNC";"SETTINGS"->"SETTINGS";else->"BUSINESS"}
    private fun bottomNav(): LinearLayout = row(surface).apply {
        gravity=Gravity.CENTER
        setPadding(dp(6),dp(5),dp(6),dp(5))
        background=outlineBg(surface,16)
        elevation=dp(8).toFloat()
        navRefs.clear()
        val items=listOf(
            Triple(R.drawable.ic_pp_business,"Nghiệp vụ","BUSINESS"),
            Triple(R.drawable.ic_pp_staff,"Nhân sự","STAFF"),
            Triple(R.drawable.ic_pp_history,"Lịch sử","HISTORY"),
            Triple(R.drawable.ic_pp_sync,"Đồng bộ","SYNC"),
            Triple(R.drawable.ic_pp_settings,"Cài đặt","SETTINGS")
        )
        items.forEach{item->
            val iconView=ImageView(this@OperationsActivity).apply{setImageResource(item.first);setPadding(dp(6),dp(4),dp(6),dp(2))}
            val labelView=txt(item.second,8.2f,muted,item.third==activeTab()).apply{gravity=Gravity.CENTER;maxLines=1}
            val cell=column(Color.TRANSPARENT).apply{
                gravity=Gravity.CENTER
                setPadding(dp(2),dp(2),dp(2),dp(2))
                addView(iconView,size(dp(32),dp(28)))
                addView(labelView)
                setOnClickListener{navigateTab(item.third)}
            }
            navRefs[item.third]=NavRefs(cell,iconView,labelView)
            addView(cell,LinearLayout.LayoutParams(0,-1,1f).apply{marginStart=dp(1);marginEnd=dp(1)})
        }
        post{refreshBottomNav()}
    }

    private fun refreshBottomNav(){
        val active=activeTab()
        navRefs.forEach{(key,ref)->
            val chosen=key==active
            ref.cell.background=if(chosen)round(ThemeManager.soft(this@OperationsActivity),10)else null
            ref.icon.imageTintList=ColorStateList.valueOf(if(chosen)teal else muted)
            ref.label.setTextColor(if(chosen)teal else muted)
            ref.label.typeface=if(chosen)Typeface.DEFAULT_BOLD else Typeface.DEFAULT
        }
    }

    private fun navigateTab(target:String){
        if(target==activeTab())return
        module=target
        initialMnv=""
        liveEmployeeMnv=""
        when(target){
            "BUSINESS"->businessHome()
            "STAFF"->staffScreen()
            "HISTORY"->historyScreen()
            "SYNC"->syncScreen()
            "SETTINGS"->settingsScreen()
        }
    }

    private fun sessionExpired(){
        api.clearSession()
        AlertDialog.Builder(this).setTitle("Phiên đăng nhập đã thay đổi").setMessage("Vui lòng đăng nhập lại để tiếp tục.").setCancelable(false).setPositiveButton("ĐĂNG NHẬP"){_,_->finishAffinity()}.show()
    }

    private fun handleAuth(r:BetaApiClient.Result):Boolean{if(r.code==401){api.clearSession();AlertDialog.Builder(this).setTitle("Phiên đăng nhập đã được thay thế").setMessage("Tài khoản đã đăng nhập ở thiết bị khác hoặc quyền tài khoản đã thay đổi.").setCancelable(false).setPositiveButton("OK"){_,_->finishAffinity()}.show();return true};return false}
    private fun showError(raw:String){val msg=when{raw.contains("PP_RESOURCE_CONFLICT")->"Tài nguyên vừa được người khác nhận. Tài nguyên cũ vẫn được giữ.";raw.contains("PP_USER_PICK_USED_TODAY")->"User Pick này đã được dùng trong ngày.";raw.contains("PP_USER_PACK_USED_TODAY")->"User Pack này đã được dùng trong ngày.";raw.contains("PP_LABOR_ALREADY_ACTIVE")->"MNV đang có công nhật chưa hoàn thành.";raw.contains("PP_LABOR_NOT_ACTIVE")->"MNV không có công nhật đang hoạt động.";raw.contains("CURRENT_PASSWORD_INVALID")->"Mật khẩu hiện tại không đúng.";raw.contains("PASSWORD_POLICY")->"Mật khẩu mới phải có ít nhất 8 ký tự.";raw.contains("EMAIL_INVALID")->"Địa chỉ mail không hợp lệ.";raw.contains("EMPLOYEE_NOT_FOUND")->"Không tìm thấy nhân sự.";raw.contains("STAFF_ACTIVE_SESSION")->"Nhân sự đang có phiên ACTIVE, chưa thể xóa.";raw.contains("FORBIDDEN")->"Tài khoản không có quyền thực hiện thao tác này.";else->raw};TopNotice.show(this,msg,TopNotice.Kind.ERROR)}

    private fun iconBubble(res:Int,color:Int)=FrameLayout(this).apply{
        background=round(ThemeManager.soft(this@OperationsActivity),14)
        addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(color);setPadding(dp(9),dp(9),dp(9),dp(9))},FrameLayout.LayoutParams(-1,-1))
    }
    private fun businessIconBubble(res:Int):FrameLayout{
        val colors=when(res){
            R.drawable.ic_pp_scan->intArrayOf(teal,accent)
            R.drawable.ic_pp_task->intArrayOf(Color.rgb(37,99,235),Color.rgb(14,165,233))
            R.drawable.ic_pp_report->intArrayOf(Color.rgb(124,58,237),Color.rgb(168,85,247))
            else->intArrayOf(Color.rgb(6,182,212),Color.rgb(14,165,233))
        }
        return FrameLayout(this).apply{
            background=GradientDrawable(GradientDrawable.Orientation.TL_BR,colors).apply{shape=GradientDrawable.OVAL}
            elevation=dp(5).toFloat()
            addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(13),dp(13),dp(13),dp(13))},FrameLayout.LayoutParams(-1,-1))
        }
    }
    private fun businessCard(iconRes:Int,title:String,sub:String,click:()->Unit)=column(surface).apply{
        gravity=Gravity.CENTER_HORIZONTAL
        setPadding(dp(14),dp(16),dp(14),dp(14))
        background=outlineBg(surface,20)
        elevation=dp(6).toFloat()
        addView(businessIconBubble(iconRes),size(dp(62),dp(62)))
        addView(gap(11))
        addView(txt(title,14.2f,ink,true).apply{gravity=Gravity.CENTER;maxLines=2})
        addView(gap(6))
        addView(View(this@OperationsActivity).apply{background=round(teal,2)},size(dp(28),dp(3)))
        addView(gap(7))
        addView(txt(sub,10.2f,muted,false).apply{gravity=Gravity.CENTER;maxLines=1})
        setOnClickListener{click()}
    }
    private fun businessRow(a:View,b:View)=row(bg).apply{
        addView(a,LinearLayout.LayoutParams(0,dp(160),1f).apply{marginEnd=dp(6)})
        addView(b,LinearLayout.LayoutParams(0,dp(160),1f).apply{marginStart=dp(6)})
    }
    private fun iconActionButton(res:Int,color:Int,desc:String,click:()->Unit)=FrameLayout(this).apply{
        contentDescription=desc
        background=round(ThemeManager.soft(this@OperationsActivity),12)
        setOnClickListener{click()}
        addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(color);setPadding(dp(9),dp(9),dp(9),dp(9))},FrameLayout.LayoutParams(-1,-1))
    }

    private fun employeeCard(e:JSONObject)=column(surface).apply{setPadding(dp(14),dp(13),dp(14),dp(13));background=outlineBg(surface,14);elevation=dp(2).toFloat();addView(txt("${e.optString("mnv")} • ${e.optString("full_name")}",15f,navy,true));addView(txt("${dash(e.optString("main_position"))} • ${dash(e.optString("supplier"))}",10.5f,ink,false));addView(txt("${dash(e.optString("department"))} • Site ${dash(e.optString("site"))} • Kho ${dash(e.optString("warehouse"))}",10f,muted,false))}
    private fun listCard(title:String,sub:String)=column(surface).apply{setPadding(dp(13),dp(11),dp(13),dp(11));background=outlineBg(surface,13);addView(txt(title,12.5f,ink,true));addView(gap(2));addView(txt(sub,10f,muted,false))}
    private fun metric(title:String,value:String,color:Int)=column(surface).apply{setPadding(dp(14),dp(12),dp(14),dp(12));background=outlineBg(surface,14);addView(txt(title,11f,color,true));addView(gap(3));addView(txt(value,13f,ink,true))}
    private fun jsonMapCard(title:String,j:JSONObject?)=column(surface).apply{setPadding(dp(14),dp(11),dp(14),dp(11));background=outlineBg(surface,14);addView(txt(title,11f,navy,true));if(j==null||j.length()==0)addView(txt("Chưa có dữ liệu",10f,muted,false))else{val keys=j.keys();while(keys.hasNext()){val k=keys.next();addView(txt("$k: ${j.optInt(k)}",10.5f,ink,false))}}}
    private fun details(items:List<Pair<String,String>>)=column(surface).apply{setPadding(dp(14),dp(10),dp(14),dp(10));background=outlineBg(surface,14);items.forEach{(k,v)->addView(row(surface).apply{addView(txt(k,10.3f,muted,false),LinearLayout.LayoutParams(0,-2,.45f));addView(txt(if(v.isBlank())"—" else v,10.5f,ink,true).apply{gravity=Gravity.END},LinearLayout.LayoutParams(0,-2,.55f));setPadding(0,dp(3),0,dp(3))})}}
    private fun section(v:String)=row(bg).apply{
        gravity=Gravity.CENTER_VERTICAL
        setPadding(0,dp(14),0,dp(5))
        addView(ImageView(this@OperationsActivity).apply{setImageResource(sectionIconRes(v));imageTintList=ColorStateList.valueOf(teal)},size(dp(23),dp(23)))
        addView(txt(v,13.5f,navy,true),LinearLayout.LayoutParams(-2,-2).apply{marginStart=dp(6)})
    }
    private fun sectionIconRes(v:String)=when{
        v.contains("Tài khoản",true)->R.drawable.ic_pp_account
        v.contains("Giao diện",true)->R.drawable.ic_pp_palette
        v.contains("Đồng bộ",true)->R.drawable.ic_pp_sync
        v.contains("Cập nhật",true)->R.drawable.ic_pp_update
        v.contains("Nhật ký",true)->R.drawable.ic_pp_log
        v.contains("Thiết bị",true)->R.drawable.ic_pp_device
        else->R.drawable.ic_pp_task
    }
    private fun status(v:String,fg:Int,c:Int)=txt(v,11.3f,fg,true).apply{gravity=Gravity.CENTER;setPadding(dp(10),dp(10),dp(10),dp(10));background=round(c,12)}
    private fun info(v:String)=txt(v,10.3f,muted,false).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(ThemeManager.soft(this@OperationsActivity),12)}
    private fun mnvInput(h:String)=input(h,false).apply{setSingleLine(true);inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");imeOptions=EditorInfo.IME_ACTION_DONE}
    private fun bindScannerEnter(v:EditText,submit:()->Unit){v.setOnEditorActionListener{_,id,_->if(id==EditorInfo.IME_ACTION_DONE||id==EditorInfo.IME_ACTION_GO||id==EditorInfo.IME_ACTION_SEARCH){submit();true}else false};v.setOnKeyListener{_,key,event->if(key==KeyEvent.KEYCODE_ENTER&&event.action==KeyEvent.ACTION_UP){submit();true}else false}}
    private fun pdaInput(pdas:JSONArray,currentSerial:String=""):AutoCompleteTextView{val labels=mutableListOf<String>();var currentLast5="";for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(serial.isBlank()||last5.isBlank())continue;labels.add("$last5 • $serial");if(serial==currentSerial)currentLast5=last5};return AutoCompleteTextView(this).apply{hint="Nhập 5 số cuối seri PDA";threshold=1;textSize=14f;setTextColor(ink);setHintTextColor(Color.rgb(153,163,176));inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");setPadding(dp(13),dp(10),dp(13),dp(10));minHeight=dp(48);background=outline();setAdapter(ArrayAdapter(this@OperationsActivity,android.R.layout.simple_dropdown_item_1line,labels));setOnItemClickListener{parent,_,pos,_->setText(parent.getItemAtPosition(pos).toString().substringBefore(" • "),false)};if(currentLast5.isNotBlank())setText(currentLast5,false)}}
    private fun resolvePda(pdas:JSONArray,rawValue:String):String?{val raw=rawValue.trim().substringBefore(" • ");if(raw.length!=5||!raw.all{it.isDigit()})return null;val hits=mutableListOf<String>();for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(last5==raw&&serial.isNotBlank())hits.add(serial)};return hits.singleOrNull()}
    private fun input(h:String,password:Boolean)=EditText(this).apply{hint=h;textSize=13.5f;setTextColor(ink);setHintTextColor(Color.rgb(148,163,184));inputType=if(password)InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT;setPadding(dp(14),dp(11),dp(14),dp(11));minHeight=dp(50);background=outline();elevation=dp(1).toFloat()}
    private fun labelled(l:String,v:View)=column(bg).apply{addView(txt(l,10.2f,muted,true));addView(gap(5));addView(v,matchWrap())}
    private fun spinner(items:Array<String>)=Spinner(this).apply{adapter=ArrayAdapter(this@OperationsActivity,android.R.layout.simple_spinner_dropdown_item,items);setPadding(dp(11),dp(5),dp(11),dp(5));minimumHeight=dp(50);background=outline();elevation=dp(1).toFloat()}
    private fun primary(t:String,c:Int,click:()->Unit)=Button(this).apply{text=t;textSize=12f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;minHeight=dp(50);background=gradient(c,darken(c),14);elevation=dp(3).toFloat();setOnClickListener{click()}}
    private fun smallButton(t:String,c:Int)=Button(this).apply{text=t;textSize=9.5f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;background=round(c,10);setPadding(dp(4),0,dp(4),0)}
    private fun host(content:View):View{
        val root=EdgeSwipeBackLayout(this){navigateBack()}.apply{setBackgroundColor(bg)}
        val contentFrame=FrameLayout(this).apply{addView(content,FrameLayout.LayoutParams(-1,-1))}
        val navFrame=FrameLayout(this).apply{
            setPadding(dp(10),0,dp(10),0)
            addView(bottomNav(),FrameLayout.LayoutParams(-1,-1))
        }
        contentHost=contentFrame;navHost=navFrame
        root.addView(contentFrame,FrameLayout.LayoutParams(-1,-1).apply{bottomMargin=dp(94)})
        root.addView(navFrame,FrameLayout.LayoutParams(-1,dp(68),Gravity.BOTTOM).apply{bottomMargin=dp(21)})
        root.addView(txt(FOOTER,7.7f,Color.rgb(113,122,136),false).apply{gravity=Gravity.CENTER;maxLines=1},FrameLayout.LayoutParams(-1,dp(20),Gravity.BOTTOM))
        root.setOnApplyWindowInsetsListener{v,i->val top:Int;val bottom:Int;if(Build.VERSION.SDK_INT>=30){top=i.getInsets(WindowInsets.Type.statusBars()).top;bottom=i.getInsets(WindowInsets.Type.navigationBars()).bottom}else{@Suppress("DEPRECATION")val tt=i.systemWindowInsetTop;@Suppress("DEPRECATION")val bb=i.systemWindowInsetBottom;top=tt;bottom=bb};v.setPadding(0,top+dp(4),0,bottom+dp(2));i}
        root.requestApplyInsets();return root
    }
    private fun jsonStrings(a:JSONArray?):MutableList<String>{val out=mutableListOf<String>();if(a!=null)for(i in 0 until a.length()){val v=a.optString(i);if(v.isNotBlank())out.add(v)};return out}
    private fun catalogValues(key:String,fallback:List<String> = emptyList()):MutableList<String>{
        val fields=MasterDataCache.snapshot(this)?.optJSONObject("catalog_fields")
        var arr=fields?.optJSONArray(key)
        if(arr==null && fields!=null){val keys=fields.keys();while(keys.hasNext()){val k=keys.next();if(foldLocal(k)==foldLocal(key)){arr=fields.optJSONArray(k);break}}}
        val out=jsonStrings(arr)
        if(out.isEmpty())fallback.filter{it.isNotBlank()}.forEach{if(!out.contains(it))out.add(it)}
        return out
    }
    private fun catalogSpinner(key:String,current:String="",allowBlank:Boolean=false):Spinner{
        val values=catalogValues(key)
        if(allowBlank)values.add(0,"—")
        if(current.isNotBlank()&&!values.contains(current))values.add(current)
        if(values.isEmpty())values.add("—")
        return spinner(values.toTypedArray()).also{sp->selectByValue(sp,values,if(current.isBlank()&&allowBlank)"—" else current)}
    }
    private fun catalogSelection(sp:Spinner)=sp.selectedItem?.toString().orEmpty().let{if(it=="—")"" else it}
    private fun selectByValue(sp:Spinner,values:List<String>,target:String){val i=values.indexOf(target);if(i>=0)sp.setSelection(i)}
    private fun formatIso(v:String):String{if(v.isBlank()||v=="null")return "—";return try{Instant.parse(v).atZone(ZoneId.of("Asia/Bangkok")).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss"))}catch(_:Throwable){v}}
    private fun roleText(v:String)=when(v){"SUPERADMIN"->"Superadmin";"ADMIN"->"Admin";"USER"->"Điều phối";else->v}
    private fun workText(v:String)=when(v){"PICK"->"Pick";"PACK"->"Pack";else->"Không"}
    private fun foldLocal(v:String)=java.text.Normalizer.normalize(v,java.text.Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"),"").uppercase().trim()
    private fun dash(v:String)=v.takeIf{it.isNotBlank()&&it!="null"}?:"—"
    private fun txt(v:String,s:Float,c:Int,b:Boolean)=TextView(this).apply{text=v;textSize=s;setTextColor(c);typeface=if(b)Typeface.DEFAULT_BOLD else Typeface.DEFAULT}
    private fun column(c:Int)=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setBackgroundColor(c)}
    private fun row(c:Int)=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL;setBackgroundColor(c)}
    private fun gap(h:Int)=Space(this).apply{layoutParams=size(1,dp(h))}
    private fun round(c:Int,r:Int)=GradientDrawable().apply{setColor(c);cornerRadius=dp(r).toFloat()}
    private fun gradient(a:Int,b:Int,r:Int)=GradientDrawable(GradientDrawable.Orientation.TL_BR,intArrayOf(a,b)).apply{cornerRadius=dp(r).toFloat()}
    private fun darken(c:Int)=Color.rgb((Color.red(c)*0.82f).toInt(),(Color.green(c)*0.82f).toInt(),(Color.blue(c)*0.82f).toInt())
    private fun outline()=GradientDrawable().apply{setColor(surface);cornerRadius=dp(15).toFloat();setStroke(dp(1),line)}
    private fun outlineBg(c:Int,r:Int)=GradientDrawable().apply{setColor(c);cornerRadius=dp(r).toFloat();setStroke(dp(1),line)}
    private fun dp(v:Int)=(v*resources.displayMetrics.density).toInt()
    private fun size(w:Int,h:Int)=ViewGroup.LayoutParams(w,h)
    private fun matchWrap()=LinearLayout.LayoutParams(-1,-2)
    private fun toast(s:String)=TopNotice.show(this,s,TopNotice.Kind.SUCCESS)
    companion object{private const val FOOTER="Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY"}
}
