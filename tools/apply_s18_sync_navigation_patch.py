#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
activity = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
client = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt"


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"S18 block start {label!r} not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"S18 block end {label!r} not found")
    return text[:start] + replacement + text[end:]

# Track genuine outbound business/account mutations as upload activity. S13 shared history remains
# server-authoritative: this transform must not restore device-local mutation history.
ct = client.read_text(encoding="utf-8")
ct = replace_block(
    ct,
    '    fun call(action: String, payload: JSONObject = JSONObject(), callback: (Result) -> Unit) {',
    '    fun health(callback: (Result) -> Unit) {',
    '''    fun call(action: String, payload: JSONObject = JSONObject(), callback: (Result) -> Unit) {
        val trackUpload = SyncDirectionTracker.isUploadAction(action)
        if (trackUpload) SyncDirectionTracker.beginUpload()
        executor.execute {
            try {
                val result = when (action) {
                    "change_password" -> changePassword(payload)
                    "account_upsert" -> accountUpsert(payload)
                    else -> post(JSONObject(payload.toString()).apply { put("action", action) }, authenticated = true)
                }
                if (result.ok) {
                    val refreshed = result.json?.optString("token")?.takeIf { it.isNotBlank() }
                    if (refreshed != null) persistSession(refreshed, result.json.optJSONObject("account") ?: restoredAccount())
                }
                if (result.code == 401) clearSession()
                // S13 shared history is server-authoritative; no local mutation history.
                callback(result)
            } catch (t: Throwable) {
                val result=failure(t)
                // Failed requests do not create shared business history.
                callback(result)
            } finally {
                if (trackUpload) SyncDirectionTracker.endUpload()
            }
        }
    }

''',
    'BetaApiClient upload tracker',
)
client.write_text(ct, encoding="utf-8")

text = activity.read_text(encoding="utf-8")

# Sync screen: direction is live state, not decorative iconography.
text = replace_block(
    text,
    '    private fun syncScreen(){',
    '    private fun settingsScreen(){',
    r'''    private fun syncScreen(){
        module="SYNC"
        screenState="SYNC"
        val root=baseRoot("ĐỒNG BỘ")
        val body=body()
        var online=lastConnected != false

        val arrow=txt("✓",30f,teal,true).apply{gravity=Gravity.CENTER}
        val state=txt("Sẵn sàng",13f,ink,true).apply{maxLines=1}
        val sub=txt("Theo dõi luồng dữ liệu thời gian thực",9.2f,muted,false).apply{maxLines=2}
        val directionCard=row(surface).apply{
            gravity=Gravity.CENTER_VERTICAL
            setPadding(dp(12),dp(11),dp(12),dp(11))
            background=outlineBg(surface,14)
            addView(arrow,size(dp(54),dp(54)))
            addView(column(surface).apply{addView(state);addView(gap(2));addView(sub)},LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(9)})
        }
        body.addView(directionCard,matchWrap())
        body.addView(gap(7))

        val legend=row(bg).apply{gravity=Gravity.CENTER}
        legend.addView(status("↑  Lên",teal,ThemeManager.soft(this@OperationsActivity)),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)})
        legend.addView(status("↓  Xuống",blue,ThemeManager.soft(this@OperationsActivity)),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(1);marginEnd=dp(1)})
        legend.addView(status("↕  Hai chiều",navy,ThemeManager.soft(this@OperationsActivity)),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)})
        body.addView(legend,matchWrap())
        body.addView(gap(8))

        val detailsBox=column(bg)
        body.addView(detailsBox,matchWrap())
        fun renderDetails(network:String){
            detailsBox.removeAllViews()
            detailsBox.addView(details(listOf(
                "Mạng" to network,
                "Cửa sổ cache" to "Tối đa 45 ngày",
                "Dữ liệu chờ gửi" to LocalLogManager.pendingCount(this).toString(),
                "Phiên bản" to BuildConfig.VERSION_NAME,
                "Service" to "Google Sheets / GAS"
            )))
        }
        renderDetails(if(online)"Tốt" else "Đang chờ")

        val handler=android.os.Handler(android.os.Looper.getMainLooper())
        val ticker=object:Runnable{
            override fun run(){
                if(screenState!="SYNC")return
                val d=SyncDirectionTracker.snapshot()
                if(!online){
                    arrow.text="—";arrow.setTextColor(muted);state.text="Chờ kết nối";sub.text="Sẽ tự tiếp tục khi mạng trở lại"
                    syncStatusText?.text="Chờ"
                }else{
                    arrow.text=d.symbol;arrow.setTextColor(if(d.active)teal else green);state.text=d.label
                    sub.text=when{
                        d.uploading&&d.downloading->"Đang gửi thay đổi và nhận dữ liệu mới"
                        d.uploading->"Đang gửi thay đổi từ PDA lên hệ thống"
                        d.downloading->"Đang nhận snapshot/revision mới về PDA"
                        else->"Dữ liệu trên máy đã sẵn sàng"
                    }
                    syncStatusText?.text=if(d.active)"${d.symbol} ${d.shortLabel}" else "Sẵn sàng"
                }
                handler.postDelayed(this,250)
            }
        }
        handler.post(ticker)

        api.call("sync_status"){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            online=r.ok
            lastConnected=r.ok
            refreshHeaderConnection()
            renderDetails(if(r.ok)"Tốt" else "Mất kết nối")
            if(!r.ok) TopNotice.show(this,"Mất kết nối. Dữ liệu sẽ tự đồng bộ khi mạng trở lại.",TopNotice.Kind.WARNING)
        }}
        attach(root,body)
    }

''',
    'sync direction screen',
)

# Tapping the currently selected parent tab must reset any child screen to that tab's root.
old_nav = '''    private fun navigateTab(target:String){
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
'''
new_nav = '''    private fun navigateTab(target:String){
        if(target==activeTab() && isRootScreen())return
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
'''
if text.count(old_nav) != 1:
    raise SystemExit(f"S18 navigateTab anchor expected 1, got {text.count(old_nav)}")
text = text.replace(old_nav, new_nav, 1)

# S13 already owns HISTORY_DETAIL -> historyScreen() in navigateBack(). Assert it remains present;
# dual-edge gesture simply calls the same navigateBack() path from either edge.
if '            "HISTORY_DETAIL"->historyScreen()\n' not in text:
    raise SystemExit("S18 expected S13 HISTORY_DETAIL back route is missing")

activity.write_text(text, encoding="utf-8")
print("S18 sync-direction + dual-edge navigation + parent-tab reset patch applied")
