package vn.pickpack1291.app.beta

// S11_COMPACT_REPORT_PATCH: compact inner screens and bordered shift reports.

// S10_GENERATED_UI_PATCH: PDA visual/UX corrections for Beta 0.4.2-beta.10.

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
    // S54_BETA48_OWNER_10_FIXES
    // S31_SERVICE_FIRST_HOTPATH
    // S29_OWNER_LOCALFIRST_HISTORY
    // S25_CACHE_FIRST_FALLBACK_SYNC
    // S22_PDA_LOCAL_FIRST_OBSERVABILITY
    private val navy:Int get()=ThemeManager.primaryDark(this)
    private val blue:Int get()=ThemeManager.primary(this)
    private val red = Color.rgb(218,45,53)
    private val green = Color.rgb(36,153,85)
    private val orange = Color.rgb(217,119,6)
    private val teal:Int get()=ThemeManager.primary(this)
    private val accent:Int get()=ThemeManager.accent(this)
    private val bg:Int get()=Color.WHITE
    private val surface = Color.WHITE
    private val ink = Color.rgb(24,44,42)
    private val muted = Color.rgb(100,116,139)
    private val line:Int get()=Color.argb(72,Color.red(teal),Color.green(teal),Color.blue(teal))
    private val api by lazy { BetaApiClient(applicationContext) }
    private val syncApi by lazy { BetaApiClient(applicationContext) }
    private val cacheApi by lazy { BetaApiClient(applicationContext) }
    private val operationalStore by lazy { OperationalDataStore(applicationContext) }
    private val operationalSync by lazy {
        OperationalSyncEngine(this, cacheApi, operationalStore) { changedDates ->
            runOnUiThread {
                if(changedDates.isEmpty()) return@runOnUiThread
                when(screenState){
                    "REPORT" -> reportScreen()
                    "HISTORY" -> historyScreen()
                    "EMPLOYEE", "EMPLOYEE_LOADING" -> if(liveEmployeeMnv.isNotBlank()) renderLocalEmployee(liveEmployeeMnv)
                }
            }
        }
    }
    private lateinit var module: String
    private lateinit var login: String
    private lateinit var name: String
    private lateinit var role: String
    private var effectiveRole = "" // S47_BETA41_OWNER_FIVE_FIXES
    // S47B_BETA41_COMPILE_HOTFIX
    private var position = ""
    private var email = ""
    private var initialMnv = ""
    private var screenState = "ROOT"
    private var networkStatusText: TextView? = null
    private var syncStatusText: TextView? = null
    private var serviceStatusText: TextView? = null
    private var lastConnected: Boolean? = null
    private var lastSyncLatencyMs: Long? = null // S33_OWNER_UI_SYNC_RESOURCES
    private var lastProjectionPending: Int = 0
    private var historySyncInFlight=false // S35_OWNER_UI_HISTORY_CONSISTENCY
    private var historyLastCanonicalRefreshAt=0L
    private var lastLatencyMs: Long? = null
    private var lastSyncE2eMs: Long? = null
    private var serviceProviderCache = "—"
    private var historyDetailMnv = ""
    private var historyDetailName = ""
    private val statusTickerHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val statusTicker = object:Runnable {
        override fun run(){
            refreshHeaderConnection()
            statusTickerHandler.postDelayed(this,750L)
        }
    }
    private var lastPingMs: Long? = null
    private var contentHost: FrameLayout? = null
    private var navHost: FrameLayout? = null
    private data class NavRefs(val cell:LinearLayout,val icon:ImageView,val label:TextView)
    private val navRefs=mutableMapOf<String,NavRefs>()
    private val tabHistory=java.util.ArrayDeque<String>()
    private var liveEmployeeMnv=""
    private var employeeLookupGeneration=0L // S39_EMPLOYEE_SESSION_HISTORY
    private val foregroundSync by lazy {
        ForegroundSyncCoordinator(this, syncApi, object : ForegroundSyncCoordinator.Listener {
            override fun onStatus(status: ForegroundSyncCoordinator.Status) {
                lastConnected = status.connected
                lastSyncLatencyMs = status.latencyMs
                lastProjectionPending = status.projectionPending.coerceAtLeast(0)
                lastLatencyMs = status.latencyMs
                lastSyncE2eMs = status.syncE2eMs
                serviceProviderCache = serviceProviderFromRuntime()
                lastPingMs = status.latencyMs
                refreshHeaderConnection()
                if(status.connected && status.businessDate.isNotBlank()) {
                    val localFloor=status.retentionFloor.ifBlank{
                        runCatching{java.time.LocalDate.parse(status.businessDate).minusDays(44).toString()}.getOrDefault("")
                    }
                    if(localFloor.isNotBlank()) operationalSync.reconcile(status.businessDate,localFloor,status.retentionEpoch,status.dayRevisions)
                }
                if(status.masterChanged || status.masterRevision != MasterDataCache.revision(this@OperationsActivity)) refreshMasterCache()
                if (!status.connected || !status.changed) return
                if(screenState=="HISTORY"){historyLastCanonicalRefreshAt=0L;refreshHistoryCanonical()}
                if(module=="BUSINESS" && liveEmployeeMnv.isNotBlank()) return
                when (screenState) {
                    "LISTS" -> listsScreen()
                    "REPORT" -> reportScreen()
                    "HISTORY" -> historyScreen()
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
        effectiveRole = role
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
            "PDA_EXCHANGE"->pdaExchangeScreen()
            else->{module="BUSINESS";businessHome()}
        }
    }

    override fun onStart() {
        super.onStart()
        PpForegroundGate.enter()
        if (api.token != null) {
            // S43_FOREGROUND_OUTBOX_WAKE: old unresolved events are flushed immediately on a
            // background executor after the activity becomes visible. No polling and no UI wait.
            if (runCatching { OperationalDataStore(this).pendingMutationCount() }.getOrDefault(0) > 0) {
                M2ImmediateOutbox.kick(this)
            }
            foregroundSync.start()
        }
        statusTickerHandler.removeCallbacks(statusTicker)
        statusTickerHandler.post(statusTicker)
    }

    override fun onStop() {
        statusTickerHandler.removeCallbacks(statusTicker)
        PpForegroundGate.leave()
        foregroundSync.stop()
        super.onStop()
    }

    private fun isAdmin() = effectiveRole == "ADMIN" || effectiveRole == "SUPERADMIN"

    private fun isSuper() = effectiveRole == "SUPERADMIN"
    private fun isActualSuper() = role == "SUPERADMIN"

    private fun businessHome(){
        module="BUSINESS";screenState="BUSINESS"
        val root=baseRoot("NGHIỆP VỤ");val body=body()
        val cards=listOf(
            businessCard(R.drawable.ic_pp_scan,"Quét nhân sự","Vào ca / ra ca theo trạng thái hiện tại",true){employeeScan()},
            businessCard(R.drawable.ic_pp_pda_exchange,"Đổi / trả PDA","Đổi PDA có lý do hoặc trả PDA đang sử dụng",true){pdaExchangeScreen()},
            businessCard(R.drawable.ic_pp_drop_receive,"Nhận hàng Rớt","Tiếp nhận nghiệp vụ hàng rớt",true){TopNotice.show(this,"Nhận hàng Rớt đang được chuẩn bị.",TopNotice.Kind.INFO)},
            businessCard(R.drawable.ic_pp_report,"Báo cáo nhân sự","Báo cáo nhân sự Site 1291",isAdmin()){reportScreen()},
            businessCard(R.drawable.ic_pp_task,"Công nhật","Bắt đầu / hoàn thành công nhật",isAdmin()){laborHome()},
            businessCard(R.drawable.ic_pp_resource,"Tài nguyên","Quản lý PDA • User Pick • Bàn Pack • User Pack",isAdmin()){resourceHome()},
            businessCard(R.drawable.ic_pp_ccdc,"Quản lý CCDC","Quản lý công cụ dụng cụ",isAdmin()){TopNotice.show(this,"Quản lý CCDC đang được chuẩn bị.",TopNotice.Kind.INFO)},
            businessCard(R.drawable.ic_pp_document,"Quản lý biên bản","Theo dõi và quản lý biên bản",isAdmin()){TopNotice.show(this,"Quản lý biên bản đang chờ xây dựng.",TopNotice.Kind.INFO)}
        )
        body.addView(businessRow(cards[0],cards[1]));body.addView(gap(9))
        body.addView(businessRow(cards[2],cards[3]));body.addView(gap(9))
        body.addView(businessRow(cards[4],cards[5]));body.addView(gap(9))
        body.addView(businessRow(cards[6],cards[7]))
        attach(root,body)
    }

    private fun employeeScan() {
        screenState = "SCAN"; liveEmployeeMnv = ""
        val root=column(bg);root.addView(appBar("QUÉT QR NHÂN SỰ"))
        val body=column(bg).apply{setPadding(dp(10),dp(8),dp(10),dp(84))}
        val mnv=mnvInput("Scan / Nhập mã nhân viên để ghi nhận ra ca / vào ca")
        body.addView(mnv,matchWrap());body.addView(gap(4))
        var busy=false
        fun submit(){val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét Mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);mnv.postDelayed({busy=false},600)}
        bindScannerEnter(mnv){submit()}
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);mnv.requestFocus()
    }

    private fun renderLocalEmployee(mnv:String):Boolean{
        val ctx=PdaLocalProjection.employeeContext(this,mnv) ?: return false
        if(!ctx.optBoolean("session_known",true)){
            liveEmployeeMnv=mnv
            renderCachedEmployee(ctx.optJSONObject("employee")?:JSONObject())
            TopNotice.show(this,"Đã đọc nhân sự từ PDA • đang đối chiếu phiên nền",TopNotice.Kind.INFO)
            return true
        }
        val masters=if(ctx.optString("state")=="NOT_ENTERED")PdaLocalProjection.resourceOptions(this,mnv) else null
        renderEmployee(ctx,masters)
        return true
    }

    // S38_ATTENDANCE_UI: render staff identity immediately, then use current Service session/resource options.
    // S39_EMPLOYEE_SESSION_HISTORY: normalized master-backed MNV + stale callback fence.
    // S40_OWNER_LOCAL_FIRST_REPAIR: owner lock = SQLite/PDA first, Service reconcile later.
    // S45_BETA40_OWNER_FIXES: never let an N-1 Service response replace current N local context.
    private fun loadEmployee(mnv: String, button: Button? = null) {
        val resolved=MasterDataCache.resolveEmployeeMnv(this,mnv)
        if(resolved.isBlank()){button?.isEnabled=true;showError("MNV_REQUIRED");return}
        val generation=++employeeLookupGeneration
        val currentDate=operationalStore.businessDate()
        val localNow=PdaLocalProjection.employeeContext(this,resolved)
        val localOptions=PdaLocalProjection.resourceOptions(this,resolved)
        val cached=MasterDataCache.employee(this,resolved)
        if(localNow!=null)renderEmployee(localNow,localOptions)else if(cached!=null)renderCachedEmployee(cached)
        api.call("employee_context",JSONObject().put("mnv",resolved).put("include_options",true).put("include_labor",true)){result->runOnUiThread{
            if(generation!=employeeLookupGeneration)return@runOnUiThread
            button?.isEnabled=true
            val overlay=PdaLocalProjection.employeeContext(this@OperationsActivity,resolved)
            val refreshedOptions=PdaLocalProjection.resourceOptions(this@OperationsActivity,resolved)
            if(!result.ok){
                if(overlay!=null){renderEmployee(overlay,refreshedOptions);TopNotice.show(this@OperationsActivity,"Service chưa xác nhận được; thao tác vẫn lưu local và sẽ đồng bộ khi ứng dụng ở foreground.",TopNotice.Kind.WARNING)}
                else if(result.code==401)sessionExpired()
                else showError(result.error?:"Không kiểm tra được mã nhân viên")
                return@runOnUiThread
            }
            if(overlay!=null&&overlay.optString("reconciliation_state")=="LOCAL_PENDING"){renderEmployee(overlay,refreshedOptions);return@runOnUiThread}
            val ctx=result.json?:JSONObject()
            val remoteDate=ctx.optString("business_date").trim()
            if(remoteDate.isNotBlank()&&remoteDate!=currentDate){
                if(overlay!=null)renderEmployee(overlay,refreshedOptions)else if(cached!=null)renderCachedEmployee(cached)
                return@runOnUiThread
            }
            val remote=ctx.optJSONObject("options")
            val options=if(remote==null)refreshedOptions else JSONObject(remote.toString()).apply{
                for(k in listOf("user_picks_reissue","pack_tables_reissue")){
                    val local=refreshedOptions.optJSONArray(k)
                    if((optJSONArray(k)?.length()?:0)==0&&local!=null&&local.length()>0)put(k,local)
                }
            }
            renderEmployee(ctx,options)
        }}
    }

    private fun renderCachedEmployee(e: JSONObject) {
        screenState="EMPLOYEE_LOADING";val cachedMnv=e.optString("mnv")
        val root=column(bg);root.addView(appBar("QUÉT QR NHÂN SỰ"));val body=column(bg).apply{setPadding(dp(16),dp(12),dp(16),dp(58))}
        val scan=mnvInput("Quét QR hoặc nhập mã nhân viên").apply{setText("")};body.addView(labelled("Mã nhân viên",scan));body.addView(gap(9));body.addView(employeeCard(e));body.addView(gap(9));body.addView(status("ĐANG XÁC NHẬN TRẠNG THÁI PHIÊN...",blue,Color.rgb(237,244,255)))
        var busy=false;fun submit(){val v=scan.text.toString();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);scan.postDelayed({busy=false},500)};bindScannerEnter(scan){submit()}
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);scan.requestFocus()
        liveEmployeeMnv=cachedMnv
    }

    private fun renderEmployeeLookupRetry(e: JSONObject, mnv: String, reason: String) {
        screenState="EMPLOYEE_LOOKUP_ERROR";liveEmployeeMnv=mnv
        val root=column(bg);root.addView(appBar("QUÉT QR NHÂN SỰ"));val body=column(bg).apply{setPadding(dp(16),dp(12),dp(16),dp(58))}
        val scan=mnvInput("Quét QR hoặc nhập mã nhân viên").apply{setText("")};body.addView(labelled("Mã nhân viên",scan));body.addView(gap(9));body.addView(employeeCard(e));body.addView(gap(9))
        body.addView(status("CHƯA XÁC NHẬN ĐƯỢC PHIÊN",orange,Color.rgb(255,251,235)));body.addView(gap(6));body.addView(info("Dữ liệu nhân sự đã có trên PDA nhưng Service chưa trả được trạng thái phiên. Mã lỗi: ${reason.take(100)}"));body.addView(gap(8))
        body.addView(primary("THỬ XÁC NHẬN LẠI",navy){loadEmployee(mnv)},matchWrap())
        var busy=false;fun submit(){val v=scan.text.toString();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);scan.postDelayed({busy=false},500)};bindScannerEnter(scan){submit()}
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);scan.requestFocus()
    }

    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {
        screenState="EMPLOYEE"
        val e=ctx.optJSONObject("employee")?:JSONObject();val state=ctx.optString("state");val currentMnv=e.optString("mnv");liveEmployeeMnv=currentMnv
        val root=column(bg);root.addView(appBar("QUÉT QR NHÂN SỰ"));val body=column(bg).apply{setPadding(dp(16),dp(12),dp(16),dp(58))}
        val scan=mnvInput("Quét QR hoặc nhập mã nhân viên").apply{setText("")}
        body.addView(labelled("Mã nhân viên",scan));body.addView(gap(9));body.addView(employeeCard(e));body.addView(gap(10))
        var busy=false
        fun submit(){val v=scan.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);scan.postDelayed({busy=false},600)}
        bindScannerEnter(scan){submit()}
        when(state){"ACTIVE"->renderActive(body,ctx);"ENDED"->renderEnded(body,ctx);else->renderEnter(body,ctx,masters?:JSONObject())}
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);scan.requestFocus()
    }

    private fun scheduleAttendanceAutoReset(mnv:String,generation:Long){
        val expected=mnv.trim()
        android.os.Handler(mainLooper).postDelayed({
            // If another code has already been scanned/rendered, never clear that newer employee.
            if(screenState=="EMPLOYEE"&&liveEmployeeMnv==expected&&employeeLookupGeneration==generation)employeeScan()
        },650L)
    }

    // S48_BETA42_SHIFT_WORK_SUMMARY: local-first shift timeline + explicit PDA identity.
    private fun sessionWorkDetail(payload:JSONObject):String{
        val parts=mutableListOf<String>()
        val work=payload.optString("work_choice").trim().uppercase()
        when(work){
            "PICK"->{parts.add("PICK");payload.optString("pda_serial").trim().takeIf{it.isNotBlank()}?.let{parts.add("Seri PDA $it")};payload.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let{parts.add("User Pick $it")}}
            "PACK"->{parts.add("PACK");payload.optString("pack_table").trim().takeIf{it.isNotBlank()}?.let{parts.add("Bàn $it")};payload.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let{parts.add("User Pack $it")}}
            "KHÔNG","KHONG"->parts.add("Không gán Pick/Pack")
        }
        payload.optString("labor_type").trim().takeIf{it.isNotBlank()}?.let{parts.add("Công nhật: $it")}
        payload.optString("time_marker").trim().takeIf{it.isNotBlank()}?.let{parts.add("Mốc $it")}
        return parts.joinToString(" • ")
    }

    private fun sessionTimelineItems(mnv:String):MutableList<JSONObject>{
        val merged=LinkedHashMap<String,JSONObject>();val date=operationalStore.businessDate()
        val allowed=setOf("ATTENDANCE_ENTER","ENTER","RESOURCE_CHANGE","RESOURCE","LABOR_START","LABOR_FINISH","ATTENDANCE_EXIT","EXIT","ATTENDANCE_TIME_CORRECTED","ATTENDANCE_EXIT_DELETED")
        fun payload(e:JSONObject):JSONObject{val raw=e.optString("payload_json");if(raw.isNotBlank())return runCatching{JSONObject(raw)}.getOrDefault(JSONObject());return e.optJSONObject("payload")?:JSONObject()}
        fun detail(type:String,e:JSONObject,p:JSONObject):String{
            if(type=="ATTENDANCE_TIME_CORRECTED"){val field=if(p.optString("field")=="enter_at")"Giờ vào" else "Giờ ra";return "$field: ${formatIso(p.optString("before_value"))} → ${formatIso(p.optString("after_value"))} • Lý do: ${p.optString("reason").ifBlank{"—"}}"}
            if(type=="ATTENDANCE_EXIT_DELETED")return "Xóa mốc ra ca ${formatIso(p.optString("before_exit_at"))} • Lý do: ${p.optString("reason").ifBlank{"—"}}"
            if(type=="RESOURCE_CHANGE"){val after=p.optJSONObject("after");if(after!=null)return sessionWorkDetail(after)}
            return e.optString("detail").ifBlank{sessionWorkDetail(p)}
        }
        val day=operationalStore.loadDay(date);val events=day?.optJSONArray("events")?:JSONArray()
        for(i in 0 until events.length()){
            val e=events.optJSONObject(i)?:continue;val p=payload(e);val who=e.optString("mnv").ifBlank{p.optString("mnv")}.trim();if(who!=mnv)continue
            val type=e.optString("event_type").uppercase();if(type !in allowed)continue
            val copy=JSONObject(e.toString()).put("timeline_source","CANONICAL").put("mnv",mnv).put("detail",detail(type,e,p)).put("actor",e.optString("actor").ifBlank{e.optString("actor_id")})
            if(copy.optString("at_iso").isBlank())copy.put("at_iso",e.optString("committed_at").ifBlank{e.optString("occurred_at")})
            val id=copy.optString("event_id").ifBlank{"canonical:$date:$i:${copy.optString("at_iso")}"};merged[id]=copy
        }
        for(local in operationalStore.localHistoryAll()){
            val id=local.optString("event_id").trim();if(id.isBlank())continue;val body=local.optJSONObject("body")?:JSONObject();val p=body.optJSONObject("payload")?:body;if(p.optString("mnv").trim()!=mnv)continue
            val action=body.optString("action").trim();val type=when(action){"enter"->"ATTENDANCE_ENTER";"resource_change"->"RESOURCE_CHANGE";"labor_start"->"LABOR_START";"labor_finish"->"LABOR_FINISH";"exit"->"ATTENDANCE_EXIT";else->""};if(type.isBlank())continue
            val existing=merged[id];if(existing!=null){existing.put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at",0L));continue}
            val label=when(type){"ATTENDANCE_ENTER"->"Vào ca";"RESOURCE_CHANGE"->"Cập nhật công việc";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"ATTENDANCE_EXIT"->"Ra ca";else->action}
            merged[id]=JSONObject().put("event_id",id).put("event_type",type).put("label",label).put("mnv",mnv).put("actor","Thiết bị này").put("detail",sessionWorkDetail(p)).put("timeline_source","LOCAL_PDA").put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at",0L))
        }
        val out=merged.values.toMutableList();fun atMillis(e:JSONObject):Long{val q=e.optLong("local_queued_at",0L);if(q>0L)return q;return runCatching{Instant.parse(e.optString("at_iso").ifBlank{e.optString("at")}).toEpochMilli()}.getOrDefault(0L)};out.sortBy{atMillis(it)};return out
    }

    private fun sessionEventTitle(typeRaw:String,label:String):String=when(typeRaw.uppercase()){
        "ATTENDANCE_ENTER","ENTER"->"VÀO CA";"RESOURCE_CHANGE","RESOURCE"->"CẬP NHẬT CÔNG VIỆC";"LABOR_START"->"BẮT ĐẦU CÔNG NHẬT";"LABOR_FINISH"->"HOÀN THÀNH CÔNG NHẬT";"ATTENDANCE_EXIT","EXIT"->"RA CA";"ATTENDANCE_TIME_CORRECTED"->"SỬA THỜI GIAN VÀO / RA";"ATTENDANCE_EXIT_DELETED"->"XÓA GHI NHẬN RA CA";else->label.ifBlank{"THAO TÁC"}.uppercase()
    }

    private fun sessionEventTime(e:JSONObject):String{
        val local=e.optLong("local_queued_at",0L)
        if(local>0L)return Instant.ofEpochMilli(local).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("HH:mm:ss"))
        return formatIso(e.optString("at_iso").ifBlank{e.optString("at")})
    }

    private fun addPdaIdentity(body:LinearLayout,ses:JSONObject){
        fun clean(v:String)=v.trim().takeUnless{it.equals("null",true)||it=="—"}?:""
        val serial=clean(ses.optString("pda_serial"));val pdaStatus=clean(ses.optString("pda_enter_status"));body.addView(section("PDA ĐANG GIỮ TRONG PHIÊN"))
        if(serial.isBlank()){body.addView(info("Hiện tại phiên không giữ PDA; khi ra ca sẽ không yêu cầu đối chiếu tình trạng PDA."));return}
        body.addView(column(surface).apply{setPadding(dp(14),dp(12),dp(14),dp(12));background=outlineBg(surface,16);elevation=dp(2).toFloat();addView(txt("SERI PDA",9.5f,muted,true));addView(txt(serial,15f,navy,true));addView(gap(8));addView(txt("TÌNH TRẠNG KHI NHẬN PDA HIỆN TẠI",9.5f,muted,true));addView(txt(pdaStatus.ifBlank{"Chưa có dữ liệu tình trạng"},12f,if(pdaStatus.isBlank())orange else teal,true))},matchWrap())
    }

    private fun addSessionTimeline(body:LinearLayout,mnv:String){
        body.addView(section("DIỄN BIẾN CÔNG VIỆC TRONG CA"))
        body.addView(info("Mỗi lần đổi vị trí / Pick / Pack được giữ thành một mốc riêng. Mốc mới không ghi đè lịch sử cũ."));body.addView(gap(7))
        val items=sessionTimelineItems(mnv)
        if(items.isEmpty()){body.addView(info("Chưa có mốc công việc trong bộ nhớ PDA. Hệ thống sẽ bổ sung khi snapshot đồng bộ về."));return}
        for(e in items){
            val title=sessionEventTitle(e.optString("event_type"),e.optString("label"));val detail=e.optString("detail").trim();val actor=e.optString("actor").ifBlank{"Hệ thống"};val localStatus=e.optString("local_status")
            val card=column(surface).apply{
                setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,14)
                val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL;addView(txt(title,10.7f,navy,true),LinearLayout.LayoutParams(0,-2,1f));addView(txt(sessionEventTime(e),9.4f,muted,true))};addView(top,matchWrap())
                if(detail.isNotBlank()){addView(gap(4));addView(txt(detail,10f,ink,false))}
                addView(gap(4));val statusText=when(localStatus){"LOCAL_PENDING","PENDING","OFFLINE_PROVISIONAL"->" • Chờ đồng bộ";"RETRY"->" • Chờ gửi lại";"REVIEW_REQUIRED","CONFLICT"->" • Cần kiểm tra";"REJECTED"->" • Bị từ chối";else->""};addView(txt("Người thực hiện: $actor$statusText",9.2f,muted,false))
            }
            body.addView(card,matchWrap());body.addView(gap(6))
        }
    }

    // S49_BETA43_SESSION_ADMIN_CORRECTIONS
    // S49B_BETA43_KOTLIN_QUOTE_HOTFIX
    // S49C_BETA43_KOTLIN_SYNTAX_HOTFIX
    private fun pickSummary(s:JSONObject):String{val x=mutableListOf<String>();s.optString("pda_serial").trim().takeIf{it.isNotBlank()}?.let{x.add("PDA $it")};s.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let{x.add("User $it")};return if(x.isEmpty())"Không" else x.joinToString(" • ")}
    private fun packSummary(s:JSONObject):String{val x=mutableListOf<String>();s.optString("pack_table").trim().takeIf{it.isNotBlank()}?.let{x.add("Bàn $it")};s.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let{x.add("User $it")};return if(x.isEmpty())"Không" else x.joinToString(" • ")}
    private fun returnedSessionContext(ctx:JSONObject,r:BetaApiClient.Result):JSONObject?{val ss=r.json?.optJSONObject("session")?:return null;return JSONObject(ctx.toString()).put("session",ss).put("state",ss.optString("state"))}

    // S50_BETA44_OWNER_USER_PROJECTION_ADMIN_BULK_SYNC_VI
    private fun verifyDeletePassword(actionLabel:String,after:()->Unit){
        val pw=input("Mật khẩu hiện tại",true)
        val dialog=AlertDialog.Builder(this).setTitle("Xác thực trước khi xóa").setMessage("Nhập mật khẩu của tài khoản $login để $actionLabel.").setView(pw).setNegativeButton("Hủy",null).setPositiveButton("XÁC THỰC",null).create()
        dialog.setOnShowListener{val btn=dialog.getButton(AlertDialog.BUTTON_POSITIVE);btn.setOnClickListener{val value=pw.text.toString();if(value.isBlank()){showError("Nhập mật khẩu hiện tại.");return@setOnClickListener};btn.isEnabled=false;btn.text="ĐANG XÁC THỰC...";api.login(login,value){r->runOnUiThread{btn.isEnabled=true;btn.text="XÁC THỰC";if(!r.ok){showError("Mật khẩu không đúng hoặc không thể xác thực.");return@runOnUiThread};dialog.dismiss();after()}}}}
        dialog.show();pw.requestFocus()
    }

    private fun sessionWorkEditor(ctx:JSONObject){
        val ses=ctx.optJSONObject("session")?:return;val mnv=ses.optString("mnv")
        if(ses.optString("state")!="ACTIVE"){showError("Phiên đã ra ca. ADMIN/SUPERADMIN hãy hủy ghi nhận ra ca trước khi sửa công việc.");return}
        val options=PdaLocalProjection.resourceOptions(this,mnv)
        val pdas=options.optJSONArray("pdas")?:JSONArray();val picks=options.optJSONArray("user_picks")?:JSONArray();val pickReissue=options.optJSONArray("user_picks_reissue")?:JSONArray()
        val packs=options.optJSONArray("pack_tables")?:JSONArray();val packReissue=options.optJSONArray("pack_tables_reissue")?:JSONArray()
        val dialogBody=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))}
        dialogBody.addView(info("PICK và PACK là hai phần độc lập. Có thể giữ đồng thời cả hai; lưu mới chỉ cập nhật trạng thái hiện tại, lịch sử các lần trước vẫn giữ nguyên."));dialogBody.addView(gap(8))
        val pickOn=CheckBox(this).apply{text="Có công việc PICK";isChecked=ses.optString("pda_serial").isNotBlank()||ses.optString("user_pick").isNotBlank()||ses.optString("work_choice")=="PICK";setTextColor(ink)}
        val packOn=CheckBox(this).apply{text="Có công việc PACK";isChecked=ses.optString("pack_table").isNotBlank()||ses.optString("user_pack").isNotBlank()||ses.optString("work_choice")=="PACK";setTextColor(ink)}
        dialogBody.addView(pickOn,matchWrap());dialogBody.addView(packOn,matchWrap());dialogBody.addView(gap(7));val host=column(surface);dialogBody.addView(host,matchWrap())
        var pdaField:AutoCompleteTextView?=null;var selectedPda:JSONObject?=null
        var pickSpinner:Spinner?=null;var pickChoices=mutableListOf<Pair<String,Boolean>>()
        var selectedPack:JSONObject?=null;var allowPickReissue=false;var allowPackReissue=false
        fun rebuild(){
            host.removeAllViews();pdaField=null;selectedPda=null;pickSpinner=null;pickChoices.clear();selectedPack=null
            if(pickOn.isChecked){
                host.addView(section("PICK"))
                pdaField=pdaInput(pdas,ses.optString("pda_serial")){selectedPda=it}
                host.addView(labelled("PDA (có thể đổi / trả)",pdaField!!));host.addView(gap(4));host.addView(pdaSelectedPanel(pdas,pdaField!!),matchWrap());host.addView(gap(5))
                host.addView(smallButton("TRẢ PDA",orange).apply{setOnClickListener{selectedPda=null;pdaField?.setText("",false)}},matchWrap());host.addView(gap(7))
                val base=mutableListOf<String>();for(i in 0 until picks.length()){val id=picks.optString(i).trim();if(id.isNotBlank()&&!base.contains(id))base.add(id)}
                val currentPick=ses.optString("user_pick").trim();if(currentPick.isNotBlank()&&!base.contains(currentPick))base.add(currentPick)
                pickChoices=mutableListOf("" to false);val labels=mutableListOf("Không dùng")
                sortedByNaturalUser(base){it}.forEach{pickChoices.add(it to false);labels.add(it)}
                if(allowPickReissue){
                    val used=mutableListOf<String>();for(i in 0 until pickReissue.length()){val id=pickReissue.optJSONObject(i)?.optString("id").orEmpty().trim();if(id.isNotBlank()&&!base.contains(id)&&!used.contains(id))used.add(id)}
                    sortedByNaturalUser(used){it}.forEach{pickChoices.add(it to true);labels.add("⚠ $it • ĐÃ DÙNG HÔM NAY")}
                }
                pickSpinner=spinner(labels.toTypedArray());val cur=pickChoices.indexOfFirst{it.first==currentPick};if(cur>=0)pickSpinner!!.setSelection(cur)
                val userRow=row(surface).apply{gravity=Gravity.CENTER_VERTICAL}
                userRow.addView(pickSpinner!!,LinearLayout.LayoutParams(0,dp(50),1.35f).apply{marginEnd=dp(5)})
                userRow.addView(compactReissueButton("Phát lại user pick",pickReissue.length()>0&&!allowPickReissue){allowPickReissue=true;rebuild()},LinearLayout.LayoutParams(0,dp(46),.85f))
                host.addView(labelled("User Pick hy1.outbound",userRow));host.addView(gap(9))
            }
            if(packOn.isChecked){
                host.addView(section("PACK"))
                val rows=mutableListOf<JSONObject>()
                fun addPack(a:JSONArray,duplicate:Boolean){for(i in 0 until a.length()){val o=a.optJSONObject(i)?:continue;val t=o.optString("table").trim();val u=o.optString("user_pack").trim();if(t.isBlank()||u.isBlank())continue;val existing=rows.indexOfFirst{it.optString("table")==t&&it.optString("user_pack")==u};if(existing>=0){if(!duplicate)rows[existing].put("duplicate_user",false);continue};rows.add(JSONObject(o.toString()).put("duplicate_user",duplicate))}}
                addPack(packs,false);if(allowPackReissue)addPack(packReissue,true)
                val currentTable=ses.optString("pack_table").trim();val currentUser=ses.optString("user_pack").trim()
                if(currentTable.isNotBlank()&&currentUser.isNotBlank()&&!rows.any{it.optString("table")==currentTable&&it.optString("user_pack")==currentUser})rows.add(JSONObject().put("table",currentTable).put("user_pack",currentUser).put("duplicate_user",false))
                val tables=rows.map{it.optString("table")}.filter{it.isNotBlank()}.distinct().sortedWith(Comparator{a,b->naturalUserCompare(a,b)})
                val tableSp=spinner((if(tables.isEmpty())listOf("Không có bàn Pack khả dụng")else tables).toTypedArray());val tableCur=tables.indexOf(currentTable);if(tableCur>=0)tableSp.setSelection(tableCur)
                host.addView(labelled("Bàn Pack",tableSp));host.addView(gap(7));val userHost=column(surface);host.addView(userHost,matchWrap())
                fun renderPackUsers(){
                    userHost.removeAllViews();selectedPack=null
                    if(tables.isEmpty()){userHost.addView(info("Không có User Pack khả dụng."));return}
                    val table=tables.getOrNull(tableSp.selectedItemPosition).orEmpty();val mapped=sortedByNaturalUser(rows.filter{it.optString("table")==table}){it.optString("user_pack")}
                    val labels=mapped.map{if(it.optBoolean("duplicate_user"))"⚠ ${it.optString("user_pack")} • ĐÃ DÙNG HÔM NAY" else it.optString("user_pack")}
                    val userSp=spinner((if(labels.isEmpty())listOf("Không có User Pack")else labels).toTypedArray());val userCur=mapped.indexOfFirst{it.optString("table")==currentTable&&it.optString("user_pack")==currentUser};if(userCur>=0)userSp.setSelection(userCur)
                    selectedPack=mapped.getOrNull(userSp.selectedItemPosition)
                    userSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){selectedPack=mapped.getOrNull(pos)};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit}
                    val userRow=row(surface).apply{gravity=Gravity.CENTER_VERTICAL};userRow.addView(userSp,LinearLayout.LayoutParams(0,dp(50),1.35f).apply{marginEnd=dp(5)})
                    userRow.addView(compactReissueButton("Phát lại user pack",packReissue.length()>0&&!allowPackReissue){allowPackReissue=true;rebuild()},LinearLayout.LayoutParams(0,dp(46),.85f));userHost.addView(labelled("User Pack",userRow))
                }
                tableSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){renderPackUsers()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};renderPackUsers();host.addView(gap(7))
            }
            if(!pickOn.isChecked&&!packOn.isChecked)host.addView(info("Không gán công việc PICK/PACK. Lưu để trả toàn bộ tài nguyên đang giữ."))
        }
        pickOn.setOnCheckedChangeListener{_,_->rebuild()};packOn.setOnCheckedChangeListener{_,_->rebuild()};rebuild()
        AlertDialog.Builder(this).setTitle("Thêm / sửa công việc trong ca").setView(ScrollView(this).apply{addView(dialogBody)}).setNegativeButton("Hủy",null).setPositiveButton("LƯU"){_,_->
            val p=JSONObject().put("session_id",ses.optString("session_id")).put("idempotency_key",UUID.randomUUID().toString())
            val pickChoice=if(pickOn.isChecked)pickChoices.getOrNull(pickSpinner?.selectedItemPosition?:0) else null;val pick=pickChoice?.first.orEmpty();val pda=if(pickOn.isChecked)selectedPda?.optString("serial").orEmpty() else ""
            p.put("pda_serial",pda).put("user_pick",pick)
            var reissue=pickChoice?.second==true
            if(packOn.isChecked){val row=selectedPack;if(row==null){showError("Chọn Bàn Pack + User Pack hợp lệ.");return@setPositiveButton};p.put("pack_table",row.optString("table")).put("user_pack",row.optString("user_pack"));reissue=reissue||row.optBoolean("duplicate_user")}else p.put("pack_table","").put("user_pack","")
            if(reissue)p.put("duplicate_user",true)
            val current=ses.optString("work_choice");val primary=when{pickOn.isChecked&&packOn.isChecked&&current in setOf("PICK","PACK")->current;pickOn.isChecked->"PICK";packOn.isChecked->"PACK";else->"KHONG"}
            val baseNote=when{pickOn.isChecked&&packOn.isChecked->"PICK + PACK";pickOn.isChecked->"PICK";packOn.isChecked->"PACK";else->"Đã trả tài nguyên"};p.put("work_choice",primary).put("resource_note",if(reissue)"$baseNote • PHÁT LẠI USER" else baseNote)
            api.call("session_work_update",p){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không cập nhật được công việc");return@runOnUiThread};TopNotice.show(this,"Đã cập nhật công việc trong ca.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();val next=returnedSessionContext(ctx,r);if(next!=null)renderEmployee(next,PdaLocalProjection.resourceOptions(this,mnv))else loadEmployee(mnv)}}
        }.show()
    }

    private fun editableTime(iso:String):String=runCatching{Instant.parse(iso).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss"))}.getOrDefault(iso)
    private fun parseEditableTime(v:String):String?=runCatching{java.time.LocalDateTime.parse(v.trim(),DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss")).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toInstant().toString()}.getOrNull()
    private fun editAttendanceTime(ctx:JSONObject,field:String){
        if(!isAdmin())return;val ses=ctx.optJSONObject("session")?:return;val old=ses.optString(field);if(old.isBlank()){showError("Chưa có mốc thời gian để sửa.");return};val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};val time=input("dd/MM/yyyy HH:mm:ss",false).apply{setText(editableTime(old))};val reason=input("Lý do điều chỉnh",false).apply{setText("Điều chỉnh theo xác nhận thực tế")};box.addView(info("Giờ ghi nhận ban đầu vẫn được giữ trong lịch sử audit. Sheet RA/VÀO chỉ hiển thị giờ sửa sau cùng."));box.addView(gap(7));box.addView(labelled(if(field=="enter_at")"Giờ vào ca mới" else "Giờ ra ca mới",time));box.addView(gap(7));box.addView(labelled("Lý do",reason));AlertDialog.Builder(this).setTitle(if(field=="enter_at")"Sửa giờ vào ca" else "Sửa giờ ra ca").setView(box).setNegativeButton("Hủy",null).setPositiveButton("LƯU"){_,_->val parsed=parseEditableTime(time.text.toString());if(parsed==null){showError("Thời gian phải đúng định dạng dd/MM/yyyy HH:mm:ss.");return@setPositiveButton};if(reason.text.toString().trim().length<3){showError("Nhập lý do điều chỉnh.");return@setPositiveButton};api.call("attendance_time_correct",JSONObject().put("session_id",ses.optString("session_id")).put("field",field).put("corrected_at",parsed).put("reason",reason.text.toString().trim()).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không sửa được thời gian");return@runOnUiThread};TopNotice.show(this,"Đã sửa thời gian và lưu audit.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();val next=returnedSessionContext(ctx,r);if(next!=null)renderEmployee(next,PdaLocalProjection.resourceOptions(this,ses.optString("mnv")))else loadEmployee(ses.optString("mnv"))}}}.show()
    }

    private fun deleteExitRecord(ctx:JSONObject){
        if(!isAdmin())return;val ses=ctx.optJSONObject("session")?:return;val mnv=ses.optString("mnv");val reason=input("Lý do xóa ghi nhận ra ca",false).apply{setText("Bắn nhầm ra ca")}
        val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8));addView(info("Mốc RA sẽ bị xóa khỏi sheet RA/VÀO và phiên được mở lại. Nhật ký kiểm toán vẫn được giữ."));addView(gap(7));addView(reason,matchWrap())}
        AlertDialog.Builder(this).setTitle("Hủy ghi nhận RA CA?").setView(box).setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->if(reason.text.toString().trim().length<3){showError("Nhập lý do xóa.");return@setPositiveButton};verifyDeletePassword("xóa ghi nhận ra ca"){api.call("attendance_exit_delete",JSONObject().put("session_id",ses.optString("session_id")).put("reason",reason.text.toString().trim()).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không xóa được mốc ra ca");return@runOnUiThread};val conflicts=r.json?.optJSONArray("resource_reacquire_conflicts")?:JSONArray();TopNotice.show(this,if(conflicts.length()>0)"Đã mở lại phiên; một số tài nguyên không thể tự cấp lại." else "Đã xóa mốc ra ca và mở lại phiên.",if(conflicts.length()>0)TopNotice.Kind.WARNING else TopNotice.Kind.SUCCESS);foregroundSync.requestSync();loadEmployee(mnv)}}}}.show()
    }

    private fun renderActive(body: LinearLayout, ctx: JSONObject) {
        val ses=ctx.optJSONObject("session")?:JSONObject();val mnv=ses.optString("mnv");fun clean(v:String)=v.trim().takeUnless{it.equals("null",true)||it=="—"}?:""
        val pda=clean(ses.optString("pda_serial"));val expectedStatus=clean(ses.optString("pda_enter_status"));val activeLabor=ctx.optJSONObject("active_labor")
        body.addView(status("ĐANG TRONG PHIÊN",green,Color.rgb(235,248,239)));body.addView(gap(8));body.addView(section("THỜI GIAN & CÔNG VIỆC HIỆN TẠI"));body.addView(details(listOf("Ca" to ses.optString("shift"),"Vào lúc" to formatIso(ses.optString("enter_at")),"Ra lúc" to "Chưa ra ca","Công việc PICK" to pickSummary(ses),"Công việc PACK" to packSummary(ses),"Ghi chú" to dash(ses.optString("resource_note")))));body.addView(gap(9));addPdaIdentity(body,ses);body.addView(gap(8))
        if(activeLabor!=null){body.addView(status("CÒN CÔNG NHẬT ĐANG LÀM",orange,Color.rgb(255,247,230)));body.addView(gap(4));body.addView(info("${activeLabor.optString("labor_type")} • bắt đầu ${formatIso(activeLabor.optString("start_at"))}. Phải hoàn thành công nhật trước khi ra ca."));body.addView(gap(8))}
        addSessionTimeline(body,mnv);body.addView(gap(9));body.addView(primary("THÊM / SỬA CÔNG VIỆC TRONG CA",orange){sessionWorkEditor(ctx)},matchWrap());body.addView(gap(6));if(isAdmin()){body.addView(smallButton("SỬA GIỜ VÀO CA",navy).apply{setOnClickListener{editAttendanceTime(ctx,"enter_at")}},matchWrap());body.addView(gap(8))}
        val exit=primary("RA CA",red){}
        fun doExit(statusNow:String){exit.isEnabled=false;exit.text="ĐANG RA CA...";api.call("session_exit_guarded",JSONObject().put("session_id",ses.optString("session_id")).put("pda_exit_status",statusNow).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"RA CA thất bại");return@runOnUiThread};TopNotice.show(this,"Đã ghi nhận ra ca.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();scheduleAttendanceAutoReset(mnv,employeeLookupGeneration)}}}
        exit.setOnClickListener{
            if(activeLabor!=null){showError("Còn công nhật đang làm. Hoàn thành công nhật trước khi ra ca.");return@setOnClickListener}
            if(pda.isBlank()){AlertDialog.Builder(this).setTitle("Xác nhận RA CA").setMessage("Không còn PDA/công nhật cần xử lý. Xác nhận kết thúc phiên?").setNegativeButton("Hủy",null).setPositiveButton("RA CA"){_,_->doExit("")}.show();return@setOnClickListener}
            val statuses=mutableListOf<String>();val arr=MasterDataCache.resourceOptions(this).optJSONArray("pda_statuses")?:JSONArray();for(i in 0 until arr.length()){val v=clean(arr.optString(i));if(v.isNotBlank()&&!statuses.contains(v))statuses.add(v)};if(expectedStatus.isNotBlank()&&!statuses.contains(expectedStatus))statuses.add(0,expectedStatus);if(statuses.isEmpty()){showError("Không có danh mục tình trạng PDA để đối chiếu.");return@setOnClickListener};val sp=spinner(statuses.toTypedArray());val wrap=column(surface).apply{setPadding(dp(16),dp(6),dp(16),dp(4));addView(txt("Seri PDA: $pda",12f,navy,true));addView(gap(5));addView(txt("Tình trạng khi nhận: ${expectedStatus.ifBlank{"Chưa có"}}",10.5f,muted,true));addView(gap(9));addView(labelled("Tình trạng PDA hiện tại",sp))};AlertDialog.Builder(this).setTitle("Đối chiếu PDA trước khi RA CA").setView(wrap).setNegativeButton("Hủy",null).setPositiveButton("KIỂM TRA & RA CA"){_,_->doExit(sp.selectedItem?.toString().orEmpty())}.show()
        };body.addView(exit,matchWrap())
    }

    private fun renderEnded(body: LinearLayout, ctx: JSONObject) {
        val ses=ctx.optJSONObject("session")?:JSONObject();val mnv=ses.optString("mnv");body.addView(status("ĐÃ RA CA",teal,Color.rgb(232,248,245)));body.addView(gap(8));body.addView(section("PHIÊN HÔM NAY"));body.addView(details(listOf("Ca" to ses.optString("shift"),"Vào lúc" to formatIso(ses.optString("enter_at")),"Ra lúc" to formatIso(ses.optString("exit_at")),"Công việc PICK cuối" to pickSummary(ses),"Công việc PACK cuối" to packSummary(ses))));body.addView(gap(9));addPdaIdentity(body,ses);body.addView(gap(9));addSessionTimeline(body,mnv)
        if(isAdmin()){body.addView(gap(8));body.addView(section("ADMIN / SUPERADMIN"));body.addView(info("Phiên đã kết thúc chỉ ADMIN/SUPERADMIN được sửa dữ liệu. Mọi sửa/xóa đều có audit; xóa RA CA sẽ mở lại phiên để sửa công việc nếu cần."));body.addView(gap(7));body.addView(smallButton("SỬA GIỜ VÀO CA",navy).apply{setOnClickListener{editAttendanceTime(ctx,"enter_at")}},matchWrap());body.addView(gap(6));body.addView(smallButton("SỬA GIỜ RA CA",orange).apply{setOnClickListener{editAttendanceTime(ctx,"exit_at")}},matchWrap());body.addView(gap(6));body.addView(primary("XÓA GHI NHẬN RA CA",red){deleteExitRecord(ctx)},matchWrap())}
    }

    private fun renderEnter(body: LinearLayout, ctx: JSONObject, masters: JSONObject) {
        val e=ctx.optJSONObject("employee")?:JSONObject();val mnv=e.optString("mnv")
        body.addView(section("PHÂN CÔNG TRONG CA"))
        val now=java.time.LocalTime.now(ZoneId.of("Asia/Ho_Chi_Minh"));var shiftValue=when{now.isBefore(java.time.LocalTime.of(8,0))->"Ca 1";now.isBefore(java.time.LocalTime.of(10,0))->"Ca HC";else->"Ca 2"}
        var workValue=when{e.optString("main_position").trim().equals("Pick",true)->"PICK";e.optString("main_position").trim().equals("Pack",true)->"PACK";else->"KHONG"}
        val resourceBox=column(bg);val shiftBox=column(bg);val workBox=column(bg);var rebuildResources:(()->Unit)?=null
        shiftBox.addView(segmentedChoice(listOf("Ca 1" to "Ca 1","Ca HC" to "Ca HC","Ca 2" to "Ca 2"),shiftValue){shiftValue=it;rebuildResources?.invoke()},matchWrap())
        workBox.addView(segmentedChoice(listOf("Không" to "KHONG","Pick" to "PICK","Pack" to "PACK"),workValue){workValue=it;rebuildResources?.invoke()},matchWrap())
        body.addView(labelled("Ca",shiftBox));body.addView(gap(9));body.addView(labelled("Vị trí trong ca",workBox));body.addView(gap(8));body.addView(resourceBox,matchWrap())
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val pickReissue=masters.optJSONArray("user_picks_reissue")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray();val packReissue=masters.optJSONArray("pack_tables_reissue")?:JSONArray()
        var pdaField:AutoCompleteTextView?=null;var selectedPda:JSONObject?=null;var pickSpinner:Spinner?=null;var pickChoices=mutableListOf<Pair<String,Boolean>>();var packSelection:JSONObject?=null
        var allowPickReissue=false;var allowPackReissue=false
        fun renderPick(){
            pdaField=pdaInput(pdas,onSelected={selectedPda=it});resourceBox.addView(labelled("Seri PDA — gõ 5 số cuối",pdaField!!));resourceBox.addView(gap(5));resourceBox.addView(pdaSelectedPanel(pdas,pdaField!!),matchWrap());resourceBox.addView(gap(8))
            val base=mutableListOf<String>();for(i in 0 until picks.length()){val id=picks.optString(i).trim();if(id.isNotBlank()&&!base.contains(id))base.add(id)}
            pickChoices=mutableListOf("" to false);val labels=mutableListOf("Không dùng");sortedByNaturalUser(base){it}.forEach{pickChoices.add(it to false);labels.add(it)}
            if(allowPickReissue){val used=mutableListOf<String>();for(i in 0 until pickReissue.length()){val id=pickReissue.optJSONObject(i)?.optString("id").orEmpty().trim();if(id.isNotBlank()&&!base.contains(id)&&!used.contains(id))used.add(id)};sortedByNaturalUser(used){it}.forEach{pickChoices.add(it to true);labels.add("⚠ $it • ĐÃ DÙNG HÔM NAY")}}
            pickSpinner=spinner(labels.toTypedArray());val userRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL};userRow.addView(pickSpinner!!,LinearLayout.LayoutParams(0,dp(50),1.35f).apply{marginEnd=dp(5)});userRow.addView(compactReissueButton("Phát lại user pick",pickReissue.length()>0&&!allowPickReissue){allowPickReissue=true;rebuildResources?.invoke()},LinearLayout.LayoutParams(0,dp(46),.85f));resourceBox.addView(labelled("User Pick hy1.outbound",userRow))
        }
        fun renderPack(){
            val rows=mutableListOf<JSONObject>();fun addRows(a:JSONArray,duplicate:Boolean){for(i in 0 until a.length()){val o=a.optJSONObject(i)?:continue;val t=o.optString("table").trim();val u=o.optString("user_pack").trim();if(t.isBlank()||u.isBlank())continue;val existing=rows.indexOfFirst{it.optString("table")==t&&it.optString("user_pack")==u};if(existing>=0){if(!duplicate)rows[existing].put("duplicate_user",false);continue};rows.add(JSONObject(o.toString()).put("duplicate_user",duplicate))}};addRows(packs,false);if(allowPackReissue)addRows(packReissue,true)
            val tables=rows.map{it.optString("table")}.filter{it.isNotBlank()}.distinct().sortedWith(Comparator{a,b->naturalUserCompare(a,b)});val tableSp=spinner((if(tables.isEmpty())listOf("Không có bàn Pack khả dụng")else tables).toTypedArray());resourceBox.addView(labelled("Bàn Pack",tableSp));resourceBox.addView(gap(8));val userHost=column(bg);resourceBox.addView(userHost,matchWrap())
            fun renderUsers(){userHost.removeAllViews();packSelection=null;if(tables.isEmpty()){userHost.addView(info("Không có User Pack khả dụng."));return};val table=tables.getOrNull(tableSp.selectedItemPosition).orEmpty();val mapped=sortedByNaturalUser(rows.filter{it.optString("table")==table}){it.optString("user_pack")};val labels=mapped.map{if(it.optBoolean("duplicate_user"))"⚠ ${it.optString("user_pack")} • ĐÃ DÙNG HÔM NAY" else it.optString("user_pack")};val userSp=spinner((if(labels.isEmpty())listOf("Không có User Pack")else labels).toTypedArray());packSelection=mapped.getOrNull(0);userSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){packSelection=mapped.getOrNull(pos)};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};val userRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL};userRow.addView(userSp,LinearLayout.LayoutParams(0,dp(50),1.35f).apply{marginEnd=dp(5)});userRow.addView(compactReissueButton("Phát lại user pack",packReissue.length()>0&&!allowPackReissue){allowPackReissue=true;rebuildResources?.invoke()},LinearLayout.LayoutParams(0,dp(46),.85f));userHost.addView(labelled("User Pack",userRow))}
            tableSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){renderUsers()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};renderUsers()
        }
        rebuildResources={resourceBox.removeAllViews();pdaField=null;selectedPda=null;pickSpinner=null;pickChoices.clear();packSelection=null;when(workValue){"PICK"->renderPick();"PACK"->renderPack();else->Unit}}
        rebuildResources?.invoke();body.addView(gap(12));val enterBtn=primary("VÀO CA",teal){}
        enterBtn.setOnClickListener{
            val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv).put("shift",shiftValue).put("work_choice",workValue)
            if(workValue=="PICK"){
                val p=selectedPda;val expected=if(p==null)"" else p.optString("last5").trim().ifBlank{p.optString("serial").takeLast(5)};if(p==null||pdaField?.text?.toString()?.trim()!=expected){showError("Hãy gõ 5 số cuối và chọn PDA trong danh sách gợi ý.");return@setOnClickListener};payload.put("pda_serial",p.optString("serial")).put("pda_status_at_enter",p.optString("status"));val picked=pickChoices.getOrNull(pickSpinner?.selectedItemPosition?:0)?:("" to false);if(picked.first.isNotBlank())payload.put("user_pick",picked.first);if(picked.second)payload.put("duplicate_user",true).put("resource_note","PHÁT LẠI USER")
            }
            if(workValue=="PACK"){
                val row=packSelection;if(row==null){showError("Chọn Bàn Pack và User Pack hợp lệ.");return@setOnClickListener};payload.put("pack_table",row.optString("table")).put("user_pack",row.optString("user_pack"));if(row.optBoolean("duplicate_user"))payload.put("duplicate_user",true).put("resource_note","PHÁT LẠI USER")
            }
            val actionGeneration=employeeLookupGeneration;enterBtn.isEnabled=false;enterBtn.text="ĐANG VÀO CA...";api.call("enter",payload){r->runOnUiThread{enterBtn.isEnabled=true;enterBtn.text="VÀO CA";if(!r.ok)showError(r.error?:"VÀO CA thất bại")else{TopNotice.show(this,"Đã ghi nhận vào ca.",TopNotice.Kind.SUCCESS);scheduleAttendanceAutoReset(mnv,actionGeneration)}}}
        }
        body.addView(enterBtn,matchWrap())
    }

    private fun laborHome(){
        screenState="LABOR_HOME"
        if(!isAdmin()){simpleMessage("CÔNG NHẬT","Chức năng Công nhật dành cho ADMIN/SUPERADMIN theo phân quyền hiện tại.");return}
        val root=baseRoot("CÔNG NHẬT");val body=body()
        val mnv=mnvInput("Mã nhân viên").apply{setText(initialMnv)};body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(5))
        var busy=false
        fun submit(){
            val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập Mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return
            val local=PdaLocalProjection.employeeContext(this,v)
            if(local!=null){
                if(!local.optBoolean("session_known",true)){
                    renderCachedEmployee(local.optJSONObject("employee")?:JSONObject())
                    TopNotice.show(this,"Đã đọc nhân sự từ PDA • đang đối chiếu phiên/công nhật nền",TopNotice.Kind.INFO)
                    foregroundSync.requestSync();return
                }
                showLaborContext(local,MasterDataCache.snapshot(this)?:JSONObject())
                foregroundSync.requestSync()
                return
            }
            busy=true
            api.call("employee_context",JSONObject().put("mnv",v).put("include_labor",true).put("include_options",false)){r->runOnUiThread{
                busy=false;if(handleAuth(r))return@runOnUiThread
                if(!r.ok){showError(r.error?:"Không kiểm tra được Mã nhân viên");return@runOnUiThread}
                showLaborContext(r.json?:JSONObject(),MasterDataCache.snapshot(this@OperationsActivity)?:JSONObject())
            }}
        }
        bindScannerEnter(mnv){submit()};if(initialMnv.isNotBlank())mnv.post{submit()};attach(root,body);mnv.requestFocus()
    }

    private fun showLaborContext(ctx:JSONObject, masters:JSONObject){
        screenState = "LABOR_CONTEXT"
        val e=ctx.optJSONObject("employee")?:JSONObject();val state=ctx.optString("state");val active=ctx.optJSONObject("active_labor");val root=baseRoot("CÔNG NHẬT");val body=body();body.addView(employeeCard(e));body.addView(gap(10))
        if(state!="ACTIVE"){body.addView(status(if(state=="ENDED")"Mã nhân viên ĐÃ HẾT PHIÊN" else "Mã nhân viên CHƯA VÀO CA",red,Color.rgb(255,238,239)));body.addView(gap(9));body.addView(primary("Mã nhân viên KHÁC",navy){initialMnv="";laborHome()},matchWrap());attach(root,body);return}
        val s=ctx.optJSONObject("session")?:JSONObject();body.addView(details(listOf("Ca" to s.optString("shift"),"Vị trí" to workText(s.optString("work_choice")),"Vào lúc" to formatIso(s.optString("enter_at")))));body.addView(gap(10))
        if(active!=null){body.addView(status("ĐANG LÀM CÔNG NHẬT",green,Color.rgb(235,248,239)));body.addView(gap(8));body.addView(details(listOf("Nội dung" to active.optString("labor_type"),"Bắt đầu" to formatIso(active.optString("start_at")),"Mốc thời gian" to active.optString("time_marker"),"Ghi chú" to dash(active.optString("note")))));body.addView(gap(9));val note=input("Ghi chú khi kết thúc (tùy chọn)",false);body.addView(note,matchWrap());body.addView(gap(9));val finish=primary("HOÀN THÀNH CÔNG NHẬT",red){};finish.setOnClickListener{finish.isEnabled=false;finish.text="ĐANG GHI...";api.call("labor_finish",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("note",note.text.toString())){r->runOnUiThread{finish.isEnabled=true;finish.text="HOÀN THÀNH CÔNG NHẬT";if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không kết thúc được công nhật")else{initialMnv=e.optString("mnv");laborHome()}}}};body.addView(finish,matchWrap())
        }else{
            body.addView(status("CHƯA CÓ CÔNG NHẬT ĐANG LÀM",blue,Color.rgb(237,244,255)));body.addView(gap(9));val types=catalogValues("CÔNG NHẬT_Thông tin công nhật",jsonStrings(masters.optJSONArray("labor_types")));val markers=catalogValues("CÔNG NHẬT_Mốc thời gian",jsonStrings(masters.optJSONArray("time_markers")));val typeSpinner=spinner((if(types.isEmpty())listOf("Khác")else types).toTypedArray());val markerSpinner=spinner((if(markers.isEmpty())listOf("Trong ngày")else markers).toTypedArray());val note=input("Ghi chú (tùy chọn)",false);body.addView(labelled("Thông tin công nhật",typeSpinner));body.addView(gap(8));body.addView(labelled("Mốc thời gian",markerSpinner));body.addView(gap(8));val fixedMain=foldLocal(e.optString("main_position")).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val deduct=CheckBox(this).apply{text="Khấu trừ nhân sự";isChecked=false;setTextColor(ink);textSize=11f};fun updateDeduct(){val fixedLabor=foldLocal(typeSpinner.selectedItem?.toString().orEmpty()).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val blocked=fixedMain||fixedLabor;deduct.isEnabled=!blocked;if(blocked)deduct.isChecked=false;deduct.setTextColor(if(blocked)muted else ink)};typeSpinner.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){updateDeduct()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};updateDeduct();body.addView(deduct,matchWrap());body.addView(gap(6));body.addView(note,matchWrap());body.addView(gap(9));val start=primary("BẮT ĐẦU CÔNG NHẬT",green){};start.setOnClickListener{start.isEnabled=false;start.text="ĐANG GHI...";api.call("labor_start",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("shift",s.optString("shift"))/* S21_LABOR_SHIFT_APPLIED */.put("labor_type",typeSpinner.selectedItem.toString()).put("time_marker",markerSpinner.selectedItem.toString()).put("deduct_staff",deduct.isChecked&&deduct.isEnabled).put("note",note.text.toString())){r->runOnUiThread{start.isEnabled=true;start.text="BẮT ĐẦU CÔNG NHẬT";if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không bắt đầu được công nhật")else{initialMnv=e.optString("mnv");laborHome()}}}};body.addView(start,matchWrap())
        }
        body.addView(gap(9));body.addView(primary("Mã nhân viên KHÁC",navy){initialMnv="";laborHome()},matchWrap());attach(root,body)
    }

    private fun resourceHome(){
        screenState="RESOURCE_HOME"
        val root=baseRoot("TÀI NGUYÊN");val body=body()
        body.addView(info("Quản lý danh mục tài nguyên dùng chung. USER được xem; ADMIN/SUPERADMIN được thêm, sửa, xóa và cập nhật tình trạng."));body.addView(gap(10))
        val cards=listOf(
            Triple("PDA","DANH SÁCH PDA","Seri / tình trạng"),
            Triple("USER_PICK","DANH SÁCH USER PICK","User Pick / tình trạng"),
            Triple("PACK_TABLE","DANH SÁCH BÀN PACK","Bàn Pack / tình trạng"),
            Triple("USER_PACK","DANH SÁCH USER PACK","User Pack / bàn liên kết")
        )
        cards.chunked(2).forEach{pair->
            val row=businessRow(
                businessCard(R.drawable.ic_pp_resource,pair[0].second,pair[0].third){resourceListScreen(pair[0].first,pair[0].second)},
                if(pair.size>1)businessCard(R.drawable.ic_pp_resource,pair[1].second,pair[1].third){resourceListScreen(pair[1].first,pair[1].second)} else Space(this)
            );body.addView(row);body.addView(gap(10))
        }
        attach(root,body)
    }

    private fun resourceListScreen(type:String,title:String){
        screenState="RESOURCE_LIST"
        val root=baseRoot(title);val body=body();val box=column(bg);val selected=linkedSetOf<String>();val checks=mutableListOf<CheckBox>()
        body.addView(info("Danh mục dùng chung. Thay đổi được ghi nhận vào lịch sử; xóa yêu cầu xác thực lại mật khẩu."));body.addView(gap(8))
        if(isAdmin()){val actions=row(bg);actions.addView(smallButton("THÊM",teal).apply{setOnClickListener{resourceEditDialog(type,null,null,null)}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)});actions.addView(smallButton("CHỌN TẤT CẢ",navy).apply{setOnClickListener{checks.forEach{it.isChecked=true}}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3);marginEnd=dp(3)});actions.addView(smallButton("XÓA ĐÃ CHỌN",red).apply{setOnClickListener{deleteResourcesBulk(type,selected.toList(),title)}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)});body.addView(actions,matchWrap());body.addView(gap(8))}
        body.addView(box,matchWrap());box.addView(info("Đang tải danh sách..."))
        api.call("resource_master_list"){r->runOnUiThread{
            box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Không tải được tài nguyên"));return@runOnUiThread}
            val all=r.json?.optJSONArray("resources")?:JSONArray();val catalogs=r.json?.optJSONArray("catalogs")?:JSONArray();val rows=mutableListOf<JSONObject>();for(i in 0 until all.length()){val x=all.optJSONObject(i)?:continue;if(x.optString("resource_type")==type)rows.add(x)}
            if(rows.isEmpty())box.addView(info("Chưa có dữ liệu."))
            rows.forEach{x->val id=x.optString("resource_id");val card=column(surface).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,14);val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL};if(isAdmin()){val c=CheckBox(this@OperationsActivity).apply{isChecked=id in selected;setOnCheckedChangeListener{_,on->if(on)selected.add(id)else selected.remove(id)}};checks.add(c);top.addView(c,size(dp(42),dp(42)))};top.addView(column(surface).apply{addView(txt(id,13.2f,navy,true));addView(txt("Tình trạng: ${x.optString("status_label").ifBlank{"—"}}",10f,if(x.optInt("available")!=0)green else muted,true))},LinearLayout.LayoutParams(0,-2,1f));addView(top,matchWrap());if(isAdmin()){addView(gap(6));val a=row(surface);a.addView(smallButton("SỬA",teal).apply{setOnClickListener{resourceEditDialog(type,x,catalogs,all)}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginEnd=dp(3)});a.addView(smallButton("XÓA",red).apply{setOnClickListener{confirmDeleteResource(type,id,title)}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginStart=dp(3)});addView(a,matchWrap())}};box.addView(card,matchWrap());box.addView(gap(7))}
        }}
        attach(root,body)
    }

    private fun resourceStatusValues(type:String,catalogs:JSONArray?):MutableList<String>{
        val ns=when(type){"PDA"->"DANH SÁCH PDA_Tình trạng";"USER_PICK"->"DANH SÁCH USER PICK_Tình trạng";"PACK_TABLE"->"DANH SÁCH BÀN PACK_Tình trạng";else->"DANH SÁCH USER PACK_Tình trạng"}
        val out=mutableListOf<String>();if(catalogs!=null)for(i in 0 until catalogs.length()){val x=catalogs.optJSONObject(i)?:continue;if(x.optString("namespace")==ns&&x.optString("value").isNotBlank())out.add(x.optString("value"))}
        if(out.isEmpty())out.addAll(catalogValues(ns));return out.distinct().toMutableList()
    }

    private fun resourceEditDialog(type:String,existing:JSONObject?,catalogs:JSONArray?,all:JSONArray?){
        if(!isAdmin())return
        val meta=runCatching{JSONObject(existing?.optString("metadata_json","{}")?:"{}")}.getOrDefault(JSONObject());val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))}
        val id=input("Mã / tên tài nguyên",false).apply{setText(existing?.optString("resource_id").orEmpty());isEnabled=existing==null}
        val statuses=resourceStatusValues(type,catalogs);val statusSp=spinner((if(statuses.isEmpty())listOf("Hoạt động")else statuses).toTypedArray());selectByValue(statusSp,statuses,existing?.optString("status_label").orEmpty())
        val note=input("Ghi chú",false).apply{setText(meta.optString("Ghi chú").ifBlank{meta.optString("note")})}
        val extra1=input(when(type){"PDA"->"5 số cuối Seri";"USER_PICK"->"Số User";"USER_PACK"->"Tên bàn pack";else->""},false)
        val extra2=input(if(type=="USER_PACK")"Nhãn User pack (ví dụ CA 1-...)" else "",false)
        if(type=="PDA")extra1.setText(meta.optString("5 số cuối Seri"));if(type=="USER_PICK")extra1.setText(meta.optString("Số User"));if(type=="USER_PACK"){extra1.setText(meta.optString("Tên bàn pack").ifBlank{meta.optString("pack_table")});extra2.setText(meta.optString("User pack").ifBlank{meta.optString("label")})}
        fun add(l:String,v:View){if(l.isBlank())return;box.addView(txt(l,10.2f,ink,true));box.addView(gap(4));box.addView(v,matchWrap());box.addView(gap(8))}
        add("Mã / tên tài nguyên",id);add("Tình trạng",statusSp);if(type!="PACK_TABLE")add(extra1.hint?.toString().orEmpty(),extra1);if(type=="USER_PACK")add(extra2.hint?.toString().orEmpty(),extra2);add("Ghi chú",note)
        AlertDialog.Builder(this).setTitle(if(existing==null)"Thêm tài nguyên" else "Sửa tài nguyên").setView(ScrollView(this).apply{addView(box)}).setNegativeButton("Hủy",null).setPositiveButton("LƯU"){_,_->
            val key=id.text.toString().trim();if(key.isBlank()){showError("Mã tài nguyên là bắt buộc.");return@setPositiveButton}
            val m=JSONObject().put("Ghi chú",note.text.toString().trim())
            when(type){"PDA"->{val last=extra1.text.toString().trim().ifBlank{key.takeLast(5)};if(last.length!=5||!last.all{it.isDigit()}){showError("5 số cuối Seri phải gồm đúng 5 chữ số.");return@setPositiveButton};m.put("Seri PDA",key).put("5 số cuối Seri",last)};"USER_PICK"->m.put("User Pick",key).put("Số User",extra1.text.toString().trim());"USER_PACK"->{val table=extra1.text.toString().trim();if(table.isBlank()){showError("Tên bàn pack là bắt buộc cho User Pack.");return@setPositiveButton};m.put("Tên bàn pack",table).put("User Pack",key).put("User pack",extra2.text.toString().trim())};"PACK_TABLE"->m.put("Tên bàn pack",key)}
            val p=JSONObject().put("operation","UPSERT").put("resource_type",type).put("resource_id",key).put("status_label",statusSp.selectedItem?.toString().orEmpty()).put("metadata",m).put("idempotency_key",UUID.randomUUID().toString())
            api.call("resource_master_upsert",p){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không lưu được tài nguyên")else{TopNotice.show(this,"Đã cập nhật tài nguyên.",TopNotice.Kind.SUCCESS);resourceListScreen(type,when(type){"PDA"->"DANH SÁCH PDA";"USER_PICK"->"DANH SÁCH USER PICK";"PACK_TABLE"->"DANH SÁCH BÀN PACK";else->"DANH SÁCH USER PACK"})}}}
        }.show()
    }

    private fun deleteResourcesBulk(type:String,ids:List<String>,title:String){
        if(!isAdmin())return;if(ids.isEmpty()){showError("Chọn ít nhất một mục cần xóa.");return}
        AlertDialog.Builder(this).setTitle("Xóa ${ids.size} mục?").setMessage("Tài nguyên đang được sử dụng sẽ bị hệ thống chặn xóa.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa ${ids.size} tài nguyên"){fun next(i:Int){if(i>=ids.size){TopNotice.show(this,"Đã xử lý xóa các mục đã chọn.",TopNotice.Kind.SUCCESS);resourceListScreen(type,title);return};api.call("resource_master_delete",JSONObject().put("operation","DELETE").put("resource_type",type).put("resource_id",ids[i]).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError("${ids[i]}: ${r.error?:"Không xóa được"}");return@runOnUiThread};next(i+1)}}};next(0)}}.show()
    }

    private fun confirmDeleteResource(type:String,id:String,title:String){
        if(!isAdmin())return
        AlertDialog.Builder(this).setTitle("Xóa tài nguyên?").setMessage("Xóa $id khỏi $title?").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa tài nguyên $id"){api.call("resource_master_delete",JSONObject().put("operation","DELETE").put("resource_type",type).put("resource_id",id).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không xóa được tài nguyên")else{TopNotice.show(this,"Đã xóa tài nguyên.",TopNotice.Kind.SUCCESS);resourceListScreen(type,title)}}}}}.show()
    }

    private fun staffScreen(){
        module="STAFF";screenState="STAFF"
        val root=baseRoot("NHÂN SỰ");val body=body();val selected=linkedSetOf<String>();val checks=mutableListOf<CheckBox>();val searchRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL};val q=input("Tìm mã nhân viên, họ tên hoặc số điện thoại",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH}
        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(50),1f));if(isAdmin()){searchRow.addView(gap(8));searchRow.addView(iconActionButton(R.drawable.ic_pp_add,teal,"Thêm nhân sự"){staffEditor(null)},size(dp(50),dp(50)))};body.addView(searchRow,matchWrap())
        if(isSuper()){body.addView(gap(7));val bulk=row(bg);bulk.addView(smallButton("CHỌN TẤT CẢ",navy).apply{setOnClickListener{checks.forEach{it.isChecked=true}}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)});bulk.addView(smallButton("XÓA ĐÃ CHỌN",red).apply{setOnClickListener{deleteStaffBulk(selected.toList())}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)});body.addView(bulk,matchWrap())}
        body.addView(gap(10));val box=column(bg);body.addView(box,matchWrap());var pageSize=60
        fun render(query:String){box.removeAllViews();checks.clear();val clean=query.trim();val limit=if(clean.isBlank())pageSize else 180;val arr=MasterDataCache.searchStaff(this,clean,limit)
            for(i in 0 until arr.length()){val e=arr.optJSONObject(i)?:continue;val id=e.optString("mnv");val card=column(surface).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,18);val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL};if(isSuper()){val c=CheckBox(this@OperationsActivity).apply{isChecked=id in selected;setOnCheckedChangeListener{_,on->if(on)selected.add(id)else selected.remove(id)}};checks.add(c);top.addView(c,size(dp(42),dp(42)))};top.addView(column(surface).apply{addView(txt(e.optString("full_name"),14f,ink,true));addView(txt("Mã nhân viên $id • ${dash(e.optString("main_position"))}",10.7f,navy,true));addView(txt("${dash(e.optString("supplier"))} • ${dash(e.optString("department"))} • ${dash(e.optString("site"))}",9.8f,muted,false))},LinearLayout.LayoutParams(0,-2,1f));if(isAdmin()){top.addView(iconActionButton(R.drawable.ic_pp_edit,teal,"Sửa"){staffEditor(e)},size(dp(38),dp(38)));if(isSuper()){top.addView(gap(4));top.addView(iconActionButton(R.drawable.ic_pp_delete,red,"Xóa"){confirmDeleteStaff(e)},size(dp(38),dp(38)))}};addView(top,matchWrap())};box.addView(card,matchWrap());box.addView(gap(8))}
            if(arr.length()==0)box.addView(info("Không có nhân sự phù hợp."));if(clean.isBlank()&&arr.length()>=pageSize&&pageSize<MasterDataCache.staffCount(this)){box.addView(primary("XEM THÊM",teal){pageSize+=60;render("")},matchWrap())}}
        q.addTextChangedListener(object:TextWatcher{override fun beforeTextChanged(v:CharSequence?,st:Int,c:Int,a:Int)=Unit;override fun onTextChanged(v:CharSequence?,st:Int,b:Int,c:Int){render(v?.toString().orEmpty())};override fun afterTextChanged(v:Editable?)=Unit});q.setOnEditorActionListener{_,_,_->render(q.text.toString());true};render("");attach(root,body)
    }

    private fun staffEditor(existing:JSONObject?){
        if(!isAdmin())return
        if(existing!=null){val code=input("Mã xác nhận 4 số",true).apply{inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789")};AlertDialog.Builder(this).setTitle("Xác nhận quyền sửa").setMessage("Nhập mã 4 số theo giờ Việt Nam hiện tại (HHmm). Ví dụ 07:42 → 0742.").setView(code).setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->val expected=java.time.LocalTime.now(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("HHmm"));if(code.text.toString()!=expected){showError("Mã xác nhận không đúng.")}else staffEditorUnlocked(existing)}.show();return}
        staffEditorUnlocked(null)
    }

    private fun staffEditorUnlocked(existing:JSONObject?){
        val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};val mnv=mnvInput("Mã nhân viên").apply{setText(existing?.optString("mnv").orEmpty());isEnabled=existing==null};val full=input("Họ và tên",false).apply{setText(existing?.optString("full_name").orEmpty())};val phone=input("Số điện thoại",false).apply{setText(existing?.optString("phone").orEmpty());inputType=InputType.TYPE_CLASS_PHONE;keyListener=DigitsKeyListener.getInstance("0123456789")}
        val pos=catalogSpinner("DANH SÁCH NHÂN SỰ_Vị trí chính",existing?.optString("main_position").orEmpty(),true);val supplier=catalogSpinner("DANH SÁCH NHÂN SỰ_Nhà cung cấp",existing?.optString("supplier").orEmpty(),true);val department=catalogSpinner("DANH SÁCH NHÂN SỰ_Bộ phận",existing?.optString("department").orEmpty(),true);val site=catalogSpinner("DANH SÁCH NHÂN SỰ_Site",existing?.optString("site").orEmpty(),true);val warehouse=catalogSpinner("DANH SÁCH NHÂN SỰ_Kho",existing?.optString("warehouse").orEmpty(),true)
        val startDate=input("Chọn ngày bắt đầu",false).apply{setText(existing?.optString("start_date").orEmpty());isFocusable=false;isClickable=true};startDate.setOnClickListener{val now=java.time.LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh"));val parts=startDate.text.toString().split("/");val d=parts.getOrNull(0)?.toIntOrNull()?:now.dayOfMonth;val m=(parts.getOrNull(1)?.toIntOrNull()?:now.monthValue)-1;val y=parts.getOrNull(2)?.toIntOrNull()?:now.year;android.app.DatePickerDialog(this,{_,yy,mm,dd->startDate.setText(String.format(java.util.Locale.US,"%02d/%02d/%04d",dd,mm+1,yy))},y,m,d).show()};val note=input("Ghi chú",false).apply{setText(existing?.optString("note").orEmpty())}
        fun addField(label:String,view:View){box.addView(txt(label,10.2f,ink,true));box.addView(gap(4));box.addView(view,matchWrap());box.addView(gap(8))};addField("Mã nhân viên",mnv);addField("Họ và tên",full);addField("Số điện thoại",phone);addField("Vị trí chính",pos);addField("Nhà cung cấp",supplier);addField("Bộ phận",department);addField("Site",site);addField("Kho",warehouse);addField("Ngày bắt đầu làm việc",startDate);addField("Ghi chú",note)
        val dialog=AlertDialog.Builder(this).setTitle(if(existing==null)"Thêm nhân sự" else "Sửa nhân sự").setView(ScrollView(this).apply{addView(box)}).setNegativeButton("Hủy",null).setPositiveButton("LƯU",null).create();dialog.setOnShowListener{dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener{val id=mnv.text.toString().trim();val nm=full.text.toString().trim();val ph=phone.text.toString().trim();val sd=startDate.text.toString().trim();if(id.isBlank()||!id.all{it.isDigit()}){showError("Mã nhân viên là bắt buộc và chỉ gồm chữ số.");return@setOnClickListener};if(nm.isBlank()){showError("Họ và tên là bắt buộc.");return@setOnClickListener};if(!Regex("^0[0-9]{9}$").matches(ph)){showError("Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0.");return@setOnClickListener};if(!Regex("^(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/([0-9]{4})$").matches(sd)){showError("Ngày bắt đầu làm việc chưa hợp lệ.");return@setOnClickListener};val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id).put("full_name",nm).put("phone",ph).put("main_position",catalogSelection(pos)).put("supplier",catalogSelection(supplier)).put("department",catalogSelection(department)).put("site",catalogSelection(site)).put("warehouse",catalogSelection(warehouse)).put("start_date",sd).put("note",note.text.toString());api.call("staff_upsert",payload){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không lưu được nhân sự")else{dialog.dismiss();reloadMaster{TopNotice.show(this,"Đã lưu nhân sự.",TopNotice.Kind.SUCCESS);staffScreen()}}}}}};dialog.show()
    }

    private fun deleteStaffBulk(ids:List<String>){
        if(!isSuper()){showError("Chỉ Quản trị cao nhất được xóa nhân sự.");return};if(ids.isEmpty()){showError("Chọn ít nhất một nhân sự cần xóa.");return}
        AlertDialog.Builder(this).setTitle("Xóa ${ids.size} nhân sự?").setMessage("Nhân sự đang có phiên hoạt động sẽ bị hệ thống chặn xóa. Lịch sử nghiệp vụ vẫn được giữ.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa ${ids.size} nhân sự"){fun next(i:Int){if(i>=ids.size){reloadMaster{TopNotice.show(this,"Đã xử lý xóa các nhân sự đã chọn.",TopNotice.Kind.SUCCESS);staffScreen()};return};api.call("staff_delete",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",ids[i])){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError("${ids[i]}: ${r.error?:"Không xóa được"}");return@runOnUiThread};next(i+1)}}};next(0)}}.show()
    }

    private fun confirmDeleteStaff(employee:JSONObject){
        if(!isSuper()){showError("Chỉ Quản trị cao nhất được xóa nhân sự.");return}
        val id=employee.optString("mnv");AlertDialog.Builder(this).setTitle("Xóa nhân sự?").setMessage("Xóa Mã nhân viên $id • ${employee.optString("full_name")}? Lịch sử nghiệp vụ vẫn được giữ.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa nhân sự $id"){api.call("staff_delete",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id)){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không xóa được nhân sự")else reloadMaster{TopNotice.show(this,"Đã xóa nhân sự.",TopNotice.Kind.SUCCESS);staffScreen()}}}}}.show()
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
        val root=baseRoot("DANH SÁCH");val body=body();val q=scanSearchInput("Scan / Nhập mã nhân viên, họ tên để tìm kiếm");body.addView(q,matchWrap());body.addView(gap(8));val buttons=row(bg);val sessions=smallButton("PHIÊN HÔM NAY",blue);val labor=smallButton("CÔNG NHẬT",green);val staff=smallButton("NHÂN SỰ",navy);buttons.addView(sessions,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginEnd=dp(3)});buttons.addView(labor,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3);marginEnd=dp(3)});buttons.addView(staff,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3)});body.addView(buttons,matchWrap());body.addView(gap(9));val box=column(bg);body.addView(box,matchWrap())
        fun loadSessions(){box.removeAllViews();box.addView(txt("Đang tải...",10.5f,muted,false));api.call("list_sessions",JSONObject().put("query",q.text.toString())){r->runOnUiThread{box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Lỗi"));return@runOnUiThread};val a=r.json?.optJSONArray("items")?:JSONArray();if(a.length()==0)box.addView(info("Chưa có phiên phù hợp."));for(i in 0 until a.length()){val s=a.optJSONObject(i)?:continue;val e=s.optJSONObject("employee_snapshot")?:JSONObject();box.addView(listCard("${s.optString("mnv")} • ${e.optString("full_name")}","${s.optString("state")} • ${s.optString("shift")} • ${workText(s.optString("work_choice"))}\nPDA ${dash(s.optString("pda_serial"))} • Pick ${dash(s.optString("user_pick"))} • Pack ${dash(s.optString("pack_table"))}"));box.addView(gap(6))}}}}
        fun loadLabor(){box.removeAllViews();if(!isAdmin()){box.addView(info("Công nhật chỉ hiển thị cho ADMIN/SUPERADMIN."));return};api.call("list_labor"){r->runOnUiThread{box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Lỗi"));return@runOnUiThread};val a=r.json?.optJSONArray("items")?:JSONArray();if(a.length()==0)box.addView(info("Chưa có công nhật hôm nay."));for(i in 0 until a.length()){val l=a.optJSONObject(i)?:continue;val e=l.optJSONObject("employee_snapshot")?:JSONObject();box.addView(listCard("${l.optString("mnv")} • ${e.optString("full_name")}","${l.optString("state")} • ${l.optString("labor_type")}\n${formatIso(l.optString("start_at"))} → ${formatIso(l.optString("end_at"))}"));box.addView(gap(6))}}}}
        fun searchStaff(){val query=q.text.toString().trim();box.removeAllViews();if(query.length<2){box.addView(info("Nhập ít nhất 2 ký tự để tìm nhân sự."));return};val a=MasterDataCache.searchStaff(this,query);for(i in 0 until a.length()){val e=a.optJSONObject(i)?:continue;box.addView(listCard("${e.optString("mnv")} • ${e.optString("full_name")}","${e.optString("main_position")} • ${e.optString("supplier")} • ${e.optString("department")}"));box.addView(gap(6))};if(a.length()==0)box.addView(info("Không tìm thấy nhân sự phù hợp."))}
        sessions.setOnClickListener{loadSessions()};labor.setOnClickListener{loadLabor()};staff.setOnClickListener{searchStaff()};q.setOnEditorActionListener{_,_,_->searchStaff();true};loadSessions();attach(root,body)
    }

    private fun reportDateLabel(iso:String):String=runCatching{
        java.time.LocalDate.parse(iso).format(java.time.format.DateTimeFormatter.ofPattern("dd/MM/yyyy"))
    }.getOrDefault(iso)

    // S34C_SITE1291_LOCAL_REPORT: manpower is derived from the canonical day event snapshot.
    // A person counts on the entry business date as soon as ATTENDANCE_ENTER exists; ATTENDANCE_EXIT is not required.
    // S36_PERF_HISTORY_REPORT_SERVICE: selected-date cached aggregation; no full-day parse on UI thread.
    private fun reportScreen(){
        module="BUSINESS";screenState="REPORT"
        val root=baseRoot("BÁO CÁO NHÂN SỰ");val body=column(bg).apply{setPadding(dp(3),dp(6),dp(3),dp(42))}
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày"))
        var selectedDate=operationalStore.businessDate()
        val dateButton=Button(this).apply{text=runCatching{java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(selectedDate);textSize=12f;isAllCaps=false;background=outlineBg(surface,14);setTextColor(ink)}
        val controls=row(bg).apply{gravity=Gravity.CENTER_VERTICAL;addView(period,LinearLayout.LayoutParams(0,dp(50),1f).apply{marginEnd=dp(5)});addView(dateButton,LinearLayout.LayoutParams(0,dp(50),1f).apply{marginStart=dp(5)})}
        body.addView(section("Phạm vi báo cáo"));body.addView(controls,matchWrap());body.addView(gap(7))
        val box=column(bg);body.addView(box,matchWrap())
        fun fold(v:String)=java.text.Normalizer.normalize(v,java.text.Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"),"").uppercase().trim()
        fun site1291(v:String):Boolean{val x=fold(v);return x=="1291"||x=="SITE 1291"||Regex("(^|[^0-9])1291([^0-9]|$)").containsMatchIn(x)}
        fun shiftBucket(v:String):String{val x=fold(v).replace(Regex("\\s+")," ");return when{x=="CA 1"||x=="CA1"||x=="1"->"CA1";x=="CA HC"||x=="CAHC"||x=="HC"||x.contains("HANH CHINH")->"HC";x=="CA 2"||x=="CA2"||x=="2"->"CA2";else->x}}
        fun supplierCode(raw:String):String{val x=fold(raw);return when{x=="INHOUSE"||x=="IH"->"IH";x=="NGUON LUC VIET"||x=="NLV"->"NLV";x=="VIET WORK"||x=="VW"->"VW";x=="MAN POWER"||x=="MP"->"MP";x=="MEGA LINK"||x=="MGL"->"MGL";x=="HA GIA PHAT"||x=="HGP"->"HGP";x=="HOA ANH DAO"||x=="HAD"->"HAD";else->raw.trim().ifBlank{"Khác"}}}
        fun reportPosition(emp:JSONObject,work:String):String{val p=fold(emp.optString("main_position"));val d=fold(emp.optString("department"));return when{p=="TRUONG NHOM"->"Trưởng nhóm";p=="CHUYEN VIEN"->"Chuyên viên";p=="TO TRUONG"->"Tổ trưởng";p.contains("DIEU PHOI")&&d.contains("PACK")->"Điều phối khu pack";p.contains("DIEU PHOI")&&(d.contains("CHO XUAT")||d.contains("GIAO VAN")||d.contains("OUTBOUND"))->"Điều phối khu chờ xuất";p.contains("KEO HANG")->"Kéo hàng";p=="5S"||p.contains(" 5S")->"5S";p.contains("PHUC LONG")->"Phúc Long";fold(work)=="PICK"||p.contains("PICK")->"Picker";fold(work)=="PACK"||p.contains("PACK")->"Packer";else->emp.optString("main_position").ifBlank{"Khác"}}}
        fun tenureLabel(emp:JSONObject,date:String):String{val raw=emp.optString("start_date").trim();if(raw.isBlank())return "Nhân sự cũ";val started=runCatching{if(raw.matches(Regex("\\d{2}/\\d{2}/\\d{4}")))java.time.LocalDate.parse(raw,DateTimeFormatter.ofPattern("dd/MM/yyyy"))else java.time.LocalDate.parse(raw.take(10))}.getOrNull()?:return "Nhân sự cũ";val target=runCatching{java.time.LocalDate.parse(date)}.getOrNull()?:return "Nhân sự cũ";return if(java.time.temporal.ChronoUnit.DAYS.between(started,target)<=30)"Nhân sự mới" else "Nhân sự cũ"}
        data class Entry(val mnv:String,val shift:String,val work:String,val emp:JSONObject)
        var cachedDate="";var cachedEntries:List<Entry> = emptyList();var loadSerial=0
        fun makeGrid(rows:List<Entry>,kind:String,date:String):JSONObject{
            val columns=listOf("IH","NLV","VW","MP","MGL","HGP","HAD").filter{c->rows.any{supplierCode(it.emp.optString("supplier"))==c}}
            val rowOrder=if(kind=="position")listOf("Trưởng nhóm","Chuyên viên","Tổ trưởng","Điều phối khu pack","Điều phối khu chờ xuất","Kéo hàng","5S","Picker","Packer","Phúc Long","Khác") else listOf("Nhân sự mới","Nhân sự cũ")
            val values=LinkedHashMap<String,MutableMap<String,Int>>();rowOrder.forEach{values[it]=LinkedHashMap()}
            rows.forEach{r->val label=if(kind=="position")reportPosition(r.emp,r.work) else tenureLabel(r.emp,date);val key=if(values.containsKey(label))label else if(kind=="position")"Khác" else label;val sup=supplierCode(r.emp.optString("supplier"));values.getOrPut(key){LinkedHashMap()}[sup]=(values[key]?.get(sup)?:0)+1}
            val outRows=JSONArray();rowOrder.forEach{label->val counts=JSONObject();var total=0;columns.forEach{c->val n=values[label]?.get(c)?:0;counts.put(c,n);total+=n};if(total>0||kind!="position")outRows.put(JSONObject().put(if(kind=="position")"position" else "label",label).put("counts",counts).put("total",total))};val totals=JSONObject();var grand=0;columns.forEach{c->val n=rowOrder.sumOf{values[it]?.get(c)?:0};totals.put(c,n);grand+=n};return JSONObject().put("columns",JSONArray(columns)).put("rows",outRows).put("totals",totals).put("total",grand)
        }
        fun renderCached(){
            box.removeAllViews();if(cachedDate!=selectedDate){box.addView(info("Đang đọc snapshot $selectedDate từ bộ nhớ PDA…"));return}
            val selected=cachedEntries.filter{when(period.selectedItemPosition){0->shiftBucket(it.shift) in setOf("CA1","HC");1->shiftBucket(it.shift)=="CA2";else->true}}
            val shown=runCatching{java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(selectedDate)
            box.addView(info("Site 1291 • Ngày báo cáo $shown • ${selected.size} nhân sự vào ca • Nhà thầu: IH / NLV / VW / MP / MGL / HGP / HAD"));box.addView(gap(5))
            box.addView(s34ReportGrid("",makeGrid(selected,"position",selectedDate),"Vị trí","position"));box.addView(gap(4));box.addView(s34ReportGrid("",makeGrid(selected,"tenure",selectedDate),"Thâm niên","label"))
            if(cachedEntries.isEmpty())box.addView(info("Chưa có snapshot ngày đã chọn trên PDA. Chọn ngày khác hoặc đồng bộ để tải dữ liệu canonical."))
        }
        fun loadDate(){
            val serial=++loadSerial;cachedDate="";box.removeAllViews();box.addView(info("Đang đọc báo cáo $selectedDate…"))
            Thread{
                val out=LinkedHashMap<String,Entry>();val day=operationalStore.loadDay(selectedDate);val events=day?.optJSONArray("events")?:JSONArray()
                for(i in 0 until events.length()){
                    val e=events.optJSONObject(i)?:continue;if(e.optString("event_type").uppercase()!="ATTENDANCE_ENTER")continue
                    val p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val after=p.optJSONObject("after");val snap=p.optJSONObject("employee_snapshot")?:after?.optJSONObject("employee_snapshot")
                    val mnv=e.optString("mnv").ifBlank{p.optString("mnv")}.ifBlank{after?.optString("mnv").orEmpty()}.ifBlank{snap?.optString("mnv").orEmpty()};if(mnv.isBlank())continue
                    val emp=MasterDataCache.employee(this,mnv)?:snap?:JSONObject();if(!site1291(emp.optString("site")))continue
                    val shift=e.optString("shift").ifBlank{p.optString("shift")}.ifBlank{after?.optString("shift").orEmpty()};val work=e.optString("work_choice").ifBlank{p.optString("work_choice")}.ifBlank{after?.optString("work_choice").orEmpty()}
                    val key=e.optString("entity_id").ifBlank{e.optString("session_id")}.ifBlank{e.optString("event_id")}.ifBlank{"$mnv|$shift|$i"};out[key]=Entry(mnv,shift,work,emp)
                }
                runOnUiThread{if(serial==loadSerial&&screenState=="REPORT"){cachedDate=selectedDate;cachedEntries=out.values.toList();renderCached()}}
            }.start()
        }
        dateButton.setOnClickListener{
            val d=runCatching{java.time.LocalDate.parse(selectedDate)}.getOrDefault(java.time.LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")))
            android.app.DatePickerDialog(this,{_,y,m,day->selectedDate=java.time.LocalDate.of(y,m+1,day).toString();dateButton.text=java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"));loadDate()},d.year,d.monthValue-1,d.dayOfMonth).show()
        }
        period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){if(cachedDate==selectedDate)renderCached()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit}
        attach(root,body);loadDate()
    }

    private fun reportTable(title:String,data:JSONObject?,firstTitle:String,rowKey:String,highlightPhuc:Boolean):View{
        val outer=column(surface).apply{setPadding(0,0,0,0);setBackgroundColor(surface)}
        if(title.isNotBlank())outer.addView(txt(title,10.2f,navy,true).apply{setPadding(dp(2),dp(2),0,dp(3))})
        if(data==null){outer.addView(txt("Chưa có dữ liệu",9.4f,muted,false));return outer}
        val columns=jsonStrings(data.optJSONArray("columns"))
        val rows=data.optJSONArray("rows")?:JSONArray()
        val table=TableLayout(this).apply{isStretchAllColumns=false;isShrinkAllColumns=false}
        val header=TableRow(this)
        header.addView(reportFixedCell(firstTitle,true,true,false),TableRow.LayoutParams(dp(126),-2))
        columns.forEach{header.addView(reportFixedCell(reportColumnLabel(it),true,false,false),TableRow.LayoutParams(dp(if(it=="IH")44 else 40),-2))}
        header.addView(reportFixedCell("Tổng",true,false,true),TableRow.LayoutParams(dp(42),-2));table.addView(header)
        for(i in 0 until rows.length()){
            val item=rows.optJSONObject(i)?:continue
            val label=item.optString(rowKey)
            val tr=TableRow(this)
            tr.addView(reportFixedCell(label,false,true,highlightPhuc&&label=="Phúc Long"),TableRow.LayoutParams(dp(126),-2))
            val counts=item.optJSONObject("counts")?:JSONObject()
            columns.forEach{c->tr.addView(reportFixedCell(counts.optInt(c).toString(),false,false,highlightPhuc&&label=="Phúc Long"),TableRow.LayoutParams(dp(if(c=="IH")44 else 40),-1))}
            tr.addView(reportFixedCell(item.optInt("total").toString(),false,false,highlightPhuc&&label=="Phúc Long",true),TableRow.LayoutParams(dp(42),-1));table.addView(tr)
        }
        val totals=data.optJSONObject("totals")
        if(totals!=null){
            val tr=TableRow(this)
            tr.addView(reportFixedCell("Tổng",true,true,false),TableRow.LayoutParams(dp(126),-2))
            columns.forEach{c->tr.addView(reportFixedCell(totals.optInt(c).toString(),true,false,false),TableRow.LayoutParams(dp(if(c=="IH")44 else 40),-1))}
            tr.addView(reportFixedCell(data.optInt("total").toString(),true,false,true),TableRow.LayoutParams(dp(42),-1));table.addView(tr)
        }
        outer.addView(HorizontalScrollView(this).apply{isHorizontalScrollBarEnabled=true;isFillViewport=false;addView(table,ViewGroup.LayoutParams(-2,-2))},matchWrap())
        return outer
    }

    private fun reportColumnLabel(v:String)=if(v=="IH")"Inhouse" else v
    private fun reportFixedCell(v:String,header:Boolean=false,first:Boolean=false,highlight:Boolean=false,total:Boolean=false)=TextView(this).apply{
        text=v;textSize=if(header)8.0f else 8.3f;setTextColor(if(header||total)navy else ink)
        typeface=if(header||first||total)Typeface.DEFAULT_BOLD else Typeface.DEFAULT
        gravity=if(first)Gravity.START or Gravity.CENTER_VERTICAL else Gravity.CENTER
        setPadding(dp(if(first)5 else 2),dp(4),dp(2),dp(4));maxLines=if(first)3 else 2
        background=GradientDrawable().apply{
            setColor(when{highlight->Color.rgb(246,249,82);header||total->Color.rgb(226,238,244);else->Color.WHITE})
            setStroke(dp(1),Color.rgb(105,118,126))
        }
    }

    // S32_LOCAL_HISTORY_FLUSH_FIX: History is local-first and never depends on remote ACK to exist.
    // S34D_COMPILE_FIXES: compact renderer owned by the Site 1291 local report.
    private fun s34ReportGrid(title:String,data:JSONObject?,firstTitle:String,rowKey:String):View{
        val wrap=column(surface).apply{setPadding(dp(1),dp(2),dp(1),dp(2));setBackgroundColor(surface)}
        if(title.isNotBlank())wrap.addView(txt(title,11f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(3))})
        if(data==null){wrap.addView(txt("Chưa có dữ liệu",10f,muted,false));return wrap}
        val cols=jsonStrings(data.optJSONArray("columns"));val rows=data.optJSONArray("rows")?:JSONArray()
        val table=TableLayout(this).apply{isStretchAllColumns=true;isShrinkAllColumns=true}
        fun cell(v:String,bold:Boolean=false,header:Boolean=false)=TextView(this).apply{
            text=v;textSize=if(header)8.2f else 8.5f;setTextColor(if(header)navy else ink);typeface=if(bold)Typeface.DEFAULT_BOLD else Typeface.DEFAULT;gravity=Gravity.CENTER;setPadding(dp(1),dp(3),dp(1),dp(3));maxLines=3;background=GradientDrawable().apply{setColor(if(header)Color.rgb(232,241,246) else Color.WHITE)}
        }
        val hr=TableRow(this);hr.addView(cell(firstTitle,true,true));cols.forEach{hr.addView(cell(it,true,true))};hr.addView(cell("Tổng",true,true));table.addView(hr)
        for(i in 0 until rows.length()){
            val row=rows.optJSONObject(i)?:continue;val tr=TableRow(this);tr.addView(cell(row.optString(rowKey),true));val counts=row.optJSONObject("counts")?:JSONObject();cols.forEach{c->val n=counts.optInt(c);tr.addView(cell(if(n==0)"" else n.toString()))};val total=row.optInt("total");tr.addView(cell(if(total==0)"" else total.toString(),true));table.addView(tr)
        }
        val totals=data.optJSONObject("totals")
        if(totals!=null){val tr=TableRow(this);tr.addView(cell("Tổng",true,true));cols.forEach{c->val n=totals.optInt(c);tr.addView(cell(if(n==0)"" else n.toString(),true,true))};val total=data.optInt("total");tr.addView(cell(if(total==0)"" else total.toString(),true,true));table.addView(tr)}
        wrap.addView(table,matchWrap());return wrap
    }

    // S36_PERF_HISTORY_REPORT_SERVICE: bounded background canonical refresh.
    private fun refreshHistoryCanonical(){
        if(historySyncInFlight)return
        val now=System.currentTimeMillis();if(now-historyLastCanonicalRefreshAt<60_000L)return
        val before=operationalStore.revisions().toString()
        historySyncInFlight=true
        Thread{
            val ok=runCatching{M2BackgroundSync.catchUp(applicationContext)}.getOrDefault(false)
            val changed=ok&&before!=operationalStore.revisions().toString()
            runOnUiThread{
                historySyncInFlight=false;historyLastCanonicalRefreshAt=System.currentTimeMillis()
                if(changed&&screenState=="HISTORY")historyScreen()
            }
        }.start()
    }

    // S36_PERF_HISTORY_REPORT_SERVICE: selected-date history, bounded global search, pagination and Service telemetry.
    // S36B_COMPILE_HOTFIX
    private fun historyScreen(){
        module="HISTORY";screenState="HISTORY";historyDetailMnv="";historyDetailName=""
        // S52_BETA46_SUPERADMIN_HISTORY_DELETE: SUPERADMIN bulk logical delete with immutable tombstone audit.
        if(isSuper())android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({flushDeferredHistoryDeletes()},500L)
        val root=baseRoot("LỊCH SỬ");val body=body();var selectedDate=operationalStore.businessDate();var filter="ALL";val pageSize=100;var pageStart=0;var query=""
        val hiddenHistoryIds=(getSharedPreferences("pp_history_delete_ui",MODE_PRIVATE).getStringSet("hidden_ids",emptySet())?:emptySet()).toMutableSet()
        val selectedHistoryIds=linkedSetOf<String>();val currentPageDeleteIds=linkedSetOf<String>();val pageChecks=mutableListOf<CheckBox>()
        val q=input("Tìm MNV, họ tên, nghiệp vụ, người xử lý",false).apply{setSingleLine(true)};val dateButton=Button(this).apply{text=runCatching{java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(selectedDate);textSize=11f;isAllCaps=false;background=outlineBg(surface,14);setTextColor(ink)}
        val searchRow=row(bg).apply{addView(q,LinearLayout.LayoutParams(0,dp(50),1f).apply{marginEnd=dp(5)});addView(dateButton,size(dp(112),dp(50)))};body.addView(searchRow,matchWrap());body.addView(gap(7))
        val metrics=row(bg);val allBtn=metric("Tổng","0",navy);val pendingBtn=metric("Chờ","0",Color.rgb(217,119,6));val failBtn=metric("Cần xử lí","0",red);metrics.addView(allBtn,LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)});metrics.addView(pendingBtn,LinearLayout.LayoutParams(0,-2,1f).apply{setMargins(dp(2),0,dp(2),0)});metrics.addView(failBtn,LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)});body.addView(metrics,matchWrap());body.addView(gap(7))
        val selectionBox=column(bg)
        val selectionCount=txt("Đã chọn 0 lịch sử",10f,muted,true)
        fun updateSelectedCount(){selectionCount.text="Đã chọn ${selectedHistoryIds.size} lịch sử"}
        if(isSuper()){
            selectionBox.addView(gap(6));selectionBox.addView(selectionCount)
            val choose=row(bg);val selectPage=smallButton("CHỌN TRANG",navy);val clear=smallButton("BỎ CHỌN",muted)
            choose.addView(selectPage,LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)});choose.addView(clear,LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)});selectionBox.addView(gap(5));selectionBox.addView(choose,matchWrap())
            val deleteSelected=smallButton("XÓA ĐÃ CHỌN",red);selectionBox.addView(gap(5));selectionBox.addView(deleteSelected,matchWrap());selectionBox.addView(gap(8))
            selectPage.setOnClickListener{selectedHistoryIds.addAll(currentPageDeleteIds);pageChecks.forEach{it.isChecked=true};updateSelectedCount()}
            clear.setOnClickListener{selectedHistoryIds.clear();pageChecks.forEach{it.isChecked=false};updateSelectedCount()}
            deleteSelected.setOnClickListener{deleteHistoryBulk(selectedHistoryIds.toList())}
            body.addView(selectionBox,matchWrap())
        }
        val box=column(bg);body.addView(box,matchWrap())
        fun friendly(type:String,label:String):String=when(type.uppercase()){ "ATTENDANCE_ENTER","ENTER"->"Vào ca";"ATTENDANCE_EXIT","EXIT"->"Ra ca";"RESOURCE_CHANGE"->"Đổi tài nguyên";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"ADMIN_AUDIT"->"Thao tác quản trị";"MASTER_STAFF_UPSERT"->"Cập nhật nhân sự";"MASTER_STAFF_DELETE"->"Xóa nhân sự";"ACCOUNT_UPSERT"->"Tạo / sửa tài khoản";"ACCOUNT_STATUS"->"Đổi trạng thái tài khoản";"ACCOUNT_EMAIL"->"Đổi email tài khoản";"ACCOUNT_PASSWORD"->"Đổi mật khẩu";else->label.ifBlank{type.ifBlank{"Thao tác"}} }
        fun statusOf(e:JSONObject):String{val s=e.optString("local_status").uppercase();return when{s in setOf("REJECTED","REVIEW_REQUIRED","CONFLICT","FAILED","ERROR")->"FAILED";s in setOf("LOCAL_PENDING","PENDING","RETRY","OFFLINE_PROVISIONAL")->"PENDING";else->"SYNCED"}}
        fun eventDate(e:JSONObject,fallback:String):String=e.optString("business_date").ifBlank{e.optString("cache_business_date")}.ifBlank{runCatching{java.time.Instant.parse(e.optString("at_iso").ifBlank{e.optString("at")}).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toLocalDate().toString()}.getOrDefault(fallback)}
        fun scanDate(date:String,needle:String,remaining:Int,out:MutableList<JSONObject>){
            if(remaining<=0)return;val day=operationalStore.loadDay(date)?:return;val events=day.optJSONArray("events")?:JSONArray();val n=needle.uppercase()
            // First pass: collect tombstones before considering older target events in the same day snapshot.
            for(i in 0 until events.length()){
                val e=events.optJSONObject(i)?:continue;if(e.optString("event_type").uppercase()!="HISTORY_DELETE")continue
                val p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val ids=p.optJSONArray("target_event_ids")?:JSONArray();for(j in 0 until ids.length()){val id=ids.optString(j);if(id.isNotBlank())hiddenHistoryIds.add(id)}
            }
            for(i in 0 until events.length()){
                if(out.size>=remaining)return;val e=events.optJSONObject(i)?:continue;val type=e.optString("event_type");val realId=e.optString("event_id");if(type.uppercase()!="HISTORY_DELETE"&&realId in hiddenHistoryIds)continue
                var mnv=e.optString("mnv");var full=e.optString("full_name");var actor=e.optString("actor").ifBlank{e.optString("actor_id")};var detail=e.optString("detail");var shift=e.optString("shift")
                var p:JSONObject?=null;if(mnv.isBlank()||full.isBlank()||actor.isBlank()||detail.isBlank()||n.isNotBlank()){p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrNull();mnv=mnv.ifBlank{p?.optString("mnv").orEmpty()};full=full.ifBlank{p?.optString("full_name").orEmpty()};actor=actor.ifBlank{p?.optString("actor").orEmpty()};detail=detail.ifBlank{p?.optString("detail").orEmpty().ifBlank{p?.optString("labor_type").orEmpty()}};shift=shift.ifBlank{p?.optString("shift").orEmpty()}}
                if(full.isBlank()&&mnv.isNotBlank())full=MasterDataCache.employee(this,mnv)?.optString("full_name").orEmpty();val label=if(type.uppercase()=="HISTORY_DELETE")"Xóa lịch sử" else friendly(type,e.optString("label"));if(type.uppercase()=="HISTORY_DELETE"&&detail.isBlank()){val hp=p?:runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrNull();detail="Đã xóa ${hp?.optInt("deleted_count",0)?:0} mục; dữ liệu gốc và dấu vết kiểm toán được giữ."};if(n.isNotBlank()&&!listOf(mnv,full,label,actor,detail,shift).any{it.uppercase().contains(n)})continue
                out.add(JSONObject().put("event_id",realId.ifBlank{"$date:$i"}).put("event_type",type).put("entity_type",e.optString("entity_type")).put("entity_id",e.optString("entity_id")).put("payload_json",e.optString("payload_json","{}")).put("label",label).put("mnv",mnv).put("full_name",full).put("actor",actor).put("actor_role",e.optString("actor_role")).put("origin",e.optString("origin")).put("detail",detail).put("shift",shift).put("at_iso",e.optString("at_iso").ifBlank{e.optString("committed_at")}.ifBlank{e.optString("at")}).put("authority_seq",e.optLong("authority_seq",0L)).put("business_date",date).put("history_source","SERVICE_CANONICAL").put("local_status","CONFIRMED"))
            }
        }
        fun loadRows():MutableList<JSONObject>{
            val out=mutableListOf<JSONObject>();val needle=query.trim();if(needle.isBlank())scanDate(selectedDate,"",Int.MAX_VALUE,out) else for(d in operationalStore.historyWindowDates()){if(out.size>=300)break;scanDate(d,needle,300,out)}
            for(local in operationalStore.localHistoryAll()){
                val bodyJ=local.optJSONObject("body")?:continue;val payload=bodyJ.optJSONObject("payload")?:bodyJ;val d=payload.optString("business_date").ifBlank{bodyJ.optString("business_date")}.ifBlank{runCatching{java.time.Instant.ofEpochMilli(local.optLong("queued_at")).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toLocalDate().toString()}.getOrDefault(selectedDate)};if(needle.isBlank()&&d!=selectedDate)continue
                val id=local.optString("event_id");if(id in hiddenHistoryIds)continue;val idx=out.indexOfFirst{it.optString("event_id")==id};if(idx>=0){out[idx].put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at"));continue}
                val action=bodyJ.optString("action");val mnv=payload.optString("mnv").ifBlank{bodyJ.optString("target_id")};val full=payload.optString("full_name").ifBlank{bodyJ.optString("target_label")}.ifBlank{MasterDataCache.employee(this,mnv)?.optString("full_name").orEmpty()};val actor=payload.optString("actor").ifBlank{payload.optString("login_id")}.ifBlank{"Thiết bị này"};val detail=bodyJ.optString("detail").ifBlank{payload.optString("labor_type")};val label=friendly(action.uppercase(),action)
                if(needle.isNotBlank()&&!listOf(mnv,full,label,actor,detail).any{it.uppercase().contains(needle.uppercase())})continue
                out.add(JSONObject().put("event_id",id).put("event_type",action.uppercase()).put("label",label).put("mnv",mnv).put("full_name",full).put("actor",actor).put("detail",detail).put("business_date",d).put("history_source","LOCAL_PDA").put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at")))
            }
            out.sortByDescending{e->val qAt=e.optLong("local_queued_at",0L);if(qAt>0)qAt else runCatching{java.time.Instant.parse(e.optString("at_iso")).toEpochMilli()}.getOrDefault(0L)};return out
        }
        fun render(){
            box.removeAllViews();currentPageDeleteIds.clear();pageChecks.clear();val rows=loadRows();val groups=rows.groupBy{e->e.optString("mnv").ifBlank{e.optString("event_id")}}.entries.sortedByDescending{entry->entry.value.maxOfOrNull{e->e.optLong("local_queued_at",0L).takeIf{it>0}?:runCatching{java.time.Instant.parse(e.optString("at_iso")).toEpochMilli()}.getOrDefault(0L)}?:0L};val states=groups.map{g->if(g.value.any{statusOf(it)=="FAILED"})"FAILED" else if(g.value.any{statusOf(it)=="PENDING"})"PENDING" else "SYNCED"};val metricRows=if(query.isBlank())rows else run{val savedQuery=query;query="";val allRows=loadRows();query=savedQuery;allRows};val pending=metricRows.count{statusOf(it)=="PENDING"};val failed=metricRows.count{statusOf(it)=="FAILED"}
            fun updateMetric(v:View,n:Int){if(v is ViewGroup){for(i in v.childCount-1 downTo 0){val child=v.getChildAt(i);if(child is TextView){child.text=n.toString();break}}}};updateMetric(allBtn,metricRows.size);updateMetric(pendingBtn,pending);updateMetric(failBtn,failed)
            val filtered=groups.filterIndexed{idx,_->filter=="ALL"||states[idx]==filter};if(pageStart>=filtered.size&&pageStart>0)pageStart=((filtered.size-1).coerceAtLeast(0)/pageSize)*pageSize;val visible=filtered.drop(pageStart).take(pageSize)
            if(query.isNotBlank())box.addView(info("Tìm trên toàn bộ lịch sử đang giữ trên PDA • tối đa 300 kết quả trước khi nhóm."))
            for(g in visible){
                val items=g.value;val first=items.first();val state=if(items.any{statusOf(it)=="FAILED"})"FAILED" else if(items.any{statusOf(it)=="PENDING"})"PENDING" else "SYNCED";val label=when(state){"FAILED"->"Lỗi đồng bộ";"PENDING"->"Chưa đồng bộ";else->"Đã đồng bộ"};val tint=when(state){"FAILED"->Color.rgb(254,242,242);"PENDING"->Color.rgb(255,251,235);else->Color.rgb(240,253,250)};val mnv=first.optString("mnv");val full=first.optString("full_name");val last=items.first()
                val deletable=items.filter{it.optString("event_type").uppercase()!="HISTORY_DELETE"}.map{it.optString("event_id")}.filter{it.isNotBlank()}.distinct();currentPageDeleteIds.addAll(deletable)
                val card=column(tint).apply{
                    setPadding(dp(13),dp(11),dp(13),dp(11));background=outlineBg(tint,17)
                    val top=row(tint).apply{gravity=Gravity.CENTER_VERTICAL
                        if(isSuper()&&deletable.isNotEmpty()){val c=CheckBox(this@OperationsActivity).apply{isChecked=deletable.all{it in selectedHistoryIds};setOnCheckedChangeListener{_,on->if(on)selectedHistoryIds.addAll(deletable)else selectedHistoryIds.removeAll(deletable.toSet());updateSelectedCount()}};pageChecks.add(c);addView(c,size(dp(42),dp(42)))}
                        addView(txt(last.optString("label").ifBlank{"Thao tác"},12.5f,ink,true),LinearLayout.LayoutParams(0,-2,1f));addView(txt(label,9f,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal},true).apply{setPadding(dp(7),dp(4),dp(7),dp(4));background=round(Color.WHITE,9)})
                    };addView(top,matchWrap());val subject=listOf(mnv,full).filter{it.isNotBlank()}.joinToString(" – ").ifBlank{last.optString("entity_id").ifBlank{"Hệ thống"}};addView(txt(subject,10.2f,navy,true));val actorText=last.optString("actor").ifBlank{"Hệ thống"};val roleText=last.optString("actor_role").ifBlank{"—"};val originText=last.optString("origin").ifBlank{"Service"};addView(txt("${formatIso(last.optString("at_iso"))} • $actorText • $roleText • $originText",9.7f,muted,false));if(last.optString("detail").isNotBlank())addView(txt(last.optString("detail"),9.5f,muted,false).apply{maxLines=3});setOnClickListener{historyTimeline(items)}
                };box.addView(card,matchWrap());box.addView(gap(6))
            }
            updateSelectedCount()
            if(visible.isEmpty())box.addView(info("Không có lịch sử phù hợp."));if(filtered.isNotEmpty()){val from=pageStart+1;val to=(pageStart+visible.size).coerceAtMost(filtered.size);box.addView(info("Đang hiển thị $from–$to / ${filtered.size} • tối đa 100 bản ghi mỗi trang."));val nav=row(bg);if(pageStart>0)nav.addView(smallButton("‹ 100 TRƯỚC",navy).apply{setOnClickListener{pageStart=(pageStart-pageSize).coerceAtLeast(0);render()}},LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(3)});if(pageStart+pageSize<filtered.size)nav.addView(smallButton("100 TIẾP ›",teal).apply{setOnClickListener{pageStart+=pageSize;render()}},LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(3)});if(nav.childCount>0)box.addView(nav,matchWrap())}
        }
        allBtn.setOnClickListener{filter="ALL";pageStart=0;render()};pendingBtn.setOnClickListener{filter="PENDING";pageStart=0;render()};failBtn.setOnClickListener{filter="FAILED";pageStart=0;render()}
        q.addTextChangedListener(object:TextWatcher{override fun beforeTextChanged(v:CharSequence?,st:Int,c:Int,a:Int)=Unit;override fun onTextChanged(v:CharSequence?,st:Int,b:Int,c:Int){query=v?.toString().orEmpty();pageStart=0;render()};override fun afterTextChanged(v:Editable?)=Unit})
        dateButton.setOnClickListener{val d=runCatching{java.time.LocalDate.parse(selectedDate)}.getOrDefault(java.time.LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh")));android.app.DatePickerDialog(this,{_,y,m,day->selectedDate=java.time.LocalDate.of(y,m+1,day).toString();dateButton.text=java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"));query="";q.setText("");pageStart=0;render()},d.year,d.monthValue-1,d.dayOfMonth).show()}
        attach(root,body);render();refreshHistoryCanonical()
    }

    private fun historyGroupStatus(items:List<JSONObject>):String{
        val states=items.map{it.optString("local_status").trim().uppercase()}
        if(states.any{it in setOf("REJECTED","REVIEW_REQUIRED","CONFLICT","FAILED","ERROR")})return "Lỗi đồng bộ"
        val allSynced=states.all{it.isBlank()||it in setOf("CONFIRMED","SYNCED","ACKED","CANONICAL")}
        return if(allSynced)"Đã đồng bộ" else "Chưa đồng bộ"
    }

    private fun historyEventTime(e:JSONObject):String{val local=e.optLong("local_queued_at");if(local>0)return java.text.SimpleDateFormat("HH:mm:ss dd/MM/yyyy",java.util.Locale("vi","VN")).apply{timeZone=java.util.TimeZone.getTimeZone("Asia/Ho_Chi_Minh")}.format(java.util.Date(local));return formatIso(e.optString("committed_at").ifBlank{e.optString("occurred_at").ifBlank{e.optString("at_iso").ifBlank{e.optString("at")}}})}
    private fun historyCanEdit(e:JSONObject):Boolean{if(!isAdmin())return false;val date=e.optString("business_date").ifBlank{e.optString("cache_business_date")};val ix=operationalStore.availableDates().take(7).indexOf(date);return ix>=0&&ix<=if(isSuper())6 else 1}
    private fun flushDeferredHistoryDeletes(){
        if(!isSuper())return
        val prefs=getSharedPreferences("pp_history_delete_ui",MODE_PRIVATE)
        val queue=(prefs.getStringSet("deferred_ids",emptySet())?:emptySet()).filter{it.isNotBlank()}.toList()
        if(queue.isEmpty())return
        fun next(i:Int){
            if(i>=queue.size)return
            val id=queue[i]
            api.call("history_delete",JSONObject().put("event_ids",JSONArray(listOf(id))).put("idempotency_key","beta47-history-delete-$id").put("reason","SUPERADMIN xóa lịch sử từ PDA")){r->
                if(r.ok){val left=(prefs.getStringSet("deferred_ids",emptySet())?:emptySet()).toMutableSet();left.remove(id);prefs.edit().putStringSet("deferred_ids",left).apply()}
                next(i+1)
            }
        }
        next(0)
    }

    private fun deleteHistoryBulk(ids:List<String>){
        if(!isSuper()){showError("Chỉ Quản trị cao nhất được xóa lịch sử.");return}
        val clean=ids.filter{it.isNotBlank()}.distinct();if(clean.isEmpty()){showError("Chọn ít nhất một lịch sử cần xóa.");return}
        AlertDialog.Builder(this).setTitle("Xóa ${clean.size} lịch sử?").setMessage("Xóa các mục lịch sử đã chọn?").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->
            verifyDeletePassword("xóa ${clean.size} lịch sử"){
                val prefs=getSharedPreferences("pp_history_delete_ui",MODE_PRIVATE)
                val hidden=(prefs.getStringSet("hidden_ids",emptySet())?:emptySet()).toMutableSet();hidden.addAll(clean)
                val deferred=(prefs.getStringSet("deferred_ids",emptySet())?:emptySet()).toMutableSet();deferred.addAll(clean)
                prefs.edit().putStringSet("hidden_ids",hidden).putStringSet("deferred_ids",deferred).apply()
                TopNotice.show(this,"Đã ghi nhận xóa ${clean.size} lịch sử.",TopNotice.Kind.SUCCESS)
                foregroundSync.requestSync();historyScreen()
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({flushDeferredHistoryDeletes()},1400L)
            }
        }.show()
    }

    private fun historyTimeline(items:List<JSONObject>){
        screenState="HISTORY_DETAIL";val root=baseRoot("LỊCH SỬ");val body=body();val first=items.firstOrNull()?:return;val mnv=first.optString("mnv");val full=first.optString("full_name").ifBlank{MasterDataCache.employee(this,mnv)?.optString("full_name").orEmpty()};val detailTitle=if(mnv.isBlank())"Chi tiết thao tác" else listOf(mnv,full).filter{it.isNotBlank()}.joinToString(" – ");body.addView(section(detailTitle));body.addView(gap(8))
        fun label(type:String)=when(type){"ATTENDANCE_ENTER"->"Vào ca";"ATTENDANCE_EXIT"->"Ra ca";"RESOURCE_CHANGE"->"Đổi tài nguyên / vị trí";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"HISTORICAL_CORRECTION"->"Sửa lịch sử";else->type.ifBlank{"Thao tác"}}
        items.sortedBy{historyEventTime(it)}.forEach{e->
            val type=e.optString("event_type");val actor=e.optString("actor_id").ifBlank{e.optString("actor")}.ifBlank{"Hệ thống"};val status=historyGroupStatus(listOf(e));val statusColor=when(status){"Đã đồng bộ"->green;"Lỗi đồng bộ"->red;else->orange};val fill=when(status){"Đã đồng bộ"->android.graphics.Color.rgb(239,250,244);"Lỗi đồng bộ"->android.graphics.Color.rgb(255,239,239);else->android.graphics.Color.rgb(255,248,230)}
            val p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val after=p.optJSONObject("after");val src=after?:p;val d=mutableListOf<String>();listOf("shift","work_choice","pda_serial","user_pick","pack_table","user_pack","labor_type","time_marker","start_at","end_at","note","state").forEach{k->val v=src.optString(k);if(v.isNotBlank())d.add("$k: $v")}
            val card=column(fill).apply{setPadding(dp(13),dp(11),dp(13),dp(11));background=android.graphics.drawable.GradientDrawable().apply{setColor(fill);cornerRadius=dp(14).toFloat();setStroke(dp(1),statusColor)}}
            val head=row(android.graphics.Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL};head.addView(txt(label(type),12.5f,navy,true),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(6)});head.addView(txt(status,8.9f,statusColor,true).apply{setPadding(dp(7),dp(4),dp(7),dp(4));background=round(fill,9)})
            card.addView(head,matchWrap());card.addView(txt("${historyEventTime(e)} • $actor",9.8f,muted,false));if(d.isNotEmpty())card.addView(txt(d.joinToString("\n"),9.8f,ink,false));val err=e.optString("local_error");if(err.isNotBlank())card.addView(txt("Lỗi: $err",9.5f,red,true));card.addView(txt("Event ID: ${e.optString("event_id")}",8.7f,muted,false));if((e.optString("entity_type")=="ATTENDANCE_SESSION"||e.optString("entity_type")=="LABOR_SESSION")&&e.optString("entity_id").isNotBlank()&&historyCanEdit(e)){card.addView(gap(7));card.addView(smallButton("SỬA THÔNG TIN",teal).apply{setOnClickListener{historyEditDialog(e)}})};body.addView(card,matchWrap());body.addView(gap(7))
        };attach(root,body)
    }

    private fun historyEditDialog(e:JSONObject){val entity=e.optString("entity_type");if(entity!="ATTENDANCE_SESSION"&&entity!="LABOR_SESSION")return;val raw=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val initial=raw.optJSONObject("after")?:raw;val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};val fields=LinkedHashMap<String,EditText>();val keys=if(entity=="ATTENDANCE_SESSION")listOf("shift","work_choice","pda_serial","user_pick","pack_table","user_pack","state")else listOf("labor_type","time_marker","start_at","end_at","note","state");for(k in keys){val v=input(k,false).apply{setText(initial.optString(k))};fields[k]=v;box.addView(labelled(k,v));box.addView(gap(6))};val deduct=CheckBox(this).apply{text="Khấu trừ nhân sự";isChecked=initial.optBoolean("deduct_staff",false);visibility=if(entity=="LABOR_SESSION")View.VISIBLE else View.GONE};box.addView(deduct);val reason=input("Lý do chỉnh sửa (bắt buộc)",false);box.addView(labelled("Lý do",reason));val dialog=AlertDialog.Builder(this).setTitle("Sửa thông tin lịch sử").setView(ScrollView(this).apply{addView(box)}).setNegativeButton("Hủy",null).setPositiveButton("LƯU",null).create();dialog.setOnShowListener{dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener{val why=reason.text.toString().trim();if(why.length<3){showError("Nhập lý do chỉnh sửa.");return@setOnClickListener};val patch=JSONObject();fields.forEach{(k,v)->patch.put(k,v.text.toString().trim())};if(entity=="LABOR_SESSION")patch.put("deduct_staff",deduct.isChecked);val p=JSONObject().put("entity_type",entity).put("entity_id",e.optString("entity_id")).put("reason",why).put("patch",patch).put("target_event_id",e.optString("event_id")).put("idempotency_key",UUID.randomUUID().toString()).put("client_source","PDA");api.call("history_correction",p){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không sửa được lịch sử")else{dialog.dismiss();TopNotice.show(this,"Đã lưu chỉnh sửa vào lịch sử.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();historyScreen()}}}}};dialog.show()}

    // S51B_BETA45_COMPILE_GUARD
    // S51_BETA45_MANUAL_UPDATE_SYNC_DETAIL_VI: detailed Vietnamese sync view shared by all roles.
    // S53_BETA47_SHEET_LOGIC_UI: concise sync screen + unified APP/WEB presence.
    private fun syncScreen(){
        module="SYNC";screenState="SYNC"
        val root=baseRoot("ĐỒNG BỘ");val body=body()
        val overview=column(surface).apply{setPadding(dp(14),dp(12),dp(14),dp(12));background=outlineBg(surface,18)}
        val overviewTitle=txt("Đang kiểm tra trạng thái...",14f,navy,true);val overviewSub=txt("Đang kiểm tra PDA, Service và Google Sheet.",10f,muted,false)
        overview.addView(overviewTitle);overview.addView(gap(4));overview.addView(overviewSub);body.addView(overview,matchWrap());body.addView(gap(9))
        val pdaBox=column(bg);val serviceBox=column(bg);val sheetBox=column(bg);val otherBox=column(bg)
        body.addView(pdaBox,matchWrap());body.addView(serviceBox,matchWrap());body.addView(sheetBox,matchWrap());body.addView(otherBox,matchWrap())
        val actions=row(bg);val syncNow=smallButton("ĐỒNG BỘ NGAY",teal);val refresh=smallButton("LÀM MỚI",navy);actions.addView(syncNow,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(4)});actions.addView(refresh,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(4)});body.addView(gap(9));body.addView(actions,matchWrap())
        fun dateVi(v:String)=runCatching{java.time.LocalDate.parse(v.take(10)).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(v.ifBlank{"—"})
        fun timeVi(v:String)=if(v.isBlank())"—" else formatIso(v)
        fun authorityVi(v:String)=when(v.uppercase()){ "SERVICE_PRIMARY"->"Dịch vụ chính";"GOOGLE_FALLBACK"->"Google dự phòng";"RECONCILING"->"Đang đối chiếu dữ liệu";"OFFLINE_LOCAL"->"Chỉ lưu trên PDA";else->"Chưa xác định" }
        fun replicaVi(v:String)=when(v.uppercase()){ "SYNCED","HEALTHY","OK"->"Đã đồng bộ";"PENDING","INFLIGHT","RUNNING"->"Đang chuyển dữ liệu";"RETRY"->"Đang chờ gửi lại";"ERROR","FAILED"->"Có lỗi";else->if(v.isBlank())"Chưa có dữ liệu" else "Đang theo dõi" }
        fun loadPda(){
            pdaBox.removeAllViews()
            val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(0)
            val active=runCatching{SyncDirectionTracker.snapshot().active}.getOrDefault(false)
            val dates=runCatching{operationalStore.availableDates()}.getOrDefault(emptyList())
            val network=DeviceNetworkStatus.snapshot(this).header(lastLatencyMs)
            val syncText=when{active->"Đang trao đổi dữ liệu";pending>0->"Đang chờ đồng bộ";lastConnected==true->"Đã đồng bộ";else->"Chưa xác định"}
            overviewTitle.text=when{lastConnected==false->"Chưa kết nối được Service";active->"Đang đồng bộ dữ liệu";pending>0->"Có dữ liệu đang chờ đồng bộ";else->"Hệ thống đang hoạt động bình thường"}
            overviewTitle.setTextColor(if(lastConnected==false)red else if(active||pending>0)orange else teal)
            overviewSub.text="$network • PDA: $syncText"
            pdaBox.addView(section("THÔNG TIN TRÊN PDA"))
            pdaBox.addView(details(listOf(
                "Kết nối mạng" to network,
                "Trạng thái đồng bộ trên PDA" to syncText,
                "Hàng đợi đồng bộ trên PDA" to pending.toString(),
                "Dung lượng cache" to humanBytes(operationalStore.storageBytes()),
                "Ngày nghiệp vụ hiện tại" to dateVi(operationalStore.businessDate()),
                "Ngày dữ liệu mới nhất trên PDA" to dateVi(dates.firstOrNull().orEmpty())
            )))
            pdaBox.addView(gap(8))
            otherBox.removeAllViews();otherBox.addView(section("THÔNG TIN ĐỒNG BỘ KHÁC"));otherBox.addView(details(listOf(
                "Luồng trao đổi dữ liệu" to if(active)"Đang hoạt động" else "Đang nghỉ",
                "Trạng thái mạng" to network,
                "Cơ chế gửi lại" to if(pending>0)"Tự động khi kết nối phù hợp" else "Không có dữ liệu cần gửi lại"
            )));otherBox.addView(gap(8))
        }
        fun loadService(){
            serviceBox.removeAllViews();serviceBox.addView(section("THÔNG TIN TRÊN SERVICE"));serviceBox.addView(info("Đang kiểm tra Service..."))
            sheetBox.removeAllViews();sheetBox.addView(section("THÔNG TIN TRÊN GOOGLE SHEET"));sheetBox.addView(info("Đang kiểm tra trạng thái sao chép Google Sheet..."))
            val started=android.os.SystemClock.elapsedRealtime()
            api.call("sync_status",JSONObject()){r->runOnUiThread{
                if(screenState!="SYNC")return@runOnUiThread
                val rt=(android.os.SystemClock.elapsedRealtime()-started).coerceAtLeast(0);lastLatencyMs=rt
                serviceBox.removeAllViews();serviceBox.addView(section("THÔNG TIN TRÊN SERVICE"))
                sheetBox.removeAllViews();sheetBox.addView(section("THÔNG TIN TRÊN GOOGLE SHEET"))
                if(!r.ok||r.json==null){
                    lastConnected=false;refreshHeaderConnection()
                    serviceBox.addView(details(listOf("Trạng thái Service" to "Chưa phản hồi","Độ trễ lần kiểm tra" to "$rt ms","Dữ liệu trên PDA" to "Vẫn được lưu an toàn")))
                    sheetBox.addView(details(listOf("Trạng thái Google Sheet" to "Chưa lấy được từ Service","Lần sao chép thành công" to "Chưa xác định")))
                    serviceBox.addView(gap(8));sheetBox.addView(gap(8));loadPda();return@runOnUiThread
                }
                lastConnected=true;refreshHeaderConnection()
                val j=r.json?:JSONObject();val auth=j.optJSONObject("authority")?:JSONObject();val rep=j.optJSONObject("replication")?:JSONObject()
                serviceBox.addView(details(listOf(
                    "Trạng thái Service" to "Đang hoạt động",
                    "Độ trễ tới Service" to "$rt ms",
                    "Nguồn dữ liệu đang dùng" to authorityVi(auth.optString("mode").ifBlank{j.optString("authority_mode")}),
                    "Mốc dữ liệu trên Service" to auth.optLong("authority_seq",j.optLong("server_seq",0L)).toString()
                )))
                sheetBox.addView(details(listOf(
                    "Trạng thái Google Sheet" to replicaVi(rep.optString("state")),
                    "Bản ghi chờ sao chép Google Sheet" to rep.optInt("pending_count",0).toString(),
                    "Lần sao chép thành công" to timeVi(rep.optString("last_success_at"))
                )))
                serviceBox.addView(gap(8));sheetBox.addView(gap(8));loadPda()
            }}
        }
        fun load(){loadPda();loadService()}
        syncNow.setOnClickListener{foregroundSync.requestSync();flushDeferredHistoryDeletes();TopNotice.show(this,"Đã yêu cầu đồng bộ dữ liệu.",TopNotice.Kind.INFO);android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({if(screenState=="SYNC")load();flushDeferredHistoryDeletes()},900L)}
        refresh.setOnClickListener{load()}
        attach(root,body);load()
    }

    private fun pdaExchangeScreen(){
        module="PDA_EXCHANGE";screenState="PDA_EXCHANGE";val root=baseRoot("ĐỔI / TRẢ PDA");val body=body();body.addView(info("Logic thử nghiệm: thao tác Đổi PDA giữ phiên và chuyển sang PICK với PDA mới; Trả PDA thu hồi tài nguyên và chuyển vị trí trong ca về KHÔNG. Mọi thao tác dùng Event ID và được lưu lịch sử."));body.addView(gap(8));val mnv=mnvInput("Quét QR hoặc nhập mã nhân viên");val reason=input("Lý do đổi / trả PDA",false);val box=column(bg);body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(7));body.addView(labelled("Lý do",reason));body.addView(gap(8));body.addView(box,matchWrap());fun load(){val id=mnv.text.toString().trim();if(id.isBlank()){showError("Nhập mã nhân viên.");return};api.call("employee_context",JSONObject().put("mnv",id).put("include_options",false)){r->runOnUiThread{box.removeAllViews();if(!r.ok){showError(r.error?:"Không tải được phiên");return@runOnUiThread};if(r.json?.optString("state")!="ACTIVE"){box.addView(info("Nhân viên phải đang trong phiên ACTIVE."));return@runOnUiThread};val ctx=r.json?:JSONObject();val e=ctx.optJSONObject("employee")?:JSONObject();val ses=ctx.optJSONObject("session")?:JSONObject();box.addView(employeeCard(e));box.addView(gap(7));box.addView(details(listOf("PDA hiện tại" to dash(ses.optString("pda_serial")),"Vị trí" to workText(ses.optString("work_choice")),"Ca" to ses.optString("shift"))));box.addView(gap(7));val pdas=MasterDataCache.resourceOptions(this).optJSONArray("pdas")?:JSONArray();val pdaField=pdaInput(pdas,ses.optString("pda_serial"));box.addView(labelled("PDA mới",pdaField));box.addView(gap(8));val actions=row(bg);val change=smallButton("ĐỔI PDA",teal);val giveBack=smallButton("TRẢ PDA",orange);actions.addView(change,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginEnd=dp(3)});actions.addView(giveBack,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3)});box.addView(actions,matchWrap());change.setOnClickListener{val why=reason.text.toString().trim();if(why.isBlank()){showError("Nhập lý do đổi PDA.");return@setOnClickListener};val serial=resolvePda(pdas,pdaField.text.toString());if(serial==null){showError("Chọn đúng PDA theo 5 số cuối Seri.");return@setOnClickListener};val p=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id).put("work_choice","PICK").put("pda_serial",serial).put("note","Đổi PDA: $why");val pick=ses.optString("user_pick");if(pick.isNotBlank())p.put("user_pick",pick);api.call("resource_change",p){x->runOnUiThread{if(!x.ok)showError(x.error?:"Không đổi được PDA")else{TopNotice.show(this,"Đã đổi PDA.",TopNotice.Kind.SUCCESS);load()}}}};giveBack.setOnClickListener{val why=reason.text.toString().trim();if(why.isBlank()){showError("Nhập lý do trả PDA.");return@setOnClickListener};api.call("resource_change",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id).put("work_choice","KHONG").put("note","Trả PDA: $why")){x->runOnUiThread{if(!x.ok)showError(x.error?:"Không trả được PDA")else{TopNotice.show(this,"Đã trả PDA.",TopNotice.Kind.SUCCESS);load()}}}}}}};bindScannerEnter(mnv){load()};attach(root,body);mnv.requestFocus()
    }

    // S53_BETA47_SHEET_LOGIC_UI
    private fun settingsScreen(){
        module="SETTINGS"
        screenState="SETTINGS"
        val root=baseRoot("CÀI ĐẶT")
        val body=body()
        body.addView(section("Tài khoản"))
        body.addView(listCard("$name • ${roleText(effectiveRole)}","$login${if(position.isBlank())"" else "  •  $position"}\nMail: ${email.ifBlank{"Chưa cấu hình"}}"))
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
        // S23_PDA_IMPORT_UI_APPLIED: SUPERADMIN uses the shared Service Import Engine.
        if(isSuper()){
            body.addView(gap(7))
            body.addView(primary("IMPORT EXCEL",teal){
                startActivity(android.content.Intent(this,PdaImportActivity::class.java))
            },matchWrap())
        }
        body.addView(section("Giao diện"))
        body.addView(themePicker(),matchWrap())
        body.addView(section("THÔNG TIN ỨNG DỤNG"))
        val deviceName="${Build.MANUFACTURER} ${Build.MODEL}".trim()
        body.addView(details(listOf(
            "Tên thiết bị" to deviceName,
            "Hệ điều hành" to "Android ${Build.VERSION.RELEASE}",
            "Kênh phát hành" to if(BuildConfig.CHANNEL=="BETA")"Bản thử nghiệm" else "Bản ổn định",
            "Phiên bản ứng dụng" to BuildConfig.VERSION_NAME,
            "Mã phiên bản" to BuildConfig.VERSION_CODE.toString()
        )))
        body.addView(section("CẬP NHẬT PHIÊN BẢN"))
        body.addView(primary("KIỂM TRA CẬP NHẬT",teal){UpdateManager.openManual(this)},matchWrap())
        body.addView(gap(10))
        body.addView(section("Nhật ký"))
        body.addView(primary("GỬI BÁO LỖI",teal){sendDiagnostic()},matchWrap())
        body.addView(gap(14))
        body.addView(primary("ĐĂNG XUẤT",red){api.call("logout"){runOnUiThread{api.clearSession();startActivity(android.content.Intent(this,FullBetaActivity::class.java).apply{addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP or android.content.Intent.FLAG_ACTIVITY_NEW_TASK or android.content.Intent.FLAG_ACTIVITY_CLEAR_TASK)});finish();overridePendingTransition(0,0)}}},matchWrap())
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
    private fun changePasswordDialog(){val box=column(surface).apply{setPadding(dp(8),0,dp(8),0)};val current=input("Mật khẩu hiện tại",true);val next=input("Mật khẩu mới",true);val confirm=input("Nhập lại mật khẩu mới",true);box.addView(current);box.addView(gap(7));box.addView(next);box.addView(gap(7));box.addView(confirm);AlertDialog.Builder(this).setTitle("Đổi mật khẩu").setView(box).setNegativeButton("Hủy",null).setPositiveButton("CẬP NHẬT"){_,_->if(next.text.toString()!=confirm.text.toString()){showError("Mật khẩu xác nhận không khớp.");return@setPositiveButton};api.call("change_password",JSONObject().put("current_password",current.text.toString()).put("new_password",next.text.toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Đổi mật khẩu thất bại")else TopNotice.show(this,"Đã đổi mật khẩu.",TopNotice.Kind.SUCCESS)}}}.show()}
    private fun changeEmailDialog(){val value=input("Địa chỉ mail nhận reset mật khẩu",false).apply{setText(email)};AlertDialog.Builder(this).setTitle("Đổi mail").setView(value).setNegativeButton("Hủy",null).setPositiveButton("CẬP NHẬT"){_,_->val next=value.text.toString().trim();api.call("change_email",JSONObject().put("email",next)){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không đổi được mail")else{email=r.json?.optJSONObject("account")?.optString("email",next)?:next;TopNotice.show(this,"Đã cập nhật mail nhận reset.",TopNotice.Kind.SUCCESS);settingsScreen()}}}}.show()}
    private fun sendDiagnostic(){AlertDialog.Builder(this).setTitle("Gửi log thủ công?").setMessage("Gửi gói chẩn đoán hiện tại lên hệ thống?").setNegativeButton("NO",null).setPositiveButton("YES"){_,_->LocalLogManager.sendManualReport(this,api,module,connectionSummary()){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không gửi được báo lỗi")else TopNotice.show(this,"Đã gửi báo lỗi thành công.",TopNotice.Kind.SUCCESS)}}}.show()}

    private fun accountManager(){
        screenState="ACCOUNT_MANAGER"
        val root=baseRoot("QUẢN LÝ TÀI KHOẢN")
        val body=body()
        val selected=linkedSetOf<String>()
        val checks=mutableListOf<CheckBox>()
        body.addView(primary("TẠO TÀI KHOẢN",green){accountCreateDialog()},matchWrap())
        if(isSuper()){
            body.addView(gap(7))
            val bulk=row(bg)
            bulk.addView(smallButton("CHỌN TẤT CẢ",navy).apply{
                setOnClickListener{checks.forEach{if(it.isEnabled)it.isChecked=true}}
            },LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)})
            bulk.addView(smallButton("XÓA ĐÃ CHỌN",red).apply{
                setOnClickListener{deleteAccountsBulk(selected.toList())}
            },LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)})
            body.addView(bulk,matchWrap())
        }
        body.addView(gap(10))
        val box=column(bg)
        body.addView(box,matchWrap())
        api.call("account_list"){r->runOnUiThread{
            box.removeAllViews()
            if(handleAuth(r))return@runOnUiThread
            if(!r.ok){box.addView(info(r.error?:"Không tải được tài khoản"));return@runOnUiThread}
            val a=r.json?.optJSONArray("items")?:JSONArray()
            for(i in 0 until a.length()){
                val x=a.optJSONObject(i)?:continue
                val id=x.optString("login_id")
                val isProtectedAccount=id==login||x.optString("role")=="SUPERADMIN"
                val card=column(surface).apply{
                    setPadding(dp(12),dp(10),dp(12),dp(10))
                    background=outlineBg(surface,12)
                    val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL}
                    if(isSuper()){
                        val c=CheckBox(this@OperationsActivity).apply{
                            isEnabled=!isProtectedAccount
                            isChecked=id in selected
                            setOnCheckedChangeListener{_,on->if(on)selected.add(id)else selected.remove(id)}
                        }
                        checks.add(c)
                        top.addView(c,size(dp(42),dp(42)))
                    }
                    top.addView(column(surface).apply{
                        addView(txt("$id • ${x.optString("display_name")}",13f,navy,true))
                        addView(txt("${roleText(x.optString("role"))} • ${if(x.optString("status")=="ACTIVE")"Đang hoạt động" else "Đã vô hiệu hóa"} • ${x.optString("email")}",9.8f,muted,false))
                    },LinearLayout.LayoutParams(0,-2,1f))
                    addView(top,matchWrap())
                    if(id!=login){
                        addView(gap(6))
                        val actions=row(surface)
                        if(isSuper()){
                            actions.addView(smallButton("SỬA",teal).apply{setOnClickListener{accountEditDialog(x)}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginEnd=dp(3)})
                        }
                        val newStatus=if(x.optString("status")=="ACTIVE")"DISABLED" else "ACTIVE"
                        actions.addView(smallButton(if(newStatus=="DISABLED")"VÔ HIỆU" else "KÍCH HOẠT",if(newStatus=="DISABLED")orange else green).apply{
                            setOnClickListener{api.call("account_status",JSONObject().put("login_id",id).put("status",newStatus)){rr->runOnUiThread{if(!rr.ok)showError(rr.error?:"Không cập nhật được")else accountManager()}}}
                        },LinearLayout.LayoutParams(0,dp(38),1f).apply{marginStart=dp(3);marginEnd=dp(3)})
                        if(isSuper()&&!isProtectedAccount){
                            actions.addView(smallButton("XÓA",red).apply{setOnClickListener{deleteAccountsBulk(listOf(id))}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginStart=dp(3)})
                        }
                        addView(actions,matchWrap())
                    }
                }
                box.addView(card,matchWrap())
                box.addView(gap(7))
            }
        }}
        attach(root,body)
    }

    private fun accountEditDialog(x:JSONObject){
        if(!isSuper())return;val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};val display=input("Tên hiển thị",false).apply{setText(x.optString("display_name"))};val mail=input("Mail",false).apply{setText(x.optString("email"))};val roles=arrayOf("USER","ADMIN");val roleSp=spinner(roles);roleSp.setSelection(if(x.optString("role")=="ADMIN")1 else 0);box.addView(labelled("Tên hiển thị",display));box.addView(gap(7));box.addView(labelled("Quyền",roleSp));box.addView(gap(7));box.addView(labelled("Mail",mail));AlertDialog.Builder(this).setTitle("Sửa tài khoản ${x.optString("login_id")}").setView(box).setNegativeButton("Hủy",null).setPositiveButton("LƯU"){_,_->val rr=roleSp.selectedItem.toString();api.call("account_upsert",JSONObject().put("login_id",x.optString("login_id")).put("display_name",display.text.toString().trim()).put("position",rr.lowercase()).put("email",mail.text.toString().trim()).put("role",rr)){r->runOnUiThread{if(!r.ok)showError(r.error?:"Không sửa được tài khoản")else accountManager()}}}.show()
    }

    private fun deleteAccountsBulk(ids:List<String>){
        if(!isSuper()){showError("Chỉ Quản trị cao nhất được xóa tài khoản.");return};val clean=ids.filter{it.isNotBlank()&&it!=login}.distinct();if(clean.isEmpty()){showError("Chọn ít nhất một tài khoản có thể xóa.");return}
        AlertDialog.Builder(this).setTitle("Xóa ${clean.size} tài khoản?").setMessage("Tài khoản Quản trị cao nhất và tài khoản đang đăng nhập được bảo vệ. Nhật ký kiểm toán vẫn được giữ.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa ${clean.size} tài khoản"){api.call("account_delete",JSONObject().put("login_ids",JSONArray(clean))){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không xóa được tài khoản");return@runOnUiThread};val blocked=r.json?.optJSONArray("blocked")?:JSONArray();TopNotice.show(this,if(blocked.length()>0)"Đã xóa các tài khoản hợp lệ; ${blocked.length()} mục được bảo vệ hoặc không thể xóa." else "Đã xóa tài khoản.",if(blocked.length()>0)TopNotice.Kind.WARNING else TopNotice.Kind.SUCCESS);accountManager()}}}}.show()
    }

    private fun accountCreateDialog(){
        val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))}
        val loginInput=input("Tài khoản",false)
        val display=input("Tên hiển thị",false)
        val allowedPositions=if(isSuper())arrayOf("USER","ADMIN")else arrayOf("USER")
        val positionSp=spinner(allowedPositions)
        val mail=input("Mail nhận reset",false).apply{setText("tam95.supra@gmail.com")}
        val pass=input("Mật khẩu ban đầu",true)
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
            "RESOURCE_EDITOR","RESOURCE_LIST"->resourceHome()
            "ACCOUNT_MANAGER"->settingsScreen()
            "EMPLOYEE","EMPLOYEE_LOADING","EMPLOYEE_LOOKUP_ERROR"->employeeScan()
            "SCAN","LABOR_HOME","RESOURCE_HOME","REPORT","LISTS","PDA_EXCHANGE"->businessHome()
            "HISTORY_DETAIL"->historyScreen()
            else->{
                if(isRootScreen()&&tabHistory.isNotEmpty()){
                    val previous=tabHistory.removeLast()
                    navigateTab(previous,false)
                }else if(module!="BUSINESS"){
                    module="BUSINESS";businessHome()
                }else finish()
            }
        }
    }

    private fun simpleMessage(title:String,message:String){val root=baseRoot(title);val body=body();body.addView(info("ⓘ $message"));attach(root,body)}
    private fun baseRoot(title:String)=column(bg).apply{addView(appBar(title))}
    private fun body()=column(bg).apply{setPadding(dp(14),dp(13),dp(14),dp(83))}
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
    private fun isRootScreen()=screenState=="BUSINESS"||screenState=="STAFF"||screenState=="HISTORY"||screenState=="SYNC"||screenState=="SETTINGS"||screenState=="ROLE_MODE"

    private fun serviceProviderFromRuntime():String{
        val st=api.runtimeStatus();val mode=st.optString("authority_mode");val route=st.optString("route")
        return when{
            mode=="GOOGLE_FALLBACK"||route=="GAS_COMPAT"->"Google Drive"
            mode=="SERVICE_PRIMARY"||mode=="RECONCILING"||route.startsWith("SERVICE_")->"Cloudflare"
            st.optString("service_url").isNotBlank()->"Cloudflare"
            else->serviceProviderCache
        }
    }
    private fun connectionSummary():String{val network=when(lastConnected){true->lastSyncLatencyMs?.let{"$it ms"}?:"Có mạng";false->"Mất kết nối";null->"Chưa kiểm tra"};val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(0);return "Mạng: $network | Đồng bộ: ${if(pending==0)"Hoàn tất" else "Đang chờ đồng bộ"} | Dịch vụ: ${if(lastConnected==true)"Hoạt động" else "Đang chờ"}"}
    private fun refreshHeaderConnection(){val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(lastProjectionPending);networkStatusText?.text=when(lastConnected){true->lastSyncLatencyMs?.let{"$it ms"}?:"Có mạng";false->"Mất mạng";null->"—"};syncStatusText?.text=if(pending>0)"Đang chờ" else if(lastConnected==true)"Hoàn tất" else "Đang chờ";serviceStatusText?.text=if(lastConnected==true)"Hoạt động" else if(lastConnected==false)"Mất kết nối" else "—"}
    private fun headerStatusChip(iconRes:Int,label:String,valueView:TextView)=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(6),dp(6),dp(6),dp(6));background=round(Color.argb(32,255,255,255),13);addView(ImageView(this@OperationsActivity).apply{setImageResource(iconRes);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(2),dp(2),dp(2),dp(2))},size(dp(22),dp(22)));addView(column(Color.TRANSPARENT).apply{addView(txt(label,7.2f,Color.argb(210,255,255,255),false).apply{maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,8,1,android.util.TypedValue.COMPLEX_UNIT_SP)});addView(valueView.apply{maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,10,1,android.util.TypedValue.COMPLEX_UNIT_SP)})},LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(4)})}
    private fun greetingText():String{val h=java.time.LocalTime.now(ZoneId.of("Asia/Ho_Chi_Minh")).hour;val part=when(h){in 5..10->"sáng";in 11..13->"trưa";in 14..17->"chiều";else->"tối"};return "Chào buổi $part, ${name.ifBlank{login}}"}
    private fun appBar(title:String)=column(Color.TRANSPARENT).apply{setPadding(dp(16),dp(11),dp(16),dp(12));background=gradient(navy,accent,0);val identity=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL};if(!isRootScreen())identity.addView(ImageView(this@OperationsActivity).apply{setImageResource(R.drawable.ic_pp_back);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(7),dp(7),dp(7),dp(7));setOnClickListener{navigateBack()}},size(dp(36),dp(36)));identity.addView(txt(greetingText(),16f,Color.WHITE,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END},LinearLayout.LayoutParams(0,-2,1f).apply{if(!isRootScreen())marginStart=dp(3)});addView(identity,matchWrap());addView(gap(10));val statuses=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER};val net=txt("—",9f,Color.WHITE,true);networkStatusText=net;val syn=txt("—",9f,Color.WHITE,true);syncStatusText=syn;val svc=txt("—",9f,Color.WHITE,true);serviceStatusText=svc;statuses.addView(headerStatusChip(R.drawable.ic_pp_network,"Mạng",net),LinearLayout.LayoutParams(0,dp(44),1f).apply{marginEnd=dp(3)});statuses.addView(headerStatusChip(R.drawable.ic_pp_sync,"Đồng bộ",syn),LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(2);marginEnd=dp(2)});statuses.addView(headerStatusChip(R.drawable.ic_pp_service,"Dịch vụ",svc),LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3)});addView(statuses,matchWrap());refreshHeaderConnection()}
    private fun activeTab()=when(module){"STAFF"->"STAFF";"HISTORY"->"HISTORY";"SYNC"->"SYNC";"SETTINGS"->"SETTINGS";"ROLE_MODE"->"ROLE_MODE";else->"BUSINESS"}

    private fun bottomNav():LinearLayout=row(surface).apply{
        gravity=Gravity.CENTER;setPadding(dp(3),dp(5),dp(3),dp(5));background=outlineBg(surface,16);elevation=dp(8).toFloat();navRefs.clear()
        val items=mutableListOf(
            Triple(R.drawable.ic_pp_business,"Nghiệp vụ","BUSINESS"),
            Triple(R.drawable.ic_pp_staff,"Nhân sự","STAFF"),
            Triple(R.drawable.ic_pp_history,"Lịch sử","HISTORY"),
            Triple(R.drawable.ic_pp_sync,"Đồng bộ","SYNC"),
            Triple(R.drawable.ic_pp_settings,"Cài đặt","SETTINGS")
        )
        if(isActualSuper())items.add(Triple(R.drawable.ic_pp_settings,"Quyền","ROLE_MODE"))
        items.forEach{item->
            val iconView=ImageView(this@OperationsActivity).apply{setImageResource(item.first);setPadding(dp(4),dp(4),dp(4),dp(2))}
            val labelView=txt(item.second,7.2f,muted,item.third==activeTab()).apply{gravity=Gravity.CENTER;maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,9,1,android.util.TypedValue.COMPLEX_UNIT_SP)}
            val cell=column(Color.TRANSPARENT).apply{gravity=Gravity.CENTER;setPadding(dp(1),dp(2),dp(1),dp(2));addView(iconView,size(dp(30),dp(27)));addView(labelView);setOnClickListener{navigateTab(item.third)}}
            navRefs[item.third]=NavRefs(cell,iconView,labelView);addView(cell,LinearLayout.LayoutParams(0,-1,1f))
        };post{refreshBottomNav()}
    }

    private fun refreshBottomNav(){val active=activeTab();navRefs.forEach{(key,ref)->val chosen=key==active;ref.cell.background=if(chosen)round(ThemeManager.soft(this@OperationsActivity),10)else null;ref.icon.imageTintList=ColorStateList.valueOf(if(chosen)teal else muted);ref.label.setTextColor(if(chosen)teal else muted);ref.label.typeface=if(chosen)Typeface.DEFAULT_BOLD else Typeface.DEFAULT}}
    private fun navigateTab(target:String,remember:Boolean=true){
        val current=activeTab()
        if(target==current&&isRootScreen())return
        if(remember&&target!=current)tabHistory.addLast(current)
        module=target;initialMnv="";liveEmployeeMnv=""
        when(target){
            "BUSINESS"->businessHome()
            "STAFF"->staffScreen()
            "HISTORY"->historyScreen()
            "SYNC"->syncScreen()
            "SETTINGS"->settingsScreen()
            "ROLE_MODE"->if(isActualSuper())roleModeScreen() else businessHome()
        }
    }

    private fun roleModeScreen(){
        if(!isActualSuper()){module="BUSINESS";businessHome();return}
        module="ROLE_MODE";screenState="ROLE_MODE"
        val root=baseRoot("CHẾ ĐỘ QUYỀN");val body=body()
        body.addView(section("Quyền giao diện đang áp dụng"))
        body.addView(info("Đang hiển thị ứng dụng theo quyền: ${roleText(effectiveRole)}"))
        body.addView(gap(9))
        body.addView(primary("ÁP QUYỀN USER",teal){effectiveRole="USER";TopNotice.show(this,"Đã chuyển giao diện sang quyền USER.",TopNotice.Kind.SUCCESS);navigateTab("BUSINESS")},matchWrap())
        body.addView(gap(8))
        body.addView(primary("ÁP QUYỀN ADMIN",blue){effectiveRole="ADMIN";TopNotice.show(this,"Đã chuyển giao diện sang quyền ADMIN.",TopNotice.Kind.SUCCESS);navigateTab("BUSINESS")},matchWrap())
        body.addView(gap(8))
        body.addView(primary("QUAY VỀ QUYỀN SUPERADMIN",navy){effectiveRole="SUPERADMIN";TopNotice.show(this,"Đã quay về quyền SUPERADMIN.",TopNotice.Kind.SUCCESS);navigateTab("BUSINESS")},matchWrap())
        attach(root,body)
    }

    private fun sessionExpired(){
        api.clearSession()
        AlertDialog.Builder(this).setTitle("Phiên đăng nhập đã thay đổi").setMessage("Vui lòng đăng nhập lại để tiếp tục.").setCancelable(false).setPositiveButton("ĐĂNG NHẬP"){_,_->finishAffinity()}.show()
    }

    private fun handleAuth(r:BetaApiClient.Result):Boolean{if(r.code==401){api.clearSession();AlertDialog.Builder(this).setTitle("Phiên đăng nhập đã được thay thế").setMessage("Tài khoản đã đăng nhập ở thiết bị khác hoặc quyền tài khoản đã thay đổi.").setCancelable(false).setPositiveButton("OK"){_,_->finishAffinity()}.show();return true};return false}
    private fun showError(raw:String){val msg=when{raw.contains("PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST")->"Tình trạng PDA hiện tại không khớp lúc vào ca. Không thể RA CA. Phải thông báo cho Chuyên viên sự việc.";raw.contains("PDA_ENTRY_STATUS_MISSING_NOTIFY_SPECIALIST")->"Không xác định được tình trạng PDA lúc vào ca. Không thể RA CA. Phải thông báo cho Chuyên viên sự việc.";raw.contains("PDA_ENTRY_STATUS_STALE")->"Tình trạng PDA vừa thay đổi trên hệ thống. Chọn lại PDA trước khi VÀO CA.";raw.contains("DUPLICATE_USER_OVERRIDE_NOT_REQUIRED")->"User này hiện không thuộc nhóm đang dùng/đã dùng; hãy chọn từ danh sách thường.";raw.contains("PP_RESOURCE_CONFLICT")->"Tài nguyên vừa được người khác nhận. Tài nguyên cũ vẫn được giữ.";raw.contains("PP_USER_PICK_USED_TODAY")->"User Pick này đã được dùng trong ngày.";raw.contains("PP_USER_PACK_USED_TODAY")->"User Pack này đã được dùng trong ngày.";raw.contains("PP_LABOR_ALREADY_ACTIVE")->"Mã nhân viên đang có công nhật chưa hoàn thành.";raw.contains("PP_LABOR_NOT_ACTIVE")->"Mã nhân viên không có công nhật đang hoạt động.";raw.contains("CURRENT_PASSWORD_INVALID")->"Mật khẩu hiện tại không đúng.";raw.contains("PASSWORD_POLICY")->"Mật khẩu mới phải có ít nhất 8 ký tự.";raw.contains("EMAIL_INVALID")->"Địa chỉ mail không hợp lệ.";raw.contains("EMPLOYEE_NOT_FOUND")->"Không tìm thấy nhân sự.";raw.contains("STAFF_ACTIVE_SESSION")->"Nhân sự đang có phiên ACTIVE, chưa thể xóa.";raw.contains("FORBIDDEN")->"Tài khoản không có quyền thực hiện thao tác này.";else->raw};TopNotice.show(this,msg,TopNotice.Kind.ERROR)}

    private fun iconBubble(res:Int,color:Int)=FrameLayout(this).apply{
        background=round(ThemeManager.soft(this@OperationsActivity),14)
        addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(color);setPadding(dp(9),dp(9),dp(9),dp(9))},FrameLayout.LayoutParams(-1,-1))
    }
    private fun businessIconBubble(res:Int):FrameLayout{
        val colors=when(res){
            R.drawable.ic_pp_scan->intArrayOf(teal,accent)
            R.drawable.ic_pp_pda_exchange->intArrayOf(Color.rgb(2,132,199),Color.rgb(14,165,233))
            R.drawable.ic_pp_drop_receive->intArrayOf(Color.rgb(234,88,12),Color.rgb(249,115,22))
            R.drawable.ic_pp_report->intArrayOf(Color.rgb(124,58,237),Color.rgb(168,85,247))
            R.drawable.ic_pp_task->intArrayOf(Color.rgb(37,99,235),Color.rgb(14,165,233))
            R.drawable.ic_pp_resource->intArrayOf(Color.rgb(5,150,105),Color.rgb(16,185,129))
            R.drawable.ic_pp_ccdc->intArrayOf(Color.rgb(71,85,105),Color.rgb(100,116,139))
            R.drawable.ic_pp_document->intArrayOf(Color.rgb(79,70,229),Color.rgb(99,102,241))
            else->intArrayOf(Color.rgb(6,182,212),Color.rgb(14,165,233))
        }
        return FrameLayout(this).apply{
            background=GradientDrawable(GradientDrawable.Orientation.TL_BR,colors).apply{shape=GradientDrawable.OVAL}
            elevation=dp(5).toFloat()
            addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(13),dp(13),dp(13),dp(13))},FrameLayout.LayoutParams(-1,-1))
        }
    }
    private fun businessCard(iconRes:Int,title:String,sub:String,enabled:Boolean=true,click:()->Unit)=column(surface).apply{
        gravity=Gravity.CENTER_HORIZONTAL
        setPadding(dp(12),dp(14),dp(12),dp(12))
        background=outlineBg(surface,20)
        elevation=if(enabled)dp(5).toFloat() else 0f
        alpha=if(enabled)1f else .38f
        isEnabled=enabled
        addView(businessIconBubble(iconRes),size(dp(58),dp(58)))
        addView(gap(9))
        addView(txt(title,13.5f,ink,true).apply{gravity=Gravity.CENTER;maxLines=2;ellipsize=android.text.TextUtils.TruncateAt.END})
        addView(gap(5))
        addView(View(this@OperationsActivity).apply{background=round(teal,2)},size(dp(28),dp(3)))
        addView(gap(6))
        addView(txt(sub,9.8f,muted,false).apply{
            gravity=Gravity.CENTER
            maxLines=3
            ellipsize=android.text.TextUtils.TruncateAt.END
            setAutoSizeTextTypeUniformWithConfiguration(8,10,1,android.util.TypedValue.COMPLEX_UNIT_SP)
        },LinearLayout.LayoutParams(-1,0,1f))
        if(enabled)setOnClickListener{click()} else setOnClickListener(null)
    }

    private fun businessRow(a:View,b:View)=row(bg).apply{
        addView(a,LinearLayout.LayoutParams(0,dp(188),1f).apply{marginEnd=dp(6)})
        addView(b,LinearLayout.LayoutParams(0,dp(188),1f).apply{marginStart=dp(6)})
    }

    private fun iconActionButton(res:Int,color:Int,desc:String,click:()->Unit)=FrameLayout(this).apply{
        contentDescription=desc
        background=round(ThemeManager.soft(this@OperationsActivity),10)
        setOnClickListener{click()}
        addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(color);setPadding(dp(8),dp(8),dp(8),dp(8))},FrameLayout.LayoutParams(-1,-1))
    }

    private fun employeeCard(e:JSONObject)=column(surface).apply{setPadding(dp(10),dp(8),dp(10),dp(8));background=outlineBg(surface,11);addView(txt("${e.optString("mnv")} • ${e.optString("full_name")}",13.2f,navy,true));addView(txt("${dash(e.optString("main_position"))} • ${dash(e.optString("supplier"))}",9.5f,ink,false));addView(txt("${dash(e.optString("department"))} • Site ${dash(e.optString("site"))} • Kho ${dash(e.optString("warehouse"))}",9.1f,muted,false))}
    private fun listCard(title:String,sub:String)=column(surface).apply{setPadding(dp(10),dp(7),dp(10),dp(7));background=outlineBg(surface,10);addView(txt(title,11.6f,ink,true));addView(gap(1));addView(txt(sub,9.3f,muted,false))}
    private fun metric(title:String,value:String,color:Int)=column(surface).apply{setPadding(dp(8),dp(7),dp(8),dp(7));background=outlineBg(surface,10);addView(txt(title,9.7f,color,true));addView(gap(1));addView(txt(value,11.8f,ink,true))}
    private fun jsonMapCard(title:String,j:JSONObject?)=column(surface).apply{setPadding(dp(14),dp(11),dp(14),dp(11));background=outlineBg(surface,14);addView(txt(title,11f,navy,true));if(j==null||j.length()==0)addView(txt("Chưa có dữ liệu",10f,muted,false))else{val keys=j.keys();while(keys.hasNext()){val k=keys.next();addView(txt("$k: ${j.optInt(k)}",10.5f,ink,false))}}}
    private fun details(items:List<Pair<String,String>>)=column(surface).apply{setPadding(dp(9),dp(6),dp(9),dp(6));background=outlineBg(surface,10);items.forEach{(k,v)->addView(row(surface).apply{addView(txt(k,9.5f,muted,false),LinearLayout.LayoutParams(0,-2,.45f));addView(txt(if(v.isBlank())"—" else v,9.7f,ink,true).apply{gravity=Gravity.END},LinearLayout.LayoutParams(0,-2,.55f));setPadding(0,dp(2),0,dp(2))})}}
    private fun section(v:String)=row(bg).apply{
        gravity=Gravity.CENTER_VERTICAL;setPadding(0,dp(8),0,dp(3))
        addView(ImageView(this@OperationsActivity).apply{setImageResource(sectionIconRes(v));imageTintList=ColorStateList.valueOf(teal)},size(dp(20),dp(20)))
        addView(txt(v,12.2f,navy,true),LinearLayout.LayoutParams(-2,-2).apply{marginStart=dp(5)})
    }
    private fun sectionIconRes(v:String)=when{
        v.contains("Tài khoản",true)->R.drawable.ic_pp_account
        v.contains("Giao diện",true)->R.drawable.ic_pp_palette
        v.contains("Đồng bộ",true)->R.drawable.ic_pp_sync
        v.contains("Cập nhật",true)->R.drawable.ic_pp_update
        v.contains("Nhật ký",true)->R.drawable.ic_pp_log
        v.contains("Thiết bị",true)->R.drawable.ic_pp_device
        v.contains("Ứng dụng",true)->R.drawable.ic_pp_device
        v.contains("Google Sheet",true)->R.drawable.ic_pp_sync
        v.contains("Service",true)->R.drawable.ic_pp_service
        v.contains("PDA",true)->R.drawable.ic_pp_device
        else->R.drawable.ic_pp_task
    }
    private fun status(v:String,fg:Int,c:Int)=txt(v,11.3f,fg,true).apply{gravity=Gravity.CENTER;setPadding(dp(10),dp(10),dp(10),dp(10));background=round(c,12)}
    private fun info(v:String)=txt(v,9.6f,muted,false).apply{setPadding(dp(10),dp(7),dp(10),dp(7));background=outlineBg(ThemeManager.soft(this@OperationsActivity),10)}
    private fun scanField(h:String,numeric:Boolean,heightDp:Int)=input(h,false).apply{
        if(numeric){
            inputType=InputType.TYPE_CLASS_NUMBER
            keyListener=DigitsKeyListener.getInstance("0123456789")
            imeOptions=EditorInfo.IME_ACTION_DONE
        }else{
            inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            imeOptions=EditorInfo.IME_ACTION_SEARCH
        }
        setSingleLine(false)
        minLines=2
        maxLines=2
        setHorizontallyScrolling(false)
        gravity=Gravity.CENTER_VERTICAL
        minHeight=dp(heightDp)
        maxHeight=dp(heightDp)
        textSize=12.4f
        setHintTextColor(Color.rgb(100,116,139))
        setPadding(dp(12),dp(7),dp(12),dp(7))
        setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_pp_scan,0,0,0)
        compoundDrawableTintList=ColorStateList.valueOf(teal)
        compoundDrawablePadding=dp(9)
        background=GradientDrawable().apply{
            setColor(ThemeManager.soft(this@OperationsActivity))
            setStroke(dp(1),teal)
            cornerRadius=dp(14).toFloat()
        }
        elevation=0f
    }
    private fun mnvInput(h:String)=scanField(h,true,72)
    private fun scanSearchInput(h:String)=scanField(h,false,72)
    private fun bindScannerEnter(v:EditText,submit:()->Unit){v.setOnEditorActionListener{_,id,_->if(id==EditorInfo.IME_ACTION_DONE||id==EditorInfo.IME_ACTION_GO||id==EditorInfo.IME_ACTION_SEARCH){submit();true}else false};v.setOnKeyListener{_,key,event->if(key==KeyEvent.KEYCODE_ENTER&&event.action==KeyEvent.ACTION_UP){submit();true}else false}}
    private fun segmentedChoice(items:List<Pair<String,String>>,initial:String,onChanged:(String)->Unit):LinearLayout{
        val host=row(bg);val buttons=mutableListOf<Button>();var selected=initial
        fun paint(){buttons.forEachIndexed{i,b->val on=items[i].second==selected;b.setTextColor(if(on)Color.WHITE else navy);b.background=if(on)gradient(teal,darken(teal),12) else outlineBg(surface,12);b.elevation=if(on)dp(2).toFloat() else 0f}}
        items.forEachIndexed{i,item->val b=Button(this).apply{text=item.first;textSize=10.5f;isAllCaps=false;typeface=Typeface.DEFAULT_BOLD;minHeight=dp(46);setPadding(dp(3),0,dp(3),0);setOnClickListener{selected=item.second;paint();onChanged(selected)}};buttons.add(b);host.addView(b,LinearLayout.LayoutParams(0,dp(46),1f).apply{if(i>0)marginStart=dp(3);if(i<items.lastIndex)marginEnd=dp(3)})};paint();return host
    }
    private fun resolvePdaObject(pdas:JSONArray,rawValue:String):JSONObject?{
        val raw=rawValue.trim();val candidate=raw.substringBefore(" • ").trim();val hits=mutableListOf<JSONObject>();for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(serial.isBlank())continue;if(candidate==serial||candidate==last5||(raw.contains(serial)&&raw.contains("Tình trạng:")))hits.add(p)};return hits.distinctBy{it.optString("serial")}.singleOrNull()
    }
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

    private fun naturalUserCompare(aRaw:String,bRaw:String):Int{
        val a=aRaw.trim();val b=bRaw.trim();val rx=Regex("^(.*?)(\\d+)$")
        val am=rx.matchEntire(a);val bm=rx.matchEntire(b)
        if(am!=null&&bm!=null){
            val ap=am.groupValues[1].lowercase();val bp=bm.groupValues[1].lowercase();val prefix=ap.compareTo(bp)
            if(prefix!=0)return prefix
            val an=am.groupValues[2].toLongOrNull();val bn=bm.groupValues[2].toLongOrNull()
            if(an!=null&&bn!=null&&an!=bn)return an.compareTo(bn)
        }
        return a.compareTo(b,ignoreCase=true)
    }
    private fun <T> sortedByNaturalUser(items:List<T>,value:(T)->String):List<T> = items.sortedWith(Comparator{a,b->naturalUserCompare(value(a),value(b))})
    private fun compactReissueButton(label:String,enabled:Boolean,onClick:()->Unit)=smallButton(label,orange).apply{
        isAllCaps=false;textSize=8.6f;setSingleLine(true);setPadding(dp(3),0,dp(3),0);isEnabled=enabled;alpha=if(enabled)1f else .45f;setOnClickListener{if(isEnabled)onClick()}
    }

    private fun pdaInput(pdas:JSONArray,currentSerial:String="",onSelected:(JSONObject?)->Unit={}):AutoCompleteTextView{
        val labels=mutableListOf<String>()
        for(i in 0 until pdas.length()){
            val p=pdas.optJSONObject(i)?:continue
            val serial=p.optString("serial").trim()
            val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)}
            val status=p.optString("status").trim()
            if(serial.isNotBlank()&&last5.isNotBlank())labels.add("$last5 • $serial • Tình trạng: ${status.ifBlank{"—"}}")
        }
        val field=AutoCompleteTextView(this);var selectedLast5="";var internal=false
        field.hint="Gõ 5 số cuối Seri PDA";field.threshold=1;field.textSize=13f;field.setTextColor(ink);field.setHintTextColor(Color.rgb(153,163,176));field.inputType=InputType.TYPE_CLASS_TEXT;field.setPadding(dp(13),dp(10),dp(13),dp(10));field.minHeight=dp(50);field.background=outline();field.setAdapter(ArrayAdapter(this,android.R.layout.simple_dropdown_item_1line,labels))
        field.setOnItemClickListener{parent,_,pos,_->val label=parent.getItemAtPosition(pos).toString();val p=resolvePdaObject(pdas,label);if(p!=null){selectedLast5=p.optString("last5").trim().ifBlank{p.optString("serial").takeLast(5)};internal=true;field.setText(selectedLast5,false);field.setSelection(field.text.length);field.tag=JSONObject(p.toString());internal=false;onSelected(JSONObject(p.toString()))}}
        field.addTextChangedListener(object:TextWatcher{override fun beforeTextChanged(s:CharSequence?,st:Int,c:Int,a:Int)=Unit;override fun onTextChanged(s:CharSequence?,st:Int,b:Int,c:Int)=Unit;override fun afterTextChanged(e:Editable?){if(!internal&&selectedLast5.isNotBlank()&&e?.toString()?.trim()!=selectedLast5){selectedLast5="";field.tag=null;onSelected(null)}}})
        field.setOnClickListener{field.showDropDown()}
        if(currentSerial.isNotBlank()){for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;if(p.optString("serial")==currentSerial){selectedLast5=p.optString("last5").trim().ifBlank{currentSerial.takeLast(5)};internal=true;field.setText(selectedLast5,false);field.tag=JSONObject(p.toString());internal=false;onSelected(JSONObject(p.toString()));break}}}
        return field
    }
    private fun resolvePda(pdas:JSONArray,rawValue:String):String?=resolvePdaObject(pdas,rawValue)?.optString("serial")?.takeIf{it.isNotBlank()}
    private fun input(h:String,password:Boolean)=EditText(this).apply{hint=h;textSize=13.0f;setTextColor(ink);setHintTextColor(Color.rgb(148,163,184));inputType=if(password)InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT;setPadding(dp(11),dp(8),dp(11),dp(8));minHeight=dp(46);background=outline();elevation=0f}
    private fun labelled(l:String,v:View)=column(bg).apply{addView(txt(l,9.6f,muted,true));addView(gap(3));addView(v,matchWrap())}
    private fun spinner(items:Array<String>)=Spinner(this).apply{adapter=ArrayAdapter(this@OperationsActivity,android.R.layout.simple_spinner_dropdown_item,items);setPadding(dp(9),dp(3),dp(9),dp(3));minimumHeight=dp(44);background=outline();elevation=0f}
    private fun primary(t:String,c:Int,click:()->Unit)=Button(this).apply{text=t;textSize=11.5f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;minHeight=dp(46);background=gradient(c,darken(c),12);elevation=0f;setOnClickListener{click()}}
    private fun smallButton(t:String,c:Int)=Button(this).apply{text=t;textSize=9.5f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;background=round(c,10);setPadding(dp(4),0,dp(4),0)}
    private fun host(content:View):View{
        val root=EdgeSwipeBackLayout(this){navigateBack()}.apply{setBackgroundColor(bg)}
        val contentFrame=FrameLayout(this).apply{addView(content,FrameLayout.LayoutParams(-1,-1))}
        val navFrame=FrameLayout(this).apply{setPadding(dp(8),0,dp(8),0);addView(bottomNav(),FrameLayout.LayoutParams(-1,-1))}
        contentHost=contentFrame;navHost=navFrame
        root.addView(contentFrame,FrameLayout.LayoutParams(-1,-1).apply{bottomMargin=dp(86)})
        root.addView(navFrame,FrameLayout.LayoutParams(-1,dp(62),Gravity.BOTTOM).apply{bottomMargin=dp(20)})
        root.addView(txt(FOOTER,7.2f,Color.rgb(113,122,136),false).apply{gravity=Gravity.CENTER;maxLines=1},FrameLayout.LayoutParams(-1,dp(18),Gravity.BOTTOM))
        root.setOnApplyWindowInsetsListener{v,i->val top:Int;val bottom:Int;if(Build.VERSION.SDK_INT>=30){top=i.getInsets(WindowInsets.Type.statusBars()).top;bottom=i.getInsets(WindowInsets.Type.navigationBars()).bottom}else{@Suppress("DEPRECATION")val tt=i.systemWindowInsetTop;@Suppress("DEPRECATION")val bb=i.systemWindowInsetBottom;top=tt;bottom=bb};v.setPadding(0,top+dp(2),0,bottom+dp(1));i}
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
        if(values.isEmpty())values.add("Chưa cấu hình")
        return spinner(values.toTypedArray()).also{sp->selectByValue(sp,values,if(current.isBlank()&&allowBlank)"—" else current)}
    }
    private fun catalogSelection(sp:Spinner)=sp.selectedItem?.toString().orEmpty().let{if(it=="—")"" else it}
    private fun selectByValue(sp:Spinner,values:List<String>,target:String){val i=values.indexOf(target);if(i>=0)sp.setSelection(i)}
    private fun formatIso(v:String):String{if(v.isBlank()||v=="null")return "—";return try{Instant.parse(v).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("HH:mm:ss dd/MM/yyyy"))}catch(_:Throwable){v}}
    private fun greeting():String{
        val hour=java.util.Calendar.getInstance().get(java.util.Calendar.HOUR_OF_DAY)
        return when(hour){in 5..10->"Chào buổi sáng";in 11..12->"Chào buổi trưa";in 13..17->"Chào buổi chiều";else->"Chào buổi tối"}
    }
    private fun normalizePhone(v:String):String{
        val digits=v.filter{it.isDigit()}
        return if(digits.length==9&&!digits.startsWith("0"))"0$digits" else digits
    }
    private fun historyIcon(action:String)=when(action){
        "enter","exit"->R.drawable.ic_pp_scan
        "labor_start","labor_finish"->R.drawable.ic_pp_task
        "resource_change"->R.drawable.ic_pp_resource
        "staff_upsert","staff_delete"->R.drawable.ic_pp_staff
        "change_password","change_email","account_upsert","account_status"->R.drawable.ic_pp_account
        "diagnostic_log"->R.drawable.ic_pp_log
        else->R.drawable.ic_pp_history
    }
    private fun historyFriendlyDetail(action:String,raw:String,ok:Boolean):String{
        if(ok)return when(action){
            "enter"->"Đã ghi nhận vào ca.";"exit"->"Đã ghi nhận ra ca.";"resource_change"->"Đã cập nhật tài nguyên."
            "labor_start"->"Đã bắt đầu công nhật.";"labor_finish"->"Đã hoàn thành công nhật."
            "staff_upsert"->"Đã lưu thông tin nhân sự.";"staff_delete"->"Đã xóa nhân sự.";"diagnostic_log"->"Đã gửi báo lỗi."
            "change_password"->"Đã đổi mật khẩu.";"change_email"->"Đã đổi mail.";"account_upsert"->"Đã cập nhật tài khoản.";"account_status"->"Đã đổi trạng thái tài khoản."
            else->"Đã hoàn tất thao tác."
        }
        val e=raw.uppercase()
        return when{
            e.contains("RESOURCE_CONFLICT")->"Tài nguyên vừa được người khác nhận. Hãy chọn tài nguyên khác."
            e.contains("USER_PICK_USED_TODAY")->"User Pick này đã được sử dụng trong ngày."
            e.contains("USER_PACK_USED_TODAY")->"User Pack này đã được sử dụng trong ngày."
            e.contains("LABOR_ALREADY_ACTIVE")->"Nhân sự đang có công nhật chưa hoàn thành."
            e.contains("UNAUTHORIZED")->"Phiên đăng nhập đã thay đổi. Vui lòng đăng nhập lại."
            e.contains("FORBIDDEN")->"Tài khoản không có quyền thực hiện thao tác này."
            e.contains("EMPLOYEE_NOT_FOUND")->"Không tìm thấy nhân sự."
            raw.isBlank()->"Thao tác chưa hoàn tất. Vui lòng thử lại."
            else->"Thao tác chưa hoàn tất. Kiểm tra kết nối hoặc dữ liệu rồi thử lại."
        }
    }
    private fun roleText(v:String)=when(v){"SUPERADMIN"->"Superadmin";"ADMIN"->"Admin";"USER"->"Điều phối";else->v}
    private fun workText(v:String)=when(v){"PICK"->"Pick";"PACK"->"Pack";else->"Không"}
    private fun foldLocal(v:String)=java.text.Normalizer.normalize(v,java.text.Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"),"").uppercase().trim()
    private fun humanBytes(bytes:Long):String=when{bytes<1024L->"$bytes B";bytes<1024L*1024L->String.format(java.util.Locale.US,"%.1f KB",bytes/1024.0);bytes<1024L*1024L*1024L->String.format(java.util.Locale.US,"%.1f MB",bytes/(1024.0*1024.0));else->String.format(java.util.Locale.US,"%.2f GB",bytes/(1024.0*1024.0*1024.0))}
    private fun dash(v:String)=v.takeIf{it.isNotBlank()&&it!="null"}?:"—"
    private fun txt(v:String,s:Float,c:Int,b:Boolean)=TextView(this).apply{text=v;textSize=s;setTextColor(c);typeface=if(b)Typeface.DEFAULT_BOLD else Typeface.DEFAULT}
    private fun column(c:Int)=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setBackgroundColor(c)}
    private fun row(c:Int)=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL;setBackgroundColor(c)}
    private fun gap(h:Int)=Space(this).apply{layoutParams=size(1,dp(((h*9)+5)/10))}
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
