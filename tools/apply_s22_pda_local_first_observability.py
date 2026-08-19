#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
BRIDGE = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/M2RuntimeBridge.kt"
TRANSPORT = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt"
API = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt"
MARK = "S22_PDA_LOCAL_FIRST_OBSERVABILITY"


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"S22 block start {label!r} not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"S22 block end {label!r} not found")
    return text[:start] + replacement + text[end:]


def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"S22 anchor {label!r}: expected 1, got {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# OperationsActivity: hot UI reads local projection; Service revalidates in background.
# ---------------------------------------------------------------------------
s = OPS.read_text(encoding="utf-8")
if MARK not in s:
    s = once(s, "class OperationsActivity : Activity() {\n", f"class OperationsActivity : Activity() {{\n    // {MARK}\n", "marker")
    s = once(
        s,
        "    private var lastConnected: Boolean? = null\n",
        "    private var lastConnected: Boolean? = null\n    private var lastLatencyMs: Long? = null\n    private var serviceProviderCache = \"—\"\n    private var historyDetailMnv = \"\"\n    private var historyDetailName = \"\"\n    private val statusTickerHandler = android.os.Handler(android.os.Looper.getMainLooper())\n    private val statusTicker = object:Runnable {\n        override fun run(){\n            refreshHeaderConnection()\n            statusTickerHandler.postDelayed(this,750L)\n        }\n    }\n",
        "runtime status fields",
    )

    # Local DB changes update current screen after atomic save; no screen-triggered Service reload.
    start = "    private val operationalSync by lazy {"
    end = "    private lateinit var module: String"
    if start in s:
        s = replace_block(
            s,
            start,
            end,
            '''    private val operationalSync by lazy {
        OperationalSyncEngine(this, cacheApi, operationalStore) { changedDates ->
            runOnUiThread {
                if(changedDates.isEmpty()) return@runOnUiThread
                when(screenState){
                    "REPORT" -> reportScreen()
                    "HISTORY" -> historyScreen()
                    "HISTORY_DETAIL" -> if(historyDetailMnv.isNotBlank()) historyTimelineScreen(historyDetailMnv,historyDetailName)
                    "EMPLOYEE", "EMPLOYEE_LOADING" -> if(liveEmployeeMnv.isNotBlank()) renderLocalEmployee(liveEmployeeMnv)
                }
            }
        }
    }
''',
            "operational sync listener",
        )

    s = once(
        s,
        "                lastConnected = status.connected\n                refreshHeaderConnection()\n",
        "                lastConnected = status.connected\n                lastLatencyMs = status.latencyMs\n                serviceProviderCache = serviceProviderFromRuntime()\n                refreshHeaderConnection()\n",
        "foreground telemetry",
    )
    old_hot = '                if(module=="BUSINESS" && liveEmployeeMnv.isNotBlank()){ loadEmployee(liveEmployeeMnv); return }\n'
    if old_hot in s:
        s = s.replace(old_hot, '                if(module=="BUSINESS" && liveEmployeeMnv.isNotBlank()) return\n', 1)

    s = once(
        s,
        "        if (api.token != null) foregroundSync.start()\n",
        "        if (api.token != null) foregroundSync.start()\n        statusTickerHandler.removeCallbacks(statusTicker)\n        statusTickerHandler.post(statusTicker)\n",
        "start status ticker",
    )
    s = once(
        s,
        "        foregroundSync.stop()\n        super.onStop()\n",
        "        statusTickerHandler.removeCallbacks(statusTicker)\n        foregroundSync.stop()\n        super.onStop()\n",
        "stop status ticker",
    )

    # Full local employee/session context renders first. Direct Service read is revalidation only.
    s = replace_block(
        s,
        "    private fun loadEmployee(mnv: String, button: Button? = null) {",
        "    private fun renderCachedEmployee(e: JSONObject) {",
        '''    private fun renderLocalEmployee(mnv:String):Boolean{
        val ctx=PdaLocalProjection.employeeContext(this,mnv) ?: return false
        val masters=if(ctx.optString("state")=="NOT_ENTERED")PdaLocalProjection.resourceOptions(this,mnv) else null
        renderEmployee(ctx,masters)
        return true
    }

    private fun loadEmployee(mnv: String, button: Button? = null) {
        val localShown=renderLocalEmployee(mnv)
        if(!localShown){
            val cached=MasterDataCache.employee(this,mnv)
            if(cached!=null && screenState=="SCAN")renderCachedEmployee(cached)
        }
        api.call("employee_context",JSONObject().put("mnv",mnv).put("include_options",false).put("include_labor",false)){result->runOnUiThread{
            button?.isEnabled=true;button?.text="KIỂM TRA"
            if(result.code==401){sessionExpired();return@runOnUiThread}
            if(!result.ok){
                if(!localShown)showError(result.error?:"Không kiểm tra được MNV")
                return@runOnUiThread
            }
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
        "local-first employee",
    )

    # Restore S15 local History after S19 Service hot-read regression.
    s = replace_block(
        s,
        "    private fun historyScreen(){",
        "    private fun syncScreen(){",
        '''    private fun historyScreen(){
        module="HISTORY";screenState="HISTORY";historyDetailMnv="";historyDetailName=""
        val root=baseRoot("LỊCH SỬ CHUNG");val body=body();val summaryBox=column(bg);val box=column(bg)
        body.addView(summaryBox,matchWrap());body.addView(box,matchWrap())
        val dates=operationalStore.availableDates();val today=operationalStore.businessDate();val date=if(dates.contains(today))today else dates.firstOrNull()
        val snapshot=date?.let{operationalStore.loadDay(it)};val j=snapshot?.optJSONObject("history")
        if(j==null){box.addView(info("Đang đồng bộ lịch sử gần nhất về PDA."));attach(root,body);return}
        val items=j.optJSONArray("items")?:JSONArray()
        val metrics=row(bg)
        metrics.addView(metric("Nhân sự",j.optInt("total").toString(),navy),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)})
        metrics.addView(metric("Đang ca",j.optInt("active_count").toString(),green),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(1);marginEnd=dp(1)})
        metrics.addView(metric("Đã ra",j.optInt("ended_count").toString(),teal),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)})
        summaryBox.addView(metrics,matchWrap());summaryBox.addView(gap(5))
        if(items.length()==0){box.addView(info("Chưa có lịch sử nghiệp vụ trong ngày."));attach(root,body);return}
        for(i in 0 until items.length()){
            val x=items.optJSONObject(i)?:continue;val mnv=x.optString("mnv");val fullName=x.optString("full_name")
            val ended=x.optString("state")=="ENDED";val lastTime=x.optString("last_time").substringAfter(" ",x.optString("last_time"));val actor=x.optString("last_actor").ifBlank{"—"}
            val card=column(surface).apply{
                setPadding(dp(10),dp(7),dp(10),dp(7));background=outlineBg(surface,10)
                addView(txt("$mnv • ${fullName.ifBlank{"Chưa có tên"}}",11.7f,ink,true).apply{maxLines=2})
                addView(txt("${x.optString("shift").ifBlank{"—"}} • ${if(ended)"Đã ra ca" else "Đang trong ca"} • ${x.optInt("event_count")} thao tác",9.1f,if(ended)muted else green,false).apply{maxLines=2})
                addView(txt("$lastTime • ${x.optString("last_label").ifBlank{"—"}} • $actor",8.9f,muted,false).apply{maxLines=2})
                setOnClickListener{historyTimelineScreen(mnv,fullName)}
            }
            box.addView(card,matchWrap());box.addView(gap(4))
        }
        attach(root,body)
    }

    private fun historyTimelineScreen(mnv:String,nameHint:String){
        module="HISTORY";screenState="HISTORY_DETAIL";historyDetailMnv=mnv;historyDetailName=nameHint
        val root=baseRoot("CHI TIẾT LỊCH SỬ");val body=body()
        body.addView(listCard("$mnv • ${nameHint.ifBlank{"Nhân sự"}}","Dòng thời gian nghiệp vụ của phiên hôm nay"),matchWrap());body.addView(gap(5))
        val box=column(bg);body.addView(box,matchWrap())
        val dates=operationalStore.availableDates();val today=operationalStore.businessDate();val date=if(dates.contains(today))today else dates.firstOrNull()
        val timeline=JSONArray();val events=date?.let{operationalStore.loadDay(it)}?.optJSONArray("events")?:JSONArray()
        for(i in 0 until events.length()){val e=events.optJSONObject(i)?:continue;if(e.optString("mnv")==mnv)timeline.put(e)}
        if(timeline.length()==0){box.addView(info("Chưa có thao tác cho MNV này."));attach(root,body);return}
        for(i in 0 until timeline.length()){
            val e=timeline.optJSONObject(i)?:continue;val last=i==timeline.length()-1;val lineRow=row(bg).apply{gravity=Gravity.TOP}
            val rail=column(bg).apply{gravity=Gravity.CENTER_HORIZONTAL;addView(txt("●",13f,if(e.optString("event_type").contains("EXIT"))red else teal,true).apply{gravity=Gravity.CENTER},size(dp(24),dp(24)));if(!last)addView(View(this@OperationsActivity).apply{setBackgroundColor(line)},LinearLayout.LayoutParams(dp(2),dp(46)))}
            lineRow.addView(rail,LinearLayout.LayoutParams(dp(30),-2));val whenText=formatIso(e.optString("at_iso").ifBlank{e.optString("at")});val actor=e.optString("actor").ifBlank{"—"};val detail=e.optString("detail").ifBlank{"Không có thông tin bổ sung"}
            lineRow.addView(column(surface).apply{setPadding(dp(9),dp(7),dp(9),dp(7));background=outlineBg(surface,9);addView(txt(e.optString("label").ifBlank{e.optString("event_type")},11.1f,ink,true));addView(txt("$whenText • xử lý bởi $actor",9f,muted,false).apply{maxLines=2});addView(gap(2));addView(txt(detail,9.3f,ink,false).apply{maxLines=5})},LinearLayout.LayoutParams(0,-2,1f))
            box.addView(lineRow,matchWrap());if(!last)box.addView(gap(2))
        }
        attach(root,body)
    }

''',
        "local history",
    )

    # Sync screen renders immediately from local state; foreground coordinator owns network sync.
    s = replace_block(
        s,
        "    private fun syncScreen(){",
        "    private fun settingsScreen(){",
        '''    private fun formatRate(v:Long):String=when{
        v>=1024L*1024L->String.format(java.util.Locale.US,"%.1f MB/s",v/1048576.0)
        v>=1024L->String.format(java.util.Locale.US,"%.1f KB/s",v/1024.0)
        else->"$v B/s"
    }
    private fun syncHeaderText():String{
        val d=SyncDirectionTracker.snapshot()
        return when{
            lastConnected==false->"Chờ mạng"
            d.uploadBps>0&&d.downloadBps>0->"↑${formatRate(d.uploadBps).substringBefore(" ")} ↓${formatRate(d.downloadBps).substringBefore(" ")}"
            d.uploadBps>0->"↑ ${formatRate(d.uploadBps)}"
            d.downloadBps>0->"↓ ${formatRate(d.downloadBps)}"
            d.active->"${d.symbol} ${d.shortLabel}"
            else->"✓ Sẵn sàng"
        }
    }
    private fun serviceProviderFromRuntime():String{
        val st=api.runtimeStatus();val mode=st.optString("authority_mode");val route=st.optString("route")
        return when{
            mode=="GOOGLE_FALLBACK"||route=="GAS_COMPAT"->"Google Drive"
            mode=="SERVICE_PRIMARY"||mode=="RECONCILING"||route.startsWith("SERVICE_")->"Cloudflare"
            st.optString("service_url").isNotBlank()->"Cloudflare"
            else->serviceProviderCache
        }
    }
    private fun networkHeaderText():String=DeviceNetworkStatus.snapshot(this).header(lastLatencyMs)

    private fun syncScreen(){
        module="SYNC";screenState="SYNC"
        val root=baseRoot("ĐỒNG BỘ");val body=body();val state=info("Đang đọc trạng thái trên PDA...");val detailsBox=column(bg)
        body.addView(state,matchWrap());body.addView(gap(8));body.addView(detailsBox,matchWrap())
        val handler=android.os.Handler(android.os.Looper.getMainLooper())
        val ticker=object:Runnable{
            override fun run(){
                if(screenState!="SYNC")return
                val net=DeviceNetworkStatus.snapshot(this@OperationsActivity);val d=SyncDirectionTracker.snapshot()
                val dates=runCatching{operationalStore.availableDates().size}.getOrDefault(0)
                val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(0)
                val conflicts=runCatching{operationalStore.conflicts(100).size}.getOrDefault(0)
                detailsBox.removeAllViews()
                detailsBox.addView(details(listOf(
                    "Mạng" to net.header(lastLatencyMs),
                    "Internet xác thực" to if(net.validated)"Có" else if(net.hasInternet)"Đang xác nhận" else "Không",
                    "Service" to serviceProviderCache,
                    "Tải lên" to formatRate(d.uploadBps),
                    "Tải xuống" to formatRate(d.downloadBps),
                    "Dữ liệu chờ gửi" to pending.toString(),
                    "Xung đột" to conflicts.toString(),
                    "Ngày lưu trên PDA" to dates.toString(),
                    "Phiên bản" to BuildConfig.VERSION_NAME
                )))
                state.text=when{!net.hasInternet->"! Không có mạng";pending>0->"↑ Đang chờ gửi $pending thay đổi";d.active->"${d.symbol} ${d.label}";else->"✓ PDA đã sẵn sàng"}
                handler.postDelayed(this,1000L)
            }
        }
        handler.post(ticker)
        attach(root,body)
    }

''',
        "local sync diagnostics",
    )

    # Replace S19 route-oriented header with provider/network/sync telemetry.
    status_start = "    // S19_RUNTIME_UI_APPLIED: status is measured from the actual authority/route, never hard-coded."
    if status_start in s:
        s = replace_block(
            s,
            status_start,
            "    private fun headerStatusChip",
            '''    private fun connectionSummary():String{
        return "Mạng: ${networkHeaderText()} | Đồng bộ: ${syncHeaderText()} | Service: $serviceProviderCache"
    }
    private fun refreshHeaderConnection(){
        networkStatusText?.text=networkHeaderText()
        syncStatusText?.text=syncHeaderText()
        serviceStatusText?.text=serviceProviderCache
    }
''',
            "header telemetry",
        )

    # Same-tab presses always return to that tab's root. This removes module/content desynchronization.
    nav_start = "    private fun navigateTab(target:String){"
    nav_end = "    private fun sessionExpired(){"
    s = replace_block(
        s,
        nav_start,
        nav_end,
        '''    private fun navigateTab(target:String){
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

''',
        "tab root navigation",
    )

    OPS.write_text(s, encoding="utf-8")

# ---------------------------------------------------------------------------
# Runtime route status becomes cache-only and provider-oriented; no UI-thread discovery request.
# ---------------------------------------------------------------------------
b = BRIDGE.read_text(encoding="utf-8")
status_old_start = "    fun status():JSONObject {"
status_old_end = "    fun clear(){"
if "S22_CACHE_ONLY_STATUS" not in b:
    b = replace_block(
        b,
        status_old_start,
        status_old_end,
        '''    // S22_CACHE_ONLY_STATUS: UI status must never perform discovery/network I/O.
    fun status():JSONObject {
        val d=prefs.getString("discovery_json",null)?.let{runCatching{JSONObject(it)}.getOrNull()}
        val mode=d?.optString("authority_mode").orEmpty().ifBlank{prefs.getString(KEY_AUTHORITY_MODE,"").orEmpty()}
        val url=d?.optString("service_url").orEmpty().ifBlank{prefs.getString(KEY_SERVICE_URL,"").orEmpty()}
        val tokenPresent=!prefs.getString(KEY_SERVICE_TOKEN,null).isNullOrBlank()
        val route=prefs.getString(KEY_LAST_ROUTE,null) ?: when{
            mode=="SERVICE_PRIMARY"&&tokenPresent->"SERVICE_D1_DIRECT"
            mode=="SERVICE_PRIMARY"->"SERVICE_D1_VIA_GAS"
            mode=="GOOGLE_FALLBACK"->"GOOGLE_FALLBACK"
            else->"UNRESOLVED"
        }
        val provider=if(mode=="GOOGLE_FALLBACK"||route=="GAS_COMPAT")"Google Drive" else if(mode=="SERVICE_PRIMARY"||mode=="RECONCILING"||route.startsWith("SERVICE_")||url.isNotBlank())"Cloudflare" else "—"
        return JSONObject().put("authority_mode",mode).put("service_url",url).put("service_session",tokenPresent).put("route",route).put("label",provider).put("provider",provider).put("last_error",prefs.getString(KEY_LAST_ERROR,"").orEmpty())
    }

''',
        "runtime cache-only status",
    )

# ---------------------------------------------------------------------------
# Payload throughput accounting. Counts app API payloads, not APK file download traffic.
# ---------------------------------------------------------------------------
def instrument_spaced(text: str, label: str) -> str:
    old = '            conn.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }\n'
    if old in text:
        text = text.replace(old, '            val requestBytes=payload.toString().toByteArray(Charsets.UTF_8);SyncDirectionTracker.recordUploadBytes(requestBytes.size.toLong())\n            conn.outputStream.use { it.write(requestBytes) }\n', 1)
    else:
        raise SystemExit(f"S22 {label} request byte anchor missing")
    old2 = '            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()\n'
    if old2 in text:
        text = text.replace(old2, old2 + '            SyncDirectionTracker.recordDownloadBytes(text.toByteArray(Charsets.UTF_8).size.toLong())\n', 1)
    else:
        raise SystemExit(f"S22 {label} response byte anchor missing")
    return text

t = TRANSPORT.read_text(encoding="utf-8")
if "requestBytes=payload.toString()" not in t:
    t = instrument_spaced(t, "service transport")
    TRANSPORT.write_text(t, encoding="utf-8")

if "S22_CACHE_ONLY_STATUS" in b and "requestBytes=payload.toString()" not in b:
    old='            conn.outputStream.use{it.write(payload.toString().toByteArray(Charsets.UTF_8))}\n'
    if b.count(old)!=1: raise SystemExit(f"S22 bridge request byte anchor: {b.count(old)}")
    b=b.replace(old,'            val requestBytes=payload.toString().toByteArray(Charsets.UTF_8);SyncDirectionTracker.recordUploadBytes(requestBytes.size.toLong())\n            conn.outputStream.use{it.write(requestBytes)}\n',1)
    old='            val text=stream?.bufferedReader(Charsets.UTF_8)?.use{it.readText()}.orEmpty();val j=if(text.isBlank())JSONObject() else JSONObject(text)\n'
    if b.count(old)!=1: raise SystemExit(f"S22 bridge response byte anchor: {b.count(old)}")
    b=b.replace(old,'            val text=stream?.bufferedReader(Charsets.UTF_8)?.use{it.readText()}.orEmpty();SyncDirectionTracker.recordDownloadBytes(text.toByteArray(Charsets.UTF_8).size.toLong());val j=if(text.isBlank())JSONObject() else JSONObject(text)\n',1)
BRIDGE.write_text(b, encoding="utf-8")

a = API.read_text(encoding="utf-8")
if "requestBytes=body.toString()" not in a:
    old='            conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }\n'
    if a.count(old)!=1: raise SystemExit(f"S22 GAS request byte anchor: {a.count(old)}")
    a=a.replace(old,'            val requestBytes=body.toString().toByteArray(Charsets.UTF_8);SyncDirectionTracker.recordUploadBytes(requestBytes.size.toLong())\n            conn.outputStream.use { it.write(requestBytes) }\n',1)
    old='            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()\n'
    if a.count(old)!=1: raise SystemExit(f"S22 GAS response byte anchor: {a.count(old)}")
    a=a.replace(old,old+'            SyncDirectionTracker.recordDownloadBytes(text.toByteArray(Charsets.UTF_8).size.toLong())\n',1)
    API.write_text(a, encoding="utf-8")

print("Applied S22 PDA local-first + provider/network/sync observability fixes.")
