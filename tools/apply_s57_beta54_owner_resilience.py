from pathlib import Path
import re

OPS = Path('app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt')
STORE = Path('app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt')
TRANSPORT = Path('app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt')
RUNTIME = Path('app/src/main/java/vn/pickpack1291/app/beta/M2RuntimeBridge.kt')
API = Path('app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt')
FG = Path('app/src/main/java/vn/pickpack1291/app/beta/ForegroundSyncCoordinator.kt')


def once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return text.replace(old, new, 1)

# ---- Durable outbox semantics: only actually retriable rows are pending. ----
s = STORE.read_text()
s = once(s,
'''            "(status IN ('LOCAL_PENDING','PENDING','RETRY','OFFLINE_PROVISIONAL') OR (status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW')) AND next_attempt_at <= ?",''',
'''            "status IN ('LOCAL_PENDING','PENDING','RETRY','OFFLINE_PROVISIONAL') AND next_attempt_at <= ?",''',
'pendingMutations status filter')
s = re.sub(
    r'''    fun retryDateWindowRejects\(\):Int=withDbLock\{.*?\n    \}\n\n    fun markMutationSynced''',
    '''    /** Permanently rejected out-of-window rows are audit/history, never network backlog. */\n    fun retryDateWindowRejects():Int = 0\n\n    fun markMutationSynced''',
    s, count=1, flags=re.S)
if 'fun retryDateWindowRejects():Int = 0' not in s:
    raise SystemExit('retryDateWindowRejects replacement failed')
old_count = '''    fun pendingMutationCount(): Int = withDbLock {\n        readableDb().rawQuery("SELECT COUNT(*) FROM mutation_outbox WHERE status IN ('LOCAL_PENDING','PENDING','RETRY','OFFLINE_PROVISIONAL') OR (status='REJECTED' AND last_error='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW')", null).use { c -> if (c.moveToFirst()) c.getInt(0) else 0 }\n    }'''
new_count = '''    data class MutationStatusCounts(val pending:Int,val review:Int,val rejected:Int,val confirmed:Int)\n\n    fun mutationStatusCounts():MutationStatusCounts = withDbLock {\n        var pending=0;var review=0;var rejected=0;var confirmed=0\n        readableDb().rawQuery("SELECT status,COUNT(*) FROM mutation_outbox GROUP BY status",null).use { c ->\n            while(c.moveToNext()){\n                val count=c.getInt(1)\n                when(c.getString(0)){\n                    "LOCAL_PENDING","PENDING","RETRY","OFFLINE_PROVISIONAL"->pending+=count\n                    "REVIEW_REQUIRED"->review+=count\n                    "REJECTED"->rejected+=count\n                    "CONFIRMED"->confirmed+=count\n                }\n            }\n        }\n        MutationStatusCounts(pending,review,rejected,confirmed)\n    }\n\n    fun pendingMutationCount(): Int = mutationStatusCounts().pending'''
s = once(s, old_count, new_count, 'pendingMutationCount/status counts')
STORE.write_text(s)

# ---- Provider fault injection at the Android transport boundary. ----
t = TRANSPORT.read_text()
t = once(t,
'''    fun loginFromPassword(loginId: String, password: String) {\n        if (!hasNetwork()) return''',
'''    fun loginFromPassword(loginId: String, password: String) {\n        if (ServiceFaultInjection.cloudflareDisabled(app)) return\n        if (!hasNetwork()) return''',
'login Cloudflare fault')
t = once(t,
'''    fun sync(action: String, payload: JSONObject): TransportResult {\n        if (action !in SYNC_ACTIONS) return TransportResult(false, false, 0, null, null)\n        if (!hasNetwork()) return TransportResult(true, false, -1, null, "OFFLINE_LOCAL")''',
'''    fun sync(action: String, payload: JSONObject): TransportResult {\n        if (action !in SYNC_ACTIONS) return TransportResult(false, false, 0, null, null)\n        if (ServiceFaultInjection.cloudflareDisabled(app)) return TransportResult(true,false,-1,null,"TEST_CLOUDFLARE_DISABLED")\n        if (!hasNetwork()) return TransportResult(true, false, -1, null, "OFFLINE_LOCAL")''',
'sync Cloudflare fault')
t = once(t,
'''    private fun flushOutboxLocked(): Boolean {\n        if (!hasNetwork()) return false\n        var discovery=cachedDiscoverySnapshot();''',
'''    private fun flushOutboxLocked(): Boolean {\n        if (!hasNetwork()) return false\n        if(ServiceFaultInjection.cloudflareDisabled(app)){\n            // Fault injection simulates provider loss only. Do not bypass the authority fence or\n            // manufacture a Google write authority while production still says SERVICE_PRIMARY.\n            return false\n        }\n        var discovery=cachedDiscoverySnapshot();''',
'flush Cloudflare fault fence')
t = once(t,
'''    private fun flushFallbackItems(items: List<OperationalDataStore.PendingMutation>): Boolean {\n        if (items.isEmpty()) return true''',
'''    private fun flushFallbackItems(items: List<OperationalDataStore.PendingMutation>): Boolean {\n        if (ServiceFaultInjection.googleDisabled(app)) return false\n        if (items.isEmpty()) return true''',
'fallback Google fault')
t = once(t,
'''    private fun discover(force: Boolean = false): JSONObject? {\n        val now = System.currentTimeMillis()''',
'''    private fun discover(force: Boolean = false): JSONObject? {\n        if(ServiceFaultInjection.googleDisabled(app)) return cachedDiscoverySnapshot()\n        val now = System.currentTimeMillis()''',
'discovery Google fault')
t = once(t,
'''    private fun httpJson(endpoint: String, payload: JSONObject, bearer: String?, requireServiceHost: Boolean = true): HttpResult {\n        if (requireServiceHost && !validServiceUrl(endpoint.substringBefore("/v1/"))) return HttpResult(false, -1, null, "SERVICE_URL_INVALID")''',
'''    private fun httpJson(endpoint: String, payload: JSONObject, bearer: String?, requireServiceHost: Boolean = true): HttpResult {\n        if(requireServiceHost && ServiceFaultInjection.cloudflareDisabled(app)) return HttpResult(false,-1,null,"TEST_CLOUDFLARE_DISABLED")\n        if(!requireServiceHost && ServiceFaultInjection.googleDisabled(app)) return HttpResult(false,-1,null,"TEST_GOOGLE_DISABLED")\n        if (requireServiceHost && !validServiceUrl(endpoint.substringBefore("/v1/"))) return HttpResult(false, -1, null, "SERVICE_URL_INVALID")''',
'http provider fault')
t = once(t,
'''    private fun httpGetJson(endpoint:String,bearer:String?):HttpResult{\n        if(!validServiceUrl(endpoint.substringBefore("/v1/")))return HttpResult(false,-1,null,"SERVICE_URL_INVALID")''',
'''    private fun httpGetJson(endpoint:String,bearer:String?):HttpResult{\n        if(ServiceFaultInjection.cloudflareDisabled(app))return HttpResult(false,-1,null,"TEST_CLOUDFLARE_DISABLED")\n        if(!validServiceUrl(endpoint.substringBefore("/v1/")))return HttpResult(false,-1,null,"SERVICE_URL_INVALID")''',
'GET provider fault')
TRANSPORT.write_text(t)

r = RUNTIME.read_text()
r = once(r,
'''    fun ensureServiceSession(gasToken:String?,force:Boolean=false):Boolean {\n        val d=transport.cachedDiscoverySnapshot()''',
'''    fun ensureServiceSession(gasToken:String?,force:Boolean=false):Boolean {\n        if(ServiceFaultInjection.cloudflareDisabled(app)){recordServicePending("TEST_CLOUDFLARE_DISABLED");return false}\n        val d=transport.cachedDiscoverySnapshot()''',
'runtime session fault')
r = once(r,
'''    private fun httpJson(endpoint: String, payload: JSONObject, bearer: String?): HttpResult {\n        var connection: HttpURLConnection? = null''',
'''    private fun httpJson(endpoint: String, payload: JSONObject, bearer: String?): HttpResult {\n        if(ServiceFaultInjection.cloudflareDisabled(app))return HttpResult(false,-1,null,"TEST_CLOUDFLARE_DISABLED")\n        var connection: HttpURLConnection? = null''',
'runtime HTTP fault')
r = once(r,
'''            .put("last_error", prefs.getString(KEY_LAST_ERROR, "").orEmpty())''',
'''            .put("last_error", prefs.getString(KEY_LAST_ERROR, "").orEmpty())\n            .put("test_mode",ServiceFaultInjection.mode(app).stored)''',
'runtime test status')
RUNTIME.write_text(r)

a = API.read_text()
a = once(a,
'''      val result = if (usedService) {\n          Result(m2!!.ok, m2.code, m2.json, m2.error)\n      } else when (action) {''',
'''      val runtimeDataAction = action in M2RuntimeBridge.DIRECT_READS || action in M2ServiceTransport.OPERATIONAL || action in M2ServiceTransport.SYNC_ACTIONS\n      val result = if (usedService) {\n          Result(m2!!.ok, m2.code, m2.json, m2.error)\n      } else if(runtimeDataAction && ServiceFaultInjection.googleDisabled(appContext)) {\n          Result(false,-1,null,"TEST_GOOGLE_DISABLED")\n      } else when (action) {''',
'GAS fallback fault fence')
a = once(a,
'''    private fun serviceOwnerCall(action:String,payload:JSONObject):Result{\n        val d=m2Transport.discoverySnapshot()''',
'''    private fun serviceOwnerCall(action:String,payload:JSONObject):Result{\n        if(ServiceFaultInjection.cloudflareDisabled(appContext))return Result(false,-1,null,"TEST_CLOUDFLARE_DISABLED")\n        val d=m2Transport.discoverySnapshot()''',
'owner Service fault')
API.write_text(a)

# ---- Expose Service->Google replication state to the header. ----
f = FG.read_text()
f = once(f,
'''        val dayRevisions: JSONObject = JSONObject(),\n    )''',
'''        val dayRevisions: JSONObject = JSONObject(),\n        val replicationState:String = "",\n        val replicationPending:Int = 0,\n        val replicationLastSuccessAt:String = "",\n    )''',
'foreground status replication fields')
f = once(f,
'''                                dayRevisions = body.optJSONObject("day_revisions") ?: JSONObject(),\n                            )''',
'''                                dayRevisions = body.optJSONObject("day_revisions") ?: JSONObject(),\n                                replicationState = body.optJSONObject("replication")?.optString("state").orEmpty(),\n                                replicationPending = body.optJSONObject("replication")?.optInt("pending_count",0) ?: 0,\n                                replicationLastSuccessAt = body.optJSONObject("replication")?.optString("last_success_at").orEmpty(),\n                            )''',
'foreground replication assignment')
FG.write_text(f)

# ---- UI, status semantics, RA CA local-first, settings. ----
o = OPS.read_text()
o = once(o, '    // S56_BETA53_OWNER_UI_STATUS_FIX\n', '    // S57_BETA54_OWNER_RESILIENCE_FIX\n    // S56_BETA53_OWNER_UI_STATUS_FIX\n', 'S57 marker')
o = once(o,
'''    private var lastProjectionPending: Int = 0\n    private var historySyncInFlight=false''',
'''    private var lastProjectionPending: Int = 0\n    private var lastReplicationState:String = ""\n    private var lastReplicationPending:Int = 0\n    private var lastReplicationSuccessAt:String = ""\n    private var historySyncInFlight=false''',
'replication UI fields')
o = once(o,
'''                lastProjectionPending = status.projectionPending.coerceAtLeast(0)\n                lastLatencyMs = status.latencyMs''',
'''                lastProjectionPending = status.projectionPending.coerceAtLeast(0)\n                lastReplicationState = status.replicationState\n                lastReplicationPending = status.replicationPending.coerceAtLeast(0)\n                lastReplicationSuccessAt = status.replicationLastSuccessAt\n                lastLatencyMs = status.latencyMs''',
'replication UI status update')

# Replace the entire Beta53 header detail helper block; no narrative explanatory text remains.
start = o.index('    private fun bytesVi')
end = o.index('    private fun manualRefreshFromHeader', start)
new_block = '''    private fun bytesVi(v:Long):String=when{v<1024->"$v byte";v<1024L*1024->String.format(java.util.Locale.US,"%.1f KB",v/1024.0);else->String.format(java.util.Locale.US,"%.1f MB",v/(1024.0*1024.0))}\n    private fun statusTimeVi(v:Long):String=if(v<=0L)"Chưa có" else runCatching{java.time.Instant.ofEpochMilli(v).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss"))}.getOrDefault("Chưa có")\n    private fun authorityViHeader(v:String):String=when(v.uppercase()){ "SERVICE_PRIMARY"->"Cloudflare / D1";"GOOGLE_FALLBACK"->"Google Drive";"RECONCILING"->"Đang đối chiếu";"OFFLINE_LOCAL"->"PDA local";else->"Chưa xác định" }\n    private fun routeViHeader(v:String):String=when(v.uppercase()){ "SERVICE_D1_DIRECT"->"Cloudflare trực tiếp";"SERVICE_D1_PENDING"->"Cloudflare chưa xác nhận";"GOOGLE_FALLBACK","GAS_COMPAT"->"Google Drive";"UNRESOLVED"->"Chưa xác định";else->if(v.isBlank())"Chưa xác định" else v }\n    private fun replicaViHeader(v:String):String=when(v.uppercase()){ "SYNCED","HEALTHY","OK"->"Đã sao chép";"PENDING","INFLIGHT","RUNNING"->"Đang sao chép";"RETRY"->"Chờ gửi lại";"ERROR","FAILED"->"Lỗi";else->if(v.isBlank())"Chưa có trạng thái" else v }\n    private fun runtimeErrorVi(v:String):String{val x=v.uppercase();return when{v.isBlank()->"Không có";x.contains("TEST_CLOUDFLARE_DISABLED")->"Cloudflare đang tắt thử nghiệm";x.contains("TEST_GOOGLE_DISABLED")->"Google Drive đang tắt thử nghiệm";x.contains("SESSION_EXCHANGE")->"Không tạo được phiên Cloudflare";x.contains("SERVICE_SESSION_UNAVAILABLE")->"Phiên Cloudflare chưa sẵn sàng";x.contains("AUTHORITY_NOT_SERVICE_PRIMARY")->"Cloudflare không giữ quyền ghi";x.contains("NETWORK")||x.contains("TIMEOUT")->"Lỗi kết nối";else->v.take(120)}}\n    private fun showHeaderStatusDetail(kind:String){\n        val runtime=api.runtimeStatus();val counts=runCatching{operationalStore.mutationStatusCounts()}.getOrDefault(OperationalDataStore.MutationStatusCounts(0,0,0,0));val flow=SyncDirectionTracker.snapshot();val provider=serviceProviderFromRuntime();val net=DeviceNetworkStatus.snapshot(this);val fault=ServiceFaultInjection.mode(this)\n        val title=when(kind){"NETWORK"->"Chi tiết Mạng";"SYNC"->"Chi tiết Đồng bộ";else->"Chi tiết Dịch vụ"}\n        val rows=when(kind){\n            "NETWORK"->listOf(\n                "Loại kết nối" to net.transport,\n                "Internet" to when{!net.hasInternet->"Không có";net.validated->"Đã xác thực";else->"Có kết nối, chưa xác thực"},\n                "Mạng tính phí" to if(net.metered)"Có" else "Không",\n                "Độ trễ Cloudflare" to if(ServiceFaultInjection.cloudflareDisabled(this))"Tắt thử nghiệm" else (lastSyncLatencyMs?.let{"$it ms"}?:"Chưa đo"),\n                "Lần kiểm tra" to statusTimeVi(lastStatusUpdateAt)\n            )\n            "SYNC"->listOf(\n                "Trạng thái" to when{counts.pending>0->"Đang chờ gửi";flow.active->flow.label;lastConnected==true->"Hoàn tất";else->"Chưa kết nối"},\n                "Đang chờ gửi" to counts.pending.toString(),\n                "Cần kiểm tra" to counts.review.toString(),\n                "Bị từ chối" to counts.rejected.toString(),\n                "Đã xác nhận trên Service" to counts.confirmed.toString(),\n                "Google Drive chờ sao chép" to lastReplicationPending.toString(),\n                "Google Drive" to replicaViHeader(lastReplicationState),\n                "Google Drive sao chép gần nhất" to if(lastReplicationSuccessAt.isBlank())"Chưa có" else formatIso(lastReplicationSuccessAt),\n                "Dữ liệu đã gửi" to bytesVi(flow.uploadedBytes),\n                "Dữ liệu đã nhận" to bytesVi(flow.downloadedBytes)\n            )\n            else->listOf(\n                "Đang sử dụng" to provider,\n                "Cloudflare" to if(ServiceFaultInjection.cloudflareDisabled(this))"Tắt thử nghiệm" else if(provider=="Cloudflare")"Đang sử dụng" else "Không sử dụng",\n                "Google Drive" to if(ServiceFaultInjection.googleDisabled(this))"Tắt thử nghiệm" else replicaViHeader(lastReplicationState),\n                "Chế độ dữ liệu" to authorityViHeader(runtime.optString("authority_mode")),\n                "Tuyến kết nối" to routeViHeader(runtime.optString("route")),\n                "Phiên Cloudflare" to if(runtime.optBoolean("service_session",false))"Sẵn sàng" else "Chưa sẵn sàng",\n                "Chế độ thử nghiệm" to fault.label,\n                "Lỗi gần nhất" to runtimeErrorVi(runtime.optString("last_error")),\n                "Địa chỉ Cloudflare" to runtime.optString("service_url").ifBlank{"Chưa có"}\n            )\n        }\n        val box=column(surface).apply{setPadding(dp(14),dp(10),dp(14),dp(8));addView(details(rows),matchWrap())}\n        AlertDialog.Builder(this).setTitle(title).setView(ScrollView(this).apply{addView(box)}).setPositiveButton("ĐÓNG",null).show()\n    }\n\n'''
o = o[:start] + new_block + o[end:]

# RA CA now enters durable outbox first; Service batch applies canonical guards and replication.
old_exit = '''        fun doExit(statusNow:String){exit.isEnabled=false;exit.text="ĐANG RA CA...";api.call("session_exit_guarded",JSONObject().put("session_id",ses.optString("session_id")).put("mnv",mnv).put("pda_exit_status",statusNow).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"RA CA thất bại");return@runOnUiThread};TopNotice.show(this,"Đã ghi nhận ra ca.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();scheduleAttendanceAutoReset(mnv,employeeLookupGeneration)}}}'''
new_exit = '''        fun doExit(statusNow:String){exit.isEnabled=false;exit.text="ĐANG RA CA...";val eventId=UUID.randomUUID().toString();api.call("exit",JSONObject().put("event_id",eventId).put("mnv",mnv).put("pda_exit_status",statusNow).put("note","RA CA")){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"RA_CA_FAILED");return@runOnUiThread};TopNotice.show(this,if(r.code==202)"Đã ghi nhận ra ca trên PDA • đang đồng bộ" else "Đã ghi nhận ra ca.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();scheduleAttendanceAutoReset(mnv,employeeLookupGeneration)}}}'''
o = once(o, old_exit, new_exit, 'RA CA local-first')

# Accurate fault-aware provider label.
old_provider = '''    private fun serviceProviderFromRuntime():String{\n        if(lastConnected==false)return "OFFLINE"\n        val st=api.runtimeStatus();val mode=st.optString("authority_mode");val route=st.optString("route");val url=st.optString("service_url")\n        return when{\n            mode=="GOOGLE_FALLBACK"||route=="GOOGLE_FALLBACK"||route=="GAS_COMPAT"->"Google Drive"\n            mode=="SERVICE_PRIMARY"||mode=="RECONCILING"||route.startsWith("SERVICE_")||url.isNotBlank()->"Cloudflare"\n            else->"OFFLINE"\n        }\n    }'''
new_provider = '''    private fun serviceProviderFromRuntime():String{\n        val fault=ServiceFaultInjection.mode(this)\n        if(fault==ServiceFaultInjection.Mode.DISABLE_BOTH)return "OFFLINE"\n        val st=api.runtimeStatus();val mode=st.optString("authority_mode");val route=st.optString("route");val url=st.optString("service_url")\n        if(ServiceFaultInjection.cloudflareDisabled(this)){return if(mode=="GOOGLE_FALLBACK"&&!ServiceFaultInjection.googleDisabled(this))"Google Drive" else "OFFLINE"}\n        if(lastConnected==false)return "OFFLINE"\n        return when{\n            mode=="GOOGLE_FALLBACK"||route=="GOOGLE_FALLBACK"||route=="GAS_COMPAT"->if(ServiceFaultInjection.googleDisabled(this))"OFFLINE" else "Google Drive"\n            mode=="SERVICE_PRIMARY"||mode=="RECONCILING"||route.startsWith("SERVICE_")||url.isNotBlank()->"Cloudflare"\n            else->"OFFLINE"\n        }\n    }'''
o = once(o, old_provider, new_provider, 'fault-aware provider')

# Settings: useful update/log data + SUPERADMIN fault injection.
old_settings = '''        body.addView(section("CẬP NHẬT PHIÊN BẢN"))\n        body.addView(primary("KIỂM TRA CẬP NHẬT",teal){UpdateManager.openManual(this)},matchWrap())\n        body.addView(gap(10))\n        body.addView(section("Nhật ký"))\n        body.addView(primary("GỬI BÁO LỖI",teal){sendDiagnostic()},matchWrap())\n        body.addView(gap(14))'''
new_settings = '''        body.addView(section("CẬP NHẬT PHIÊN BẢN"))\n        body.addView(details(listOf(\n            "Phiên bản đang cài" to BuildConfig.VERSION_NAME,\n            "Mã phiên bản" to BuildConfig.VERSION_CODE.toString(),\n            "Kênh OTA" to BuildConfig.CHANNEL,\n            "Nguồn kiểm tra OTA" to "Google Apps Script",\n            "Kiểm tra APK" to "SHA-256 + chữ ký ứng dụng"\n        )))\n        body.addView(gap(7))\n        body.addView(primary("KIỂM TRA CẬP NHẬT",teal){UpdateManager.openManual(this)},matchWrap())\n        body.addView(gap(10))\n        body.addView(section("NHẬT KÝ"))\n        val logCounts=runCatching{operationalStore.mutationStatusCounts()}.getOrDefault(OperationalDataStore.MutationStatusCounts(0,0,0,0))\n        body.addView(details(listOf(\n            "Nhật ký trên thiết bị" to LocalLogManager.summary(this),\n            "Đang chờ gửi" to logCounts.pending.toString(),\n            "Cần kiểm tra" to logCounts.review.toString(),\n            "Bị từ chối" to logCounts.rejected.toString(),\n            "Đích gửi báo lỗi" to "Google Drive qua GAS"\n        )))\n        body.addView(gap(7))\n        body.addView(primary("GỬI BÁO LỖI",teal){sendDiagnostic()},matchWrap())\n        if(isActualSuper()){\n            body.addView(gap(10));body.addView(section("THỬ NGHIỆM LỖI SERVICE"))\n            val fault=ServiceFaultInjection.mode(this)\n            body.addView(details(listOf(\n                "Chế độ hiện tại" to fault.label,\n                "Cloudflare" to if(ServiceFaultInjection.cloudflareDisabled(this))"Tắt thử nghiệm" else "Bình thường",\n                "Google Drive" to if(ServiceFaultInjection.googleDisabled(this))"Tắt thử nghiệm" else "Bình thường"\n            )))\n            body.addView(gap(7));body.addView(primary("CHỌN CHẾ ĐỘ THỬ NGHIỆM",orange){showServiceFaultModeDialog()},matchWrap())\n        }\n        body.addView(gap(14))'''
o = once(o, old_settings, new_settings, 'settings detail sections')

# Insert fault mode dialog before theme picker.
anchor = '    private fun themePicker()=row(surface).apply{'
dialog = '''    private fun showServiceFaultModeDialog(){\n        if(!isActualSuper()){showError("SUPERADMIN_REQUIRED");return}\n        val modes=ServiceFaultInjection.Mode.entries.toTypedArray();val labels=modes.map{it.label}.toTypedArray();var selected=modes.indexOf(ServiceFaultInjection.mode(this)).coerceAtLeast(0)\n        AlertDialog.Builder(this).setTitle("Thử nghiệm lỗi service").setSingleChoiceItems(labels,selected){_,which->selected=which}.setNegativeButton("HỦY",null).setPositiveButton("ÁP DỤNG"){_,_->\n            ServiceFaultInjection.setMode(this,modes[selected]);M2ImmediateOutbox.kick(this);foregroundSync.requestSync();TopNotice.show(this,"Đã áp dụng: ${modes[selected].label}",TopNotice.Kind.INFO);settingsScreen()\n        }.show()\n    }\n\n'''
if anchor not in o: raise SystemExit('themePicker anchor missing')
o = o.replace(anchor, dialog + anchor, 1)

# Expand Vietnamese error mapping and preserve the raw code for anything unknown.
show_start = o.index('    private fun showError(raw:String){')
show_end = o.index('    private fun roleText', show_start)
show = o[show_start:show_end]
insert_after = 'raw.contains("EXCLUSIVE_RESOURCE_CONFLICT")->"Tài nguyên vừa bị phiên hoặc máy khác giữ / dùng trước. Bản ghi này không tự gửi lại để tránh cấp trùng. Hãy bấm đồng bộ, quét lại nhân sự và chọn tài nguyên còn trống.";'
if insert_after not in show: raise SystemExit('showError mapping anchor missing')
extra = insert_after + '''\nraw.contains("ATTENDANCE_NOT_ACTIVE")||raw.contains("SESSION_NOT_ACTIVE")->"Không còn phiên đang hoạt động để ra ca. Hãy quét lại nhân sự và đồng bộ trạng thái.";\nraw.contains("SESSION_ACTIVE_AMBIGUOUS")->"Có nhiều phiên đang hoạt động cho cùng nhân sự. Không tự chọn phiên để tránh ghi sai dữ liệu.";\nraw.contains("SESSION_EMPLOYEE_MISMATCH")->"Phiên đang mở không khớp mã nhân viên. Hãy quét lại nhân sự.";\nraw.contains("OPEN_LABOR_BLOCKS_EXIT")->"Nhân sự còn công nhật chưa hoàn thành. Hoàn thành công nhật trước khi ra ca.";\nraw.contains("PDA_EXIT_STATUS_REQUIRED")->"Cần chọn tình trạng PDA hiện tại trước khi ra ca.";\nraw.contains("PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST")->"Tình trạng PDA hiện tại khác lúc nhận. Báo chuyên viên phụ trách trước khi ra ca.";\nraw.contains("STALE_BASE_VERSION")->"Dữ liệu phiên vừa thay đổi trên thiết bị khác. Ứng dụng sẽ đồng bộ lại; hãy quét lại nhân sự.";\nraw.contains("TEST_CLOUDFLARE_DISABLED")->"Cloudflare đang được tắt bằng chế độ thử nghiệm lỗi service.";\nraw.contains("TEST_GOOGLE_DISABLED")->"Google Drive đang được tắt bằng chế độ thử nghiệm lỗi service.";\nraw.contains("SERVICE_NOT_WRITE_AUTHORITY")->"Dịch vụ hiện tại không có quyền ghi dữ liệu.";'''
show = show.replace(insert_after, extra, 1)
show = show.replace('else->"Có lỗi kết nối gần nhất; bấm làm mới để kiểm tra lại"', 'else->v.take(120)')
# Replace the final generic unknown branch in showError if present.
show = show.replace('else->"Lỗi không xác định. Vui lòng thử lại."', 'else->"Không thực hiện được. Mã lỗi: ${raw.ifBlank{"UNKNOWN"}.take(160)}"')
show = show.replace('else->"Thao tác thất bại. Vui lòng thử lại."', 'else->"Không thực hiện được. Mã lỗi: ${raw.ifBlank{"UNKNOWN"}.take(160)}"')
o = o[:show_start] + show + o[show_end:]
OPS.write_text(o)

print('S57_BETA54_OWNER_RESILIENCE_APPLIED')
