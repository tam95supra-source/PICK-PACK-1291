package vn.pickpack1291.app.beta

import android.app.Activity
import android.app.AlertDialog
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
    private val navy = Color.rgb(7,38,92)
    private val blue = Color.rgb(13,78,170)
    private val red = Color.rgb(218,45,53)
    private val green = Color.rgb(36,153,85)
    private val orange = Color.rgb(241,143,24)
    private val teal = Color.rgb(35,151,166)
    private val bg = Color.rgb(248,250,253)
    private val surface = Color.WHITE
    private val ink = Color.rgb(22,33,49)
    private val muted = Color.rgb(96,108,124)
    private val line = Color.rgb(218,225,234)
    private val api = BetaApiClient()
    private val syncApi = BetaApiClient()
    private val cacheApi = BetaApiClient()

    private lateinit var module: String
    private lateinit var login: String
    private lateinit var name: String
    private lateinit var role: String
    private var position = ""
    private var initialMnv = ""
    private var screenState = "ROOT"
    private var syncText: TextView? = null
    private val foregroundSync by lazy {
        ForegroundSyncCoordinator(this, syncApi, object : ForegroundSyncCoordinator.Listener {
            override fun onStatus(status: ForegroundSyncCoordinator.Status) {
                UpdateManager.check(this@OperationsActivity)
                syncText?.text = if(status.connected) "● LIVE  R${status.serverSeq}" else "● OFFLINE"
                syncText?.setTextColor(if(status.connected) green else red)
                if(status.masterChanged || status.masterRevision != MasterDataCache.revision(this@OperationsActivity)) refreshMasterCache()
                if (!status.connected || !status.changed) return
                // List/report screens are read-only and safe to refresh automatically.
                // Labor/resource editors intentionally keep the operator's in-progress input;
                // their writes are still revalidated under the Apps Script / Google Sheet transaction lock.
                when (module) {
                    "LISTS" -> listsScreen()
                    "REPORT" -> reportScreen()
                }
            }

            override fun onAuthExpired() { finish() }
        })
    }

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.statusBarColor = Color.WHITE
        window.navigationBarColor = Color.WHITE
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        module = intent.getStringExtra("module") ?: "LISTS"
        login = intent.getStringExtra("login") ?: ""
        name = intent.getStringExtra("name") ?: login
        role = intent.getStringExtra("role") ?: "USER"
        position = intent.getStringExtra("position") ?: ""
        initialMnv = intent.getStringExtra("mnv") ?: ""
        if (api.token == null) { finish(); return }
        when(module){
            "LABOR"->laborHome()
            "RESOURCES"->resourceHome()
            "REPORT"->reportScreen()
            "SETTINGS"->settingsScreen()
            "STAFF"->staffScreen()
            else->listsScreen()
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

    private fun laborHome() {
        screenState = "LABOR_HOME"
        if (!isAdmin()) { simpleMessage("CÔNG NHẬT", "Chức năng Công nhật dành cho ADMIN/SUPERADMIN theo phân quyền hiện tại."); return }
        val root=baseRoot("CÔNG NHẬT"); val body=body()
        body.addView(txt("Scan để bắt đầu hoặc kết thúc công nhật.",10.5f,muted,false));body.addView(gap(9))
        val mnv=mnvInput("MNV").apply{setText(initialMnv)}
        body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(9));val button=primary("KIỂM TRA",navy){}
        fun submit(){val v=mnv.text.toString().trim();if(v.isBlank()){toast("Nhập MNV.");return};button.isEnabled=false;button.text="ĐANG KIỂM TRA...";api.call("employee_context",JSONObject().put("mnv",v)){r->runOnUiThread{button.isEnabled=true;button.text="KIỂM TRA";if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không kiểm tra được MNV");return@runOnUiThread};showLaborContext(r.json?:JSONObject(),MasterDataCache.snapshot(this@OperationsActivity)?:JSONObject())}}}
        button.setOnClickListener{submit()};bindScannerEnter(mnv){if(button.isEnabled)submit()};body.addView(button,matchWrap())
        if(initialMnv.isNotBlank()) button.post{submit()}
        attach(root,body)
    }

    private fun showLaborContext(ctx:JSONObject, masters:JSONObject){
        screenState = "LABOR_CONTEXT"
        val e=ctx.optJSONObject("employee")?:JSONObject();val state=ctx.optString("state");val active=ctx.optJSONObject("active_labor");val root=baseRoot("CÔNG NHẬT");val body=body();body.addView(employeeCard(e));body.addView(gap(10))
        if(state!="ACTIVE"){body.addView(status(if(state=="ENDED")"MNV ĐÃ HẾT PHIÊN" else "MNV CHƯA VÀO CA",red,Color.rgb(255,238,239)));body.addView(gap(9));body.addView(primary("MNV KHÁC",navy){initialMnv="";laborHome()},matchWrap());attach(root,body);return}
        val s=ctx.optJSONObject("session")?:JSONObject();body.addView(details(listOf("Ca" to s.optString("shift"),"Vị trí" to workText(s.optString("work_choice")),"Vào lúc" to formatIso(s.optString("enter_at")))));body.addView(gap(10))
        if(active!=null){body.addView(status("ĐANG LÀM CÔNG NHẬT",green,Color.rgb(235,248,239)));body.addView(gap(8));body.addView(details(listOf("Nội dung" to active.optString("labor_type"),"Bắt đầu" to formatIso(active.optString("start_at")),"Mốc thời gian" to active.optString("time_marker"),"Ghi chú" to dash(active.optString("note")))));body.addView(gap(9));val note=input("Ghi chú khi kết thúc (tùy chọn)",false);body.addView(note,matchWrap());body.addView(gap(9));val finish=primary("HOÀN THÀNH CÔNG NHẬT",red){};finish.setOnClickListener{finish.isEnabled=false;finish.text="ĐANG GHI...";api.call("labor_finish",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("note",note.text.toString())){r->runOnUiThread{finish.isEnabled=true;finish.text="HOÀN THÀNH CÔNG NHẬT";if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không kết thúc được công nhật")else{toast("Đã hoàn thành công nhật");initialMnv=e.optString("mnv");laborHome()}}}};body.addView(finish,matchWrap())
        }else{
            body.addView(status("CHƯA CÓ CÔNG NHẬT ĐANG LÀM",blue,Color.rgb(237,244,255)));body.addView(gap(9));val types=jsonStrings(masters.optJSONArray("labor_types"));val markers=jsonStrings(masters.optJSONArray("time_markers"));val typeSpinner=spinner((if(types.isEmpty())listOf("Khác")else types).toTypedArray());val markerSpinner=spinner((if(markers.isEmpty())listOf("Trong ngày")else markers).toTypedArray());val note=input("Ghi chú (tùy chọn)",false);body.addView(labelled("Thông tin công nhật",typeSpinner));body.addView(gap(8));body.addView(labelled("Mốc thời gian",markerSpinner));body.addView(gap(8));val fixedMain=foldLocal(e.optString("main_position")).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val deduct=CheckBox(this).apply{text="Khấu trừ nhân sự";isChecked=false;setTextColor(ink);textSize=11f};fun updateDeduct(){val fixedLabor=foldLocal(typeSpinner.selectedItem?.toString().orEmpty()).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val blocked=fixedMain||fixedLabor;deduct.isEnabled=!blocked;if(blocked)deduct.isChecked=false;deduct.setTextColor(if(blocked)muted else ink)};typeSpinner.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){updateDeduct()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};updateDeduct();body.addView(deduct,matchWrap());body.addView(gap(6));body.addView(note,matchWrap());body.addView(gap(9));val start=primary("BẮT ĐẦU CÔNG NHẬT",green){};start.setOnClickListener{start.isEnabled=false;start.text="ĐANG GHI...";api.call("labor_start",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("labor_type",typeSpinner.selectedItem.toString()).put("time_marker",markerSpinner.selectedItem.toString()).put("deduct_staff",deduct.isChecked&&deduct.isEnabled).put("note",note.text.toString())){r->runOnUiThread{start.isEnabled=true;start.text="BẮT ĐẦU CÔNG NHẬT";if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không bắt đầu được công nhật")else{toast("Đã bắt đầu công nhật");initialMnv=e.optString("mnv");laborHome()}}}};body.addView(start,matchWrap())
        }
        body.addView(gap(9));body.addView(primary("MNV KHÁC",navy){initialMnv="";laborHome()},matchWrap());attach(root,body)
    }

    private fun resourceHome(){
        screenState = "RESOURCE_HOME"
        val root=baseRoot("TÀI NGUYÊN");val body=body();val mnv=mnvInput("MNV").apply{setText(initialMnv)};body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(9));val button=primary("KIỂM TRA PHIÊN",navy){}
        fun submit(){val v=mnv.text.toString().trim();if(v.isBlank()){toast("Nhập MNV.");return};button.isEnabled=false;api.call("employee_context",JSONObject().put("mnv",v)){r->runOnUiThread{button.isEnabled=true;if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không kiểm tra được MNV");return@runOnUiThread};if(r.json?.optString("state")!="ACTIVE"){showError("MNV phải đang trong phiên ACTIVE.");return@runOnUiThread};api.call("master_options",JSONObject().put("mnv",v)){m->runOnUiThread{if(handleAuth(m))return@runOnUiThread;showResourceEditor(r.json?:JSONObject(),m.json?:JSONObject())}}}}}
        button.setOnClickListener{submit()};bindScannerEnter(mnv){if(button.isEnabled)submit()};body.addView(button,matchWrap());if(initialMnv.isNotBlank())button.post{submit()};attach(root,body)
    }

    private fun showResourceEditor(ctx:JSONObject,masters:JSONObject){
        screenState = "RESOURCE_EDITOR"
        val e=ctx.optJSONObject("employee")?:JSONObject();val s=ctx.optJSONObject("session")?:JSONObject();val root=baseRoot("TÀI NGUYÊN");val body=body();body.addView(employeeCard(e));body.addView(gap(8));body.addView(details(listOf("Hiện tại" to workText(s.optString("work_choice")),"PDA" to dash(s.optString("pda_serial")),"User Pick" to dash(s.optString("user_pick")),"Bàn Pack" to dash(s.optString("pack_table")),"User Pack" to dash(s.optString("user_pack")))));body.addView(gap(10))
        val choice=spinner(arrayOf("KHÔNG","PICK","PACK"));choice.setSelection(when(s.optString("work_choice")){"PICK"->1;"PACK"->2;else->0});body.addView(labelled("Vị trí trong ca mới",choice));body.addView(gap(8));val box=column(bg);body.addView(box,matchWrap())
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray();val pdaVals=mutableListOf<String>();val pickVals=mutableListOf<String>();val packVals=mutableListOf<String>();var pdaSp:Spinner?=null;var pickSp:Spinner?=null;var packSp:Spinner?=null
        fun rebuild(){box.removeAllViews();pdaVals.clear();pickVals.clear();packVals.clear();when(choice.selectedItem.toString()){
            "PICK"->{val labels=mutableListOf<String>();for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial");if(serial.isNotBlank()){pdaVals.add(serial);labels.add("${p.optString("last5")} • $serial")}};pdaSp=spinner(labels.toTypedArray());box.addView(labelled("PDA",pdaSp!!));selectByValue(pdaSp!!,pdaVals,s.optString("pda_serial"));box.addView(gap(8));val pl=mutableListOf<String>();for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){pl.add(v);pickVals.add(v)}};pickSp=spinner((if(pl.isEmpty())listOf("Không có User Pick khả dụng")else pl).toTypedArray());box.addView(labelled("User Pick (bắt buộc)",pickSp!!));val current=s.optString("user_pick");if(current.isNotBlank()){val ix=pickVals.indexOf(current);if(ix>=0)pickSp!!.setSelection(ix)}}
            "PACK"->{val labels=mutableListOf<String>();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=s.optString("shift"))continue;val t=p.optString("table");if(t.isNotBlank()){packVals.add(t);labels.add("$t • ${p.optString("user_pack")}")}};packSp=spinner(labels.toTypedArray());box.addView(labelled("Bàn Pack + User Pack",packSp!!));selectByValue(packSp!!,packVals,s.optString("pack_table"))}
            else->Unit}}
        choice.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};rebuild();body.addView(gap(12));val save=primary("CẬP NHẬT TÀI NGUYÊN",orange){};save.setOnClickListener{val work=choice.selectedItem.toString();val p=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("work_choice",work);if(work=="PICK"){if(pdaVals.isEmpty()){showError("Không có PDA khả dụng.");return@setOnClickListener};p.put("pda_serial",pdaVals[pdaSp?.selectedItemPosition?:0]);if(pickVals.isEmpty()){showError("Không còn User Pick khả dụng.");return@setOnClickListener};p.put("user_pick",pickVals[pickSp?.selectedItemPosition?:0])};if(work=="PACK"){if(packVals.isEmpty()){showError("Không có bàn Pack khả dụng.");return@setOnClickListener};p.put("pack_table",packVals[packSp?.selectedItemPosition?:0])};save.isEnabled=false;save.text="ĐANG CẬP NHẬT...";api.call("resource_change",p){r->runOnUiThread{save.isEnabled=true;save.text="CẬP NHẬT TÀI NGUYÊN";if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không đổi được tài nguyên")else{toast("Đã cập nhật tài nguyên");initialMnv=e.optString("mnv");resourceHome()}}}};body.addView(save,matchWrap());body.addView(gap(8));body.addView(primary("MNV KHÁC",navy){initialMnv="";resourceHome()},matchWrap());attach(root,body)
    }

    private fun staffScreen(){
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
                box.addView(listCard("${e.optString("mnv")} • ${e.optString("full_name")}","${dash(e.optString("main_position"))} • ${dash(e.optString("supplier"))}\nNgày vào: ${dash(e.optString("start_date"))}"));box.addView(gap(6))
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

    private fun listsScreen(){
        screenState = "LISTS"
        val root=baseRoot("DANH SÁCH");val body=body();val q=input("Tìm MNV / họ tên",false).apply{setSingleLine(true)};body.addView(q,matchWrap());body.addView(gap(8));val buttons=row(bg);val sessions=smallButton("PHIÊN HÔM NAY",blue);val labor=smallButton("CÔNG NHẬT",green);val staff=smallButton("NHÂN SỰ",navy);buttons.addView(sessions,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginEnd=dp(3)});buttons.addView(labor,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3);marginEnd=dp(3)});buttons.addView(staff,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3)});body.addView(buttons,matchWrap());body.addView(gap(9));val box=column(bg);body.addView(box,matchWrap())
        fun loadSessions(){box.removeAllViews();box.addView(txt("Đang tải...",10.5f,muted,false));api.call("list_sessions",JSONObject().put("query",q.text.toString())){r->runOnUiThread{box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Lỗi"));return@runOnUiThread};val a=r.json?.optJSONArray("items")?:JSONArray();if(a.length()==0)box.addView(info("Chưa có phiên phù hợp."));for(i in 0 until a.length()){val s=a.optJSONObject(i)?:continue;val e=s.optJSONObject("employee_snapshot")?:JSONObject();box.addView(listCard("${s.optString("mnv")} • ${e.optString("full_name")}","${s.optString("state")} • ${s.optString("shift")} • ${workText(s.optString("work_choice"))}\nPDA ${dash(s.optString("pda_serial"))} • Pick ${dash(s.optString("user_pick"))} • Pack ${dash(s.optString("pack_table"))}"));box.addView(gap(6))}}}}
        fun loadLabor(){box.removeAllViews();if(!isAdmin()){box.addView(info("Công nhật chỉ hiển thị cho ADMIN/SUPERADMIN."));return};api.call("list_labor"){r->runOnUiThread{box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Lỗi"));return@runOnUiThread};val a=r.json?.optJSONArray("items")?:JSONArray();if(a.length()==0)box.addView(info("Chưa có công nhật hôm nay."));for(i in 0 until a.length()){val l=a.optJSONObject(i)?:continue;val e=l.optJSONObject("employee_snapshot")?:JSONObject();box.addView(listCard("${l.optString("mnv")} • ${e.optString("full_name")}","${l.optString("state")} • ${l.optString("labor_type")}\n${formatIso(l.optString("start_at"))} → ${formatIso(l.optString("end_at"))}"));box.addView(gap(6))}}}}
        fun searchStaff(){val query=q.text.toString().trim();box.removeAllViews();if(query.length<2){box.addView(info("Nhập ít nhất 2 ký tự để tìm nhân sự."));return};val a=MasterDataCache.searchStaff(this,query);for(i in 0 until a.length()){val e=a.optJSONObject(i)?:continue;box.addView(listCard("${e.optString("mnv")} • ${e.optString("full_name")}","${e.optString("main_position")} • ${e.optString("supplier")} • ${e.optString("department")}"));box.addView(gap(6))};if(a.length()==0)box.addView(info("Không có kết quả trong cache. Master data tự làm mới khi Sheet thay đổi."))}
        sessions.setOnClickListener{loadSessions()};labor.setOnClickListener{loadLabor()};staff.setOnClickListener{searchStaff()};q.setOnEditorActionListener{_,_,_->searchStaff();true};loadSessions();attach(root,body)
    }

    private fun reportScreen(){
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
                if(isAdmin()){box.addView(gap(10));box.addView(supportGrid(p.optJSONObject("support")))}
            }
            period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){render()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};render()
        }}
        attach(root,body)
    }

    private fun reportGrid(title:String,data:JSONObject?,firstTitle:String,rowKey:String):View{
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
        val h=TableRow(this);h.addView(cell("Thông tin công nhật",true,true));h.addView(cell("Số lượng",true,true));table.addView(h)
        val rows=data?.optJSONArray("rows")?:JSONArray();for(i in 0 until rows.length()){val x=rows.optJSONObject(i)?:continue;val tr=TableRow(this);tr.addView(cell(x.optString("labor_type"),true));val q=x.optInt("quantity");tr.addView(cell(if(q==0)"" else q.toString()));table.addView(tr)}
        wrap.addView(table,matchWrap());return wrap
    }

    private fun settingsScreen(){
        screenState = "SETTINGS"
        val root=baseRoot("CÀI ĐẶT");val body=body();body.addView(section("Tài khoản"));body.addView(listCard("$name • ${roleText(role)}","Tài khoản: $login${if(position.isBlank())"" else " • Vị trí: $position"}"));body.addView(gap(7));body.addView(primary("ĐỔI MẬT KHẨU",navy){changePasswordDialog()},matchWrap());if(isAdmin()){body.addView(gap(7));body.addView(primary("QUẢN LÝ TÀI KHOẢN",blue){accountManager()},matchWrap())};body.addView(section("Đồng bộ / dữ liệu"));val sync=info("Đang đọc trạng thái Google Sheet...");body.addView(sync,matchWrap());api.call("sync_status"){r->runOnUiThread{if(r.ok){val j=r.json?:JSONObject();sync.text="Google Sheet rev ${j.optLong("server_seq")} • Master rev ${j.optLong("master_revision")} • cache máy rev ${MasterDataCache.revision(this@OperationsActivity)}"}else sync.text="Không đọc được trạng thái Google Sheet"}};body.addView(section("Cập nhật"));body.addView(info("${BuildConfig.CHANNEL} • ${BuildConfig.VERSION_NAME}\nTự kiểm tra phiên bản mới: BẬT. App kiểm tra khi mở/foreground và tự hiện thông báo cập nhật."));body.addView(section("Nhật ký"));body.addView(primary("GỬI BÁO LỖI / CHẨN ĐOÁN",teal){sendDiagnostic()},matchWrap());body.addView(section("Thiết bị"));body.addView(info("Android ${Build.VERSION.RELEASE} • ${Build.MANUFACTURER} ${Build.MODEL}"));body.addView(gap(14));body.addView(primary("ĐĂNG XUẤT",red){api.call("logout"){runOnUiThread{finishAffinity()}}},matchWrap());attach(root,body)
    }

    private fun changePasswordDialog(){
        val box=column(surface).apply{setPadding(dp(8),0,dp(8),0)};val current=input("Mật khẩu hiện tại",true);val next=input("Mật khẩu mới (tối thiểu 8 ký tự)",true);val confirm=input("Nhập lại mật khẩu mới",true);box.addView(current);box.addView(gap(7));box.addView(next);box.addView(gap(7));box.addView(confirm);AlertDialog.Builder(this).setTitle("Đổi mật khẩu").setView(box).setNegativeButton("Hủy",null).setPositiveButton("CẬP NHẬT"){_,_->if(next.text.toString()!=confirm.text.toString()){showError("Mật khẩu xác nhận không khớp.");return@setPositiveButton};api.call("change_password",JSONObject().put("current_password",current.text.toString()).put("new_password",next.text.toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Đổi mật khẩu thất bại")else toast("Đã đổi mật khẩu")}}}.show()
    }

    private fun sendDiagnostic(){LocalLogManager.sendManualReport(this,api,module,syncText?.text?.toString().orEmpty()){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không gửi được báo lỗi")else AlertDialog.Builder(this).setTitle("Đã gửi").setMessage("Báo lỗi thủ công đã được lưu đúng thư mục BÁO LỖI THỦ CÔNG.").setPositiveButton("OK",null).show()}}}

    private fun accountManager(){
        screenState = "ACCOUNT_MANAGER"
        val root=baseRoot("QUẢN LÝ TÀI KHOẢN");val body=body();body.addView(primary("TẠO TÀI KHOẢN",green){accountCreateDialog()},matchWrap());body.addView(gap(10));val box=column(bg);body.addView(box,matchWrap());api.call("account_list"){r->runOnUiThread{box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Lỗi"));return@runOnUiThread};val a=r.json?.optJSONArray("items")?:JSONArray();for(i in 0 until a.length()){val x=a.optJSONObject(i)?:continue;val card=column(surface).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,8);addView(txt("${x.optString("login_id")} • ${x.optString("display_name")}",13f,navy,true));addView(txt("${x.optString("role")} • ${x.optString("status")}",10f,muted,false));if(x.optString("login_id")!=login){addView(gap(6));val newStatus=if(x.optString("status")=="ACTIVE")"DISABLED" else "ACTIVE";addView(smallButton(if(newStatus=="DISABLED")"VÔ HIỆU HÓA" else "KÍCH HOẠT",if(newStatus=="DISABLED")red else green).apply{setOnClickListener{api.call("account_status",JSONObject().put("login_id",x.optString("login_id")).put("status",newStatus)){rr->runOnUiThread{if(!rr.ok)showError(rr.error?:"Lỗi")else accountManager()}}}})}};box.addView(card,matchWrap());box.addView(gap(7))}}};attach(root,body)
    }

    private fun accountCreateDialog(){
        val box=column(surface).apply{setPadding(dp(8),0,dp(8),0)};val loginInput=input("Tài khoản",false);val display=input("Tên hiển thị",false);val roles=if(isSuper())arrayOf("USER","ADMIN")else arrayOf("USER");val roleSp=spinner(roles);val pass=input("Mật khẩu ban đầu (>=8 ký tự)",true);box.addView(loginInput);box.addView(gap(6));box.addView(display);box.addView(gap(6));box.addView(roleSp);box.addView(gap(6));box.addView(pass);AlertDialog.Builder(this).setTitle("Tạo tài khoản").setView(box).setNegativeButton("Hủy",null).setPositiveButton("TẠO"){_,_->api.call("account_upsert",JSONObject().put("login_id",loginInput.text.toString().trim()).put("display_name",display.text.toString().trim()).put("role",roleSp.selectedItem.toString()).put("password",pass.text.toString())){r->runOnUiThread{if(!r.ok)showError(r.error?:"Không tạo được tài khoản")else accountManager()}}}.show()
    }

    private fun refreshMasterCache(){cacheApi.call("master_snapshot"){r->if(r.ok&&r.json!=null)MasterDataCache.save(applicationContext,r.json)}}
    private fun navigateBack(){when(screenState){"LABOR_CONTEXT"->laborHome();"RESOURCE_EDITOR"->resourceHome();"ACCOUNT_MANAGER"->settingsScreen();else->finish()}}
    private fun simpleMessage(title:String,message:String){val root=baseRoot(title);val body=body();body.addView(info(message));attach(root,body)}
    private fun baseRoot(title:String)=column(bg).apply{addView(appBar(title))}
    private fun body()=column(bg).apply{setPadding(dp(15),dp(13),dp(15),dp(58))}
    private fun attach(root:LinearLayout,body:LinearLayout){root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setContentView(host(root))}
    private fun appBar(title:String)=row(navy).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(9),dp(7),dp(10),dp(7));addView(txt("‹",31f,Color.WHITE,false).apply{gravity=Gravity.CENTER;setOnClickListener{navigateBack()}},size(dp(42),dp(45)));addView(txt(title,17f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f));syncText=txt("● SYNC",9.5f,Color.rgb(218,229,248),true).apply{gravity=Gravity.CENTER;setPadding(dp(8),dp(5),dp(8),dp(5))};addView(syncText,size(dp(86),dp(36)))}

    private fun handleAuth(r:BetaApiClient.Result):Boolean{if(r.code==401){AlertDialog.Builder(this).setTitle("Phiên đã hết hạn").setMessage("Quay lại màn hình đăng nhập.").setCancelable(false).setPositiveButton("OK"){_,_->finishAffinity()}.show();return true};return false}
    private fun showError(raw:String){val msg=when{raw.contains("PP_RESOURCE_CONFLICT")->"Tài nguyên vừa được người khác nhận. Tài nguyên cũ vẫn được giữ.";raw.contains("PP_USER_PICK_USED_TODAY")->"User Pick này đã được dùng trong ngày.";raw.contains("PP_USER_PACK_USED_TODAY")->"User Pack này đã được dùng trong ngày.";raw.contains("PP_LABOR_ALREADY_ACTIVE")->"MNV đang có công nhật chưa hoàn thành.";raw.contains("PP_LABOR_NOT_ACTIVE")->"MNV không có công nhật đang hoạt động.";raw.contains("CURRENT_PASSWORD_INVALID")->"Mật khẩu hiện tại không đúng.";raw.contains("PASSWORD_POLICY")->"Mật khẩu mới phải có ít nhất 8 ký tự.";raw.contains("FORBIDDEN")->"Tài khoản không có quyền thực hiện thao tác này.";else->raw};AlertDialog.Builder(this).setTitle("Không thực hiện được").setMessage(msg).setPositiveButton("OK",null).show()}

    private fun employeeCard(e:JSONObject)=column(surface).apply{setPadding(dp(13),dp(11),dp(13),dp(11));background=outlineBg(surface,9);addView(txt("${e.optString("mnv")} • ${e.optString("full_name")}",15f,navy,true));addView(txt("${dash(e.optString("main_position"))} • ${dash(e.optString("supplier"))}",10.5f,ink,false));addView(txt("${dash(e.optString("department"))} • Site ${dash(e.optString("site"))} • Kho ${dash(e.optString("warehouse"))}",10f,muted,false))}
    private fun listCard(title:String,sub:String)=column(surface).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,8);addView(txt(title,12.5f,ink,true));addView(gap(2));addView(txt(sub,10f,muted,false))}
    private fun metric(title:String,value:String,color:Int)=column(surface).apply{setPadding(dp(13),dp(11),dp(13),dp(11));background=outlineBg(surface,9);addView(txt(title,11f,color,true));addView(gap(3));addView(txt(value,13f,ink,true))}
    private fun jsonMapCard(title:String,j:JSONObject?)=column(surface).apply{setPadding(dp(13),dp(10),dp(13),dp(10));background=outlineBg(surface,9);addView(txt(title,11f,navy,true));if(j==null||j.length()==0)addView(txt("Chưa có dữ liệu",10f,muted,false))else{val keys=j.keys();while(keys.hasNext()){val k=keys.next();addView(txt("$k: ${j.optInt(k)}",10.5f,ink,false))}}}
    private fun details(items:List<Pair<String,String>>)=column(surface).apply{setPadding(dp(13),dp(9),dp(13),dp(9));background=outlineBg(surface,9);items.forEach{(k,v)->addView(row(surface).apply{addView(txt(k,10.3f,muted,false),LinearLayout.LayoutParams(0,-2,.45f));addView(txt(if(v.isBlank())"—" else v,10.5f,ink,true).apply{gravity=Gravity.END},LinearLayout.LayoutParams(0,-2,.55f));setPadding(0,dp(3),0,dp(3))})}}
    private fun section(v:String)=txt(v,13.5f,navy,true).apply{setPadding(0,dp(12),0,dp(3))}
    private fun status(v:String,fg:Int,c:Int)=txt(v,11.3f,fg,true).apply{gravity=Gravity.CENTER;setPadding(dp(10),dp(9),dp(10),dp(9));background=round(c,8)}
    private fun info(v:String)=txt(v,10.3f,muted,false).apply{setPadding(dp(11),dp(9),dp(11),dp(9));background=outlineBg(Color.rgb(244,247,251),8)}
    private fun mnvInput(h:String)=input(h,false).apply{setSingleLine(true);inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");imeOptions=EditorInfo.IME_ACTION_DONE}
    private fun bindScannerEnter(v:EditText,submit:()->Unit){v.setOnEditorActionListener{_,id,_->if(id==EditorInfo.IME_ACTION_DONE||id==EditorInfo.IME_ACTION_GO||id==EditorInfo.IME_ACTION_SEARCH){submit();true}else false};v.setOnKeyListener{_,key,event->if(key==KeyEvent.KEYCODE_ENTER&&event.action==KeyEvent.ACTION_UP){submit();true}else false}}
    private fun input(h:String,password:Boolean)=EditText(this).apply{hint=h;textSize=14f;setTextColor(ink);setHintTextColor(Color.rgb(153,163,176));inputType=if(password)InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT;setPadding(dp(12),dp(9),dp(12),dp(9));minHeight=dp(46);background=outline()}
    private fun labelled(l:String,v:View)=column(bg).apply{addView(txt(l,10.5f,ink,true));addView(gap(4));addView(v,matchWrap())}
    private fun spinner(items:Array<String>)=Spinner(this).apply{adapter=ArrayAdapter(this@OperationsActivity,android.R.layout.simple_spinner_dropdown_item,items);setPadding(dp(7),dp(3),dp(7),dp(3));minimumHeight=dp(46);background=outline()}
    private fun primary(t:String,c:Int,click:()->Unit)=Button(this).apply{text=t;textSize=12.2f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;minHeight=dp(48);background=round(c,7);setOnClickListener{click()}}
    private fun smallButton(t:String,c:Int)=Button(this).apply{text=t;textSize=9.5f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;background=round(c,6);setPadding(dp(3),0,dp(3),0)}
    private fun host(content:View):View{val root=EdgeSwipeBackLayout(this){navigateBack()}.apply{setBackgroundColor(bg)};root.addView(content,FrameLayout.LayoutParams(-1,-1).apply{bottomMargin=dp(27)});root.addView(txt(FOOTER,8f,Color.rgb(113,122,136),false).apply{gravity=Gravity.CENTER;maxLines=1},FrameLayout.LayoutParams(-1,dp(23),Gravity.BOTTOM));root.setOnApplyWindowInsetsListener{v,i->val top:Int;val bottom:Int;if(Build.VERSION.SDK_INT>=30){top=i.getInsets(WindowInsets.Type.statusBars()).top;bottom=i.getInsets(WindowInsets.Type.navigationBars()).bottom}else{@Suppress("DEPRECATION")val t=i.systemWindowInsetTop;@Suppress("DEPRECATION")val b=i.systemWindowInsetBottom;top=t;bottom=b};v.setPadding(0,top+dp(7),0,bottom+dp(3));i};root.requestApplyInsets();return root}
    private fun jsonStrings(a:JSONArray?):MutableList<String>{val out=mutableListOf<String>();if(a!=null)for(i in 0 until a.length()){val v=a.optString(i);if(v.isNotBlank())out.add(v)};return out}
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
    private fun outline()=GradientDrawable().apply{setColor(surface);cornerRadius=dp(7).toFloat();setStroke(dp(1),line)}
    private fun outlineBg(c:Int,r:Int)=GradientDrawable().apply{setColor(c);cornerRadius=dp(r).toFloat();setStroke(dp(1),line)}
    private fun dp(v:Int)=(v*resources.displayMetrics.density).toInt()
    private fun size(w:Int,h:Int)=ViewGroup.LayoutParams(w,h)
    private fun matchWrap()=LinearLayout.LayoutParams(-1,-2)
    private fun toast(s:String)=Toast.makeText(this,s,Toast.LENGTH_SHORT).show()
    companion object{private const val FOOTER="Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY"}
}
