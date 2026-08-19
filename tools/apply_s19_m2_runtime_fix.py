#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

# --- BetaApiClient: seamless GAS-session -> Service-session exchange + direct hot reads. ---
p=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
s=p.read_text()
marker='S19_M2_RUNTIME_FIX_APPLIED'
if marker not in s:
    old='    // M2_SERVICE_TRANSPORT_APPLIED: dynamic Service primary + GAS fallback.\n    private val m2Transport = M2ServiceTransport(appContext)\n'
    if s.count(old)!=1: raise SystemExit(f'S19 client transport anchor mismatch: {s.count(old)}')
    s=s.replace(old,old+'    // S19_M2_RUNTIME_FIX_APPLIED: honest runtime route + inherited-session exchange.\n    private val m2Runtime = M2RuntimeBridge(appContext)\n',1)

    old='''    fun clearSession() {
        synchronized(sessionLock) { sharedToken = null }
        prefs.edit().remove(KEY_TOKEN).remove(KEY_LOGIN).remove(KEY_NAME).remove(KEY_ROLE).remove(KEY_POSITION).remove(KEY_EMAIL).apply()
    }
'''
    if s.count(old)!=1: raise SystemExit('S19 clearSession anchor mismatch')
    s=s.replace(old,'''    fun clearSession() {
        synchronized(sessionLock) { sharedToken = null }
        prefs.edit().remove(KEY_TOKEN).remove(KEY_LOGIN).remove(KEY_NAME).remove(KEY_ROLE).remove(KEY_POSITION).remove(KEY_EMAIL).apply()
        m2Runtime.clear()
    }
''',1)

    anchor='''    fun restoredAccount(): JSONObject? {
'''
    if s.count(anchor)!=1: raise SystemExit('S19 restoredAccount anchor mismatch')
    s=s.replace(anchor,'    fun runtimeStatus(): JSONObject = m2Runtime.status()\n\n'+anchor,1)

    start=s.find('      val m2 = when {')
    end=s.find('      if (result.ok) {',start)
    if start<0 or end<0: raise SystemExit('S19 transformed M2 call anchors missing')
    replacement='''      val gasSession = token
      var m2: M2ServiceTransport.TransportResult? = when {
          action in M2RuntimeBridge.DIRECT_READS -> m2Runtime.directRead(action, payload, gasSession)
          action in M2ServiceTransport.OPERATIONAL -> {
              m2Runtime.ensureServiceSession(gasSession)
              m2Transport.operational(action, payload)
          }
          action in M2ServiceTransport.SYNC_ACTIONS -> {
              m2Runtime.ensureServiceSession(gasSession)
              m2Transport.sync(action, payload)
          }
          else -> null
      }
      if (m2?.handled == true && m2?.code == 401 && !gasSession.isNullOrBlank()) {
          m2 = when {
              action in M2RuntimeBridge.DIRECT_READS -> m2Runtime.directRead(action, payload, gasSession)
              action in M2ServiceTransport.OPERATIONAL -> m2Runtime.recoverAndRetryOperational(action, payload, gasSession)
              action in M2ServiceTransport.SYNC_ACTIONS -> m2Runtime.recoverAndRetrySync(action, payload, gasSession)
              else -> m2
          }
      }
      val usedService = m2?.handled == true
      val result = if (usedService) {
          Result(m2!!.ok, m2.code, m2.json, m2.error)
      } else when (action) {
          "change_password" -> changePassword(payload)
          "account_upsert" -> accountUpsert(payload)
          else -> post(JSONObject(payload.toString()).apply { put("action", action) }, authenticated = true)
      }
      if (!usedService && action in M2ServiceTransport.OPERATIONAL) m2Transport.acknowledgeFallback(payload.optString("event_id"), result.ok, result.error)
      if (usedService && result.ok && result.code != 202) m2Runtime.recordDirect()
      else if (!usedService && (action in M2RuntimeBridge.DIRECT_READS || action in M2ServiceTransport.OPERATIONAL || action in M2ServiceTransport.SYNC_ACTIONS)) m2Runtime.recordFallback(m2?.error)
'''
    s=s[:start]+replacement+s[end:]
    s=s.replace('AppHistory.record(appContext,action,result.ok,result.error.orEmpty())','AppHistory.record(appContext,action,result.ok,result.error.orEmpty(),payload)')
    s=s.replace('AppHistory.record(appContext,action,false,result.error.orEmpty())','AppHistory.record(appContext,action,false,result.error.orEmpty(),payload)')
    p.write_text(s)

# --- OperationsActivity: actual route status, shared canonical history, truthful sync dashboard. ---
p=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=p.read_text()
if 'S19_RUNTIME_UI_APPLIED' not in s:
    start=s.find('    private fun connectionSummary():String{')
    end=s.find('    private fun headerStatusChip',start)
    if start<0 or end<0: raise SystemExit('S19 status UI structural anchors missing')
    status='''    // S19_RUNTIME_UI_APPLIED: status is measured from the actual authority/route, never hard-coded.
    private fun runtimeLabel(short:Boolean=false):String{
        val st=api.runtimeStatus();val route=st.optString("route")
        return if(short) when(route){"SERVICE_D1_DIRECT"->"CF / D1";"SERVICE_D1_VIA_GAS"->"CF qua GAS";"GOOGLE_FALLBACK"->"Google dự phòng";"GAS_COMPAT"->"Google / GAS";else->"Đang xác định"}
        else st.optString("label","Đang xác định")
    }
    private fun connectionSummary():String{
        val network=when(lastConnected){true->"Tốt";false->"Mất kết nối";null->"Chưa kiểm tra"}
        val sync=SyncDirectionTracker.snapshot().shortLabel
        return "Mạng: $network | Đồng bộ: $sync | Service: ${runtimeLabel()}"
    }
    private fun refreshHeaderConnection(){
        networkStatusText?.text=when(lastConnected){true->"Tốt";false->"Mất";null->"—"}
        syncStatusText?.text=SyncDirectionTracker.snapshot().shortLabel
        serviceStatusText?.text=runtimeLabel(true)
    }
'''
    s=s[:start]+status+s[end:]
    s=s.replace('status("ĐANG KIỂM TRA PHIÊN...", blue, Color.rgb(237,244,255))','status("Đang xác nhận trạng thái phiên...", blue, Color.rgb(237,244,255))')

    start=s.find('    private fun historyScreen(){')
    end=s.find('    private fun syncScreen(){',start)
    if start<0 or end<0: raise SystemExit('S19 history method anchors missing')
    history='''    private fun historyScreen(){
        module="HISTORY"
        screenState="HISTORY"
        val root=baseRoot("LỊCH SỬ")
        val body=body()
        body.addView(info("Đang tải lịch sử nghiệp vụ hôm nay..."))
        attach(root,body)
        api.call("history_shared"){r->runOnUiThread{
            body.removeAllViews()
            if(handleAuth(r))return@runOnUiThread
            val items=if(r.ok) r.json?.optJSONArray("items") else null
            if(items!=null){
                if(items.length()==0)body.addView(info("Chưa có lịch sử nghiệp vụ hôm nay."))
                for(i in 0 until items.length()){
                    val x=items.optJSONObject(i)?:continue
                    val title="${x.optString("mnv")} • ${x.optString("full_name").ifBlank{"Không rõ tên"}}"
                    val whenText=formatIso(x.optString("last_at_iso").ifBlank{x.optString("last_time")})
                    val sub="${x.optString("last_label").ifBlank{"Hoạt động"}} • $whenText • ${x.optString("last_actor").ifBlank{"—"}}"
                    body.addView(listCard(title,sub));body.addView(gap(6))
                }
            }else{
                val local=AppHistory.items(this@OperationsActivity)
                body.addView(info("Không tải được lịch sử dùng chung. Đang hiển thị lịch sử trên thiết bị."))
                body.addView(gap(6))
                if(local.length()==0)body.addView(info("Chưa có lịch sử trên thiết bị."))
                for(i in 0 until local.length()){
                    val x=local.optJSONObject(i)?:continue;val ok=x.optBoolean("synced")
                    val at=java.text.SimpleDateFormat("dd/MM HH:mm:ss",java.util.Locale.US).format(java.util.Date(x.optLong("at")))
                    val c=x.optJSONObject("context");val mnv=c?.optString("mnv").orEmpty()
                    val title=(if(mnv.isBlank())"" else "$mnv • ")+AppHistory.label(x.optString("action"))
                    body.addView(listCard(title,"$at • ${if(ok)"Đã ghi nhận" else "Chờ đồng bộ"}"));body.addView(gap(6))
                }
            }
        }}
    }

'''
    s=s[:start]+history+s[end:]

    start=s.find('    private fun syncScreen(){')
    end=s.find('    private fun settingsScreen(){',start)
    if start<0 or end<0: raise SystemExit('S19 sync method anchors missing')
    sync='''    private fun syncScreen(){
        module="SYNC"
        screenState="SYNC"
        val root=baseRoot("ĐỒNG BỘ")
        val body=body()
        val state=info("Đang kiểm tra kết nối...")
        val detailsBox=column(bg)
        body.addView(state,matchWrap());body.addView(gap(8));body.addView(detailsBox,matchWrap())
        fun renderDetails(server:JSONObject?=null){
            detailsBox.removeAllViews()
            val store=OperationalDataStore(this)
            val direction=SyncDirectionTracker.snapshot()
            val route=runtimeLabel()
            val dates=runCatching{store.availableDates().size}.getOrDefault(0)
            val pending=runCatching{store.pendingMutationCount()}.getOrDefault(0)
            detailsBox.addView(details(listOf(
                "Mạng" to when(lastConnected){true->"Tốt";false->"Mất kết nối";null->"Đang kiểm tra"},
                "Đồng bộ" to direction.label,
                "Nguồn nghiệp vụ" to route,
                "Dữ liệu chờ gửi" to pending.toString(),
                "Ngày đang lưu trên máy" to dates.toString(),
                "Ngày nghiệp vụ" to (server?.optString("business_date").orEmpty().ifBlank{"—"}),
                "Phiên bản" to BuildConfig.VERSION_NAME
            )))
            state.text=when{lastConnected==false->"! Mất kết nối";direction.downloading->"↓ Đang nhận dữ liệu thay đổi";direction.uploading->"↑ Đang gửi dữ liệu";else->"✓ Sẵn sàng"}
        }
        renderDetails()
        api.call("sync_status"){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            lastConnected=r.ok
            refreshHeaderConnection()
            if(r.ok)renderDetails(r.json) else {renderDetails();body.addView(gap(6));body.addView(info("Dữ liệu chờ sẽ tự gửi khi kết nối trở lại."))}
        }}
    }

'''
    s=s[:start]+sync+s[end:]
    p.write_text(s)

# --- Event-driven foreground contract guard. Never reintroduce a normal polling loop. ---
p=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/ForegroundSyncCoordinator.kt'
s=p.read_text()
legacy_markers=('main.postDelayed(tick, nextDelay(result.ok))','idlePolls <= 3 -> 1_500L','idlePolls <= 2 -> 15_000L')
found=[m for m in legacy_markers if m in s]
if found:
    raise SystemExit('S19 legacy continuous polling reintroduced: '+', '.join(found))
if 'Event-driven foreground Service/D1 revision synchronizer' not in s:
    raise SystemExit('S19 event-driven foreground contract marker missing')

print('Applied S19 M2 production runtime fix; event-driven foreground contract preserved.')
