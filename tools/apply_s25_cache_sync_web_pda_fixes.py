#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
FG = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/ForegroundSyncCoordinator.kt"
PROJ = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/PdaLocalProjection.kt"
MARK = "S25_CACHE_FIRST_FALLBACK_SYNC"


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"S25 block start {label!r} not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"S25 block end {label!r} not found")
    return text[:start] + replacement + text[end:]


# GAS fallback intentionally leaves retention_floor blank for legacy Beta17 recovery clients.
# Modern clients must use server_retention_floor so the canonical day snapshots still hydrate SQLite.
s = FG.read_text(encoding="utf-8")
if "S25_FALLBACK_RETENTION_COMPAT" not in s:
    old = '                                retentionFloor = body.optString("retention_floor"),\n'
    new = '                                // S25_FALLBACK_RETENTION_COMPAT: legacy GAS may blank retention_floor.\n                                retentionFloor = body.optString("retention_floor").ifBlank { body.optString("server_retention_floor") },\n'
    if s.count(old) != 1:
        raise SystemExit(f"S25 retention anchor mismatch: {s.count(old)}")
    s = s.replace(old, new, 1)
    FG.write_text(s, encoding="utf-8")

# Complete the local employee projection with OPEN labor and pending labor overlays.
s = PROJ.read_text(encoding="utf-8")
if "S25_LOCAL_LABOR_OVERLAY" not in s:
    s = replace_block(
        s,
        "    fun employeeContext(context: Context, mnvRaw: String): JSONObject? {",
        "    fun resourceOptions(context: Context, mnvRaw: String): JSONObject {",
        '''    // S25_LOCAL_LABOR_OVERLAY: session + labor context is rendered without waiting for network.
    fun employeeContext(context: Context, mnvRaw: String): JSONObject? {
        val mnv = mnvRaw.trim()
        if (mnv.isBlank()) return null
        val employee = MasterDataCache.employee(context, mnv) ?: return null
        val store = OperationalDataStore(context.applicationContext)
        val businessDate = store.latestBusinessDate()
        val day = store.loadDay(businessDate) ?: return null
        val sessions = day.optJSONArray("sessions") ?: JSONArray()
        var session: JSONObject? = null
        for (i in 0 until sessions.length()) {
            val candidate = sessions.optJSONObject(i) ?: continue
            if (candidate.optString("mnv") == mnv) { session = JSONObject(candidate.toString()); break }
        }
        var state = when (session?.optString("state")?.uppercase()) {
            "ACTIVE" -> "ACTIVE"
            "ENDED" -> "ENDED"
            else -> "NOT_ENTERED"
        }
        val labor = day.optJSONArray("labor") ?: JSONArray()
        var activeLabor: JSONObject? = null
        for (i in 0 until labor.length()) {
            val item = labor.optJSONObject(i) ?: continue
            if (item.optString("mnv") != mnv) continue
            val open = item.optString("state").uppercase() in setOf("OPEN", "ACTIVE") || item.optString("end_at").isBlank()
            if (open) activeLabor = JSONObject(item.toString())
        }
        var reconciliationState = "CONFIRMED"
        var provisionalExclusive = false
        for (item in store.pendingMutations(500)) {
            val body = item.body
            val payload = body.optJSONObject("payload") ?: body
            val eventDate = payload.optString("business_date").ifBlank { body.optString("business_date") }
            if (eventDate.isNotBlank() && eventDate != businessDate) continue
            if (payload.optString("mnv") != mnv) continue
            val action = body.optString("action").ifBlank { payload.optString("action") }
            when (action) {
                "enter" -> {
                    session = (session ?: JSONObject()).apply {
                        put("mnv", mnv); put("state", "ACTIVE")
                        copyIfPresent(payload, this, "shift", "work_choice", "pda_serial", "user_pick", "pack_table", "user_pack")
                    }
                    state = "ACTIVE"
                }
                "exit" -> {
                    session = (session ?: JSONObject()).apply { put("mnv", mnv); put("state", "ENDED") }
                    state = "ENDED"
                }
                "resource_change" -> {
                    session = (session ?: JSONObject()).apply {
                        put("mnv", mnv)
                        copyIfPresent(payload, this, "work_choice", "pda_serial", "user_pick", "pack_table", "user_pack")
                    }
                }
                "labor_start" -> {
                    activeLabor = JSONObject().apply {
                        put("mnv", mnv); put("state", "OPEN")
                        copyIfPresent(payload, this, "labor_type", "time_marker", "note", "deduct_staff", "shift")
                    }
                }
                "labor_finish" -> activeLabor = null
            }
            reconciliationState = "LOCAL_PENDING"
            provisionalExclusive = provisionalExclusive || item.exclusive
        }
        return JSONObject()
            .put("ok", true)
            .put("source", "PDA_SQLITE")
            .put("business_date", day.optString("business_date", businessDate))
            .put("day_revision", day.optLong("day_revision", 0L))
            .put("employee", employee)
            .put("state", state)
            .put("session", session ?: JSONObject.NULL)
            .put("active_labor", activeLabor ?: JSONObject.NULL)
            .put("reconciliation_state", reconciliationState)
            .put("provisional", provisionalExclusive)
    }

''',
        "local employee/labor projection",
    )
    PROJ.write_text(s, encoding="utf-8")

s = OPS.read_text(encoding="utf-8")
if MARK not in s:
    class_anchor = "class OperationsActivity : Activity() {\n"
    if s.count(class_anchor) != 1:
        raise SystemExit("S25 OperationsActivity class anchor mismatch")
    s = s.replace(class_anchor, class_anchor + f"    // {MARK}\n", 1)

    # Cached session is authoritative for immediate UX. A revision sync is requested in background;
    # its atomic SQLite save will re-render the screen through OperationalSyncEngine's listener.
    s = replace_block(
        s,
        "    private fun loadEmployee(mnv: String, button: Button? = null) {",
        "    private fun renderCachedEmployee(e: JSONObject) {",
        '''    private fun loadEmployee(mnv: String, button: Button? = null) {
        val localShown=renderLocalEmployee(mnv)
        if(localShown){
            button?.isEnabled=true;button?.text="KIỂM TRA"
            foregroundSync.requestSync()
            return
        }
        val cached=MasterDataCache.employee(this,mnv)
        if(cached!=null && screenState=="SCAN")renderCachedEmployee(cached)
        api.call("employee_context",JSONObject().put("mnv",mnv).put("include_options",false).put("include_labor",false)){result->runOnUiThread{
            button?.isEnabled=true;button?.text="KIỂM TRA"
            if(result.code==401){sessionExpired();return@runOnUiThread}
            if(!result.ok){showError(result.error?:"Không kiểm tra được MNV");return@runOnUiThread}
            val ctx=result.json?:JSONObject()
            if(ctx.optString("state")=="NOT_ENTERED"){
                val localOptions=PdaLocalProjection.resourceOptions(this@OperationsActivity,mnv)
                val pdas=localOptions.optJSONArray("pdas")
                if(pdas!=null)renderEmployee(ctx,localOptions)
                else api.call("master_options",JSONObject().put("mnv",mnv)){masters->runOnUiThread{
                    if(masters.code==401){sessionExpired();return@runOnUiThread}
                    renderEmployee(ctx,masters.json?:JSONObject())
                }}
            }else renderEmployee(ctx,null)
        }}
    }

''',
        "cache-first employee scan",
    )

    # Labor scan uses the same SQLite projection, including active_labor overlay. Remote lookup is
    # cache-miss recovery only; normal hot scans never block on Google/Service.
    s = replace_block(
        s,
        "    private fun laborHome(){",
        "    private fun showLaborContext(ctx:JSONObject, masters:JSONObject){",
        '''    private fun laborHome(){
        screenState="LABOR_HOME"
        if(!isAdmin()){simpleMessage("CÔNG NHẬT","Chức năng Công nhật dành cho ADMIN/SUPERADMIN theo phân quyền hiện tại.");return}
        val root=baseRoot("CÔNG NHẬT");val body=body()
        val mnv=mnvInput("MNV").apply{setText(initialMnv)};body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(5))
        var busy=false
        fun submit(){
            val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập MNV.",TopNotice.Kind.WARNING);return};if(busy)return
            val local=PdaLocalProjection.employeeContext(this,v)
            if(local!=null){
                showLaborContext(local,MasterDataCache.snapshot(this)?:JSONObject())
                foregroundSync.requestSync()
                return
            }
            busy=true
            api.call("employee_context",JSONObject().put("mnv",v).put("include_labor",true).put("include_options",false)){r->runOnUiThread{
                busy=false;if(handleAuth(r))return@runOnUiThread
                if(!r.ok){showError(r.error?:"Không kiểm tra được MNV");return@runOnUiThread}
                showLaborContext(r.json?:JSONObject(),MasterDataCache.snapshot(this@OperationsActivity)?:JSONObject())
            }}
        }
        bindScannerEnter(mnv){submit()};if(initialMnv.isNotBlank())mnv.post{submit()};attach(root,body);mnv.requestFocus()
    }

''',
        "cache-first labor scan",
    )

    # Resource editor reads session and resource occupancy locally; revision sync runs after screen
    # render and may refresh atomically if another PDA changed the day.
    s = replace_block(
        s,
        "    private fun resourceHome(){",
        "    private fun showResourceEditor(ctx:JSONObject,masters:JSONObject){",
        '''    private fun resourceHome(){
        screenState="RESOURCE_HOME"
        val root=baseRoot("TÀI NGUYÊN");val body=body()
        val mnv=mnvInput("MNV").apply{setText(initialMnv)};body.addView(labelled("Mã nhân viên",mnv));var busy=false
        fun submit(){
            val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập MNV.",TopNotice.Kind.WARNING);return};if(busy)return
            val local=PdaLocalProjection.employeeContext(this,v)
            if(local!=null){
                if(local.optString("state")!="ACTIVE"){showError("MNV phải đang trong phiên ACTIVE.");return}
                showResourceEditor(local,PdaLocalProjection.resourceOptions(this,v))
                foregroundSync.requestSync()
                return
            }
            busy=true
            api.call("employee_context",JSONObject().put("mnv",v)){r->runOnUiThread{
                if(handleAuth(r)){busy=false;return@runOnUiThread}
                if(!r.ok){busy=false;showError(r.error?:"Không kiểm tra được MNV");return@runOnUiThread}
                if(r.json?.optString("state")!="ACTIVE"){busy=false;showError("MNV phải đang trong phiên ACTIVE.");return@runOnUiThread}
                api.call("master_options",JSONObject().put("mnv",v)){m->runOnUiThread{busy=false;if(handleAuth(m))return@runOnUiThread;showResourceEditor(r.json?:JSONObject(),m.json?:JSONObject())}}
            }}
        }
        bindScannerEnter(mnv){submit()};if(initialMnv.isNotBlank())mnv.post{submit()};attach(root,body);mnv.requestFocus()
    }

''',
        "cache-first resource scan",
    )

    # History stays local-only for rendering. Entry triggers a non-blocking revision reconcile so a
    # second PDA's committed actions appear after the snapshot save, without a loading dependency.
    hist_anchor = '        val root=baseRoot("LỊCH SỬ CHUNG");val body=body();val summaryBox=column(bg);val box=column(bg)\n'
    if hist_anchor in s:
        s = s.replace(hist_anchor, hist_anchor + '        foregroundSync.requestSync()\n', 1)

    # Make the status wording explicit: Google is an authority fallback, not the Cloudflare Service.
    s = s.replace('mode=="GOOGLE_FALLBACK"||route=="GAS_COMPAT"->"Google Drive"', 'mode=="GOOGLE_FALLBACK"||route=="GAS_COMPAT"->"Google dự phòng"')

    # Replace the compact sync card with an owner-useful project-wide diagnostic dashboard. This is
    # still local-first: opening the screen never waits for a network request.
    s = replace_block(
        s,
        "    private fun syncScreen(){",
        "    private fun settingsScreen(){",
        '''    private fun syncScreen(){
        module="SYNC";screenState="SYNC"
        val root=baseRoot("ĐỒNG BỘ");val body=body();val state=info("Đang đọc trạng thái đồng bộ trên PDA...");val detailsBox=column(bg)
        body.addView(state,matchWrap());body.addView(gap(8));body.addView(detailsBox,matchWrap())
        foregroundSync.requestSync()
        val handler=android.os.Handler(android.os.Looper.getMainLooper())
        val ticker=object:Runnable{
            override fun run(){
                if(screenState!="SYNC")return
                val net=DeviceNetworkStatus.snapshot(this@OperationsActivity)
                val d=SyncDirectionTracker.snapshot()
                val rt=api.runtimeStatus()
                val mode=rt.optString("authority_mode").ifBlank{operationalStore.authorityMode()}
                val route=rt.optString("route")
                val serviceUrl=rt.optString("service_url")
                val dates=runCatching{operationalStore.availableDates()}.getOrDefault(emptyList())
                val revisions=runCatching{operationalStore.revisions()}.getOrDefault(emptyMap())
                val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(0)
                val review=runCatching{operationalStore.conflicts(100).size}.getOrDefault(0)
                val master=MasterDataCache.snapshot(this@OperationsActivity)
                val masterRev=master?.optLong("master_revision",0L)?:0L
                val staff=MasterDataCache.staffCount(this@OperationsActivity)
                val hot=dates.take(2).joinToString(" • ").ifBlank{"Chưa có"}
                val window=dates.take(7).joinToString(" • ").ifBlank{"Chưa có"}
                val revText=dates.take(7).joinToString(" • "){x->"$x:${revisions[x]?:0}"}.ifBlank{"Chưa có"}
                val source=when(mode){"SERVICE_PRIMARY"->"Cloudflare / D1";"GOOGLE_FALLBACK"->"Google dự phòng";"RECONCILING"->"Đang đối soát";else->mode.ifBlank{"Chưa xác định"}}
                val foregroundMode=if(mode=="SERVICE_PRIMARY")"WebSocket thay đổi + kéo delta" else "Đồng bộ revision từ nguồn dự phòng"
                val fcm=when{
                    !M2Firebase.configured()->"Chưa cấu hình"
                    M2Firebase.registeredToken(this@OperationsActivity).isNotBlank()->"Đã đăng ký wake nền"
                    M2Firebase.pendingToken(this@OperationsActivity).isNotBlank()->"Có token • chờ đăng ký Service"
                    else->"Đang lấy token"
                }
                val lastError=rt.optString("last_error").ifBlank{"Không có"}
                detailsBox.removeAllViews()
                detailsBox.addView(section("TRẠNG THÁI HIỆN TẠI"))
                detailsBox.addView(details(listOf(
                    "Mạng" to net.header(lastLatencyMs),
                    "Internet xác thực" to if(net.validated)"Có" else if(net.hasInternet)"Đang xác nhận" else "Không",
                    "Nguồn ghi hiện tại" to source,
                    "Đường kết nối" to route.ifBlank{"Đang xác định"},
                    "Cloudflare Service" to if(serviceUrl.isNotBlank())"Đã discovery" else "Chưa discovery",
                    "Đồng bộ foreground" to foregroundMode,
                    "Wake background" to fcm,
                    "Tải lên" to formatRate(d.uploadBps),
                    "Tải xuống" to formatRate(d.downloadBps),
                    "Dữ liệu chờ gửi" to pending.toString(),
                    "Cần rà soát" to review.toString()
                )))
                detailsBox.addView(gap(8));detailsBox.addView(section("BỘ NHỚ CỤC BỘ PDA"))
                detailsBox.addView(details(listOf(
                    "Phiên nghiệp vụ đang giữ" to dates.take(7).size.toString(),
                    "Hai phiên nóng N / N-1" to hot,
                    "Cửa sổ N..N-6" to window,
                    "Revision từng phiên" to revText,
                    "Nhân sự master" to staff.toString(),
                    "Master revision" to masterRev.toString()
                )))
                detailsBox.addView(gap(8));detailsBox.addView(section("CHẨN ĐOÁN HỆ THỐNG"))
                detailsBox.addView(details(listOf(
                    "Authority epoch / seq" to "${operationalStore.authorityEpoch()} / ${operationalStore.authoritySeq()}",
                    "Service generation" to operationalStore.serviceGeneration().ifBlank{"—"},
                    "Lỗi route gần nhất" to lastError,
                    "Phiên bản / kênh" to "${BuildConfig.VERSION_NAME} / ${BuildConfig.CHANNEL}",
                    "Realtime thiết kế" to "Foreground invalidation • Background FCM • Local SQLite first"
                )))
                state.text=when{
                    !net.hasInternet->"! Không có mạng • PDA vẫn đọc dữ liệu local"
                    pending>0->"↑ Có $pending thay đổi đang chờ gửi"
                    d.active->"${d.symbol} ${d.label}"
                    mode=="GOOGLE_FALLBACK"->"✓ Local sẵn sàng • Google đang là nguồn dự phòng"
                    else->"✓ Local sẵn sàng • Đồng bộ nền hoạt động"
                }
                serviceProviderCache=when(mode){"GOOGLE_FALLBACK"->"Google dự phòng";"SERVICE_PRIMARY"->"Cloudflare";else->serviceProviderCache}
                refreshHeaderConnection()
                handler.postDelayed(this,1000L)
            }
        }
        handler.post(ticker);attach(root,body)
    }

''',
        "full sync diagnostics",
    )

    OPS.write_text(s, encoding="utf-8")

print("Applied S25 cache-first fallback sync + shared PDA history/session UX + full sync diagnostics")
