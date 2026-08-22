from pathlib import Path
import re

PATH = Path('app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt')
MARKER = 'S56_BETA53_OWNER_UI_STATUS_FIX'
s = PATH.read_text()


def once(old: str, new: str, label: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"S56 anchor {label!r}: expected 1, got {count}")
    s = s.replace(old, new, 1)


if MARKER not in s:
    once(
        'class OperationsActivity : Activity() {\n    // S55_BETA51_OWNER_REFRESH_HISTORY_FIX',
        'class OperationsActivity : Activity() {\n    // S56_BETA53_OWNER_UI_STATUS_FIX\n    // S55_BETA51_OWNER_REFRESH_HISTORY_FIX',
        'marker',
    )
    once(
        '    private var lastPingMs: Long? = null\n',
        '    private var lastPingMs: Long? = null\n    private var lastStatusUpdateAt: Long = 0L\n',
        'status timestamp field',
    )
    once(
        '                lastPingMs = status.latencyMs\n                refreshHeaderConnection()',
        '                lastPingMs = status.latencyMs\n                lastStatusUpdateAt = System.currentTimeMillis()\n                refreshHeaderConnection()',
        'status timestamp update',
    )
    once(
        '        fun submit(){val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét Mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);mnv.postDelayed({busy=false},600)}',
        '        fun submit(){val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét Mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;hideSoftKeyboard(mnv);loadEmployee(v);mnv.postDelayed({busy=false},600)}',
        'scan submit keyboard',
    )
    # Three employee-result renderers intentionally stop forcing the input field to focus.
    result_anchor = 'root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);scan.requestFocus()'
    if s.count(result_anchor) != 3:
        raise SystemExit(f"S56 anchor 'employee result keyboard': expected 3, got {s.count(result_anchor)}")
    s = s.replace(result_anchor, 'root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);hideKeyboardForResult(root,scan)')

    nav_old = '''        val items=mutableListOf(\n            Triple(R.drawable.ic_pp_business,"Nghiệp vụ","BUSINESS"),\n            Triple(R.drawable.ic_pp_history,"Lịch sử","HISTORY"),\n            Triple(R.drawable.ic_pp_sync,"Đồng bộ","SYNC"),\n            Triple(R.drawable.ic_pp_settings,"Cài đặt","SETTINGS")\n        )'''
    nav_new = '''        val items=mutableListOf(\n            Triple(R.drawable.ic_pp_business,"Nghiệp vụ","BUSINESS"),\n            Triple(R.drawable.ic_pp_staff,"Nhân sự","STAFF"),\n            Triple(R.drawable.ic_pp_history,"Lịch sử","HISTORY"),\n            Triple(R.drawable.ic_pp_settings,"Cài đặt","SETTINGS")\n        )'''
    once(nav_old, nav_new, 'bottom navigation')

    start = s.index('    private fun connectionSummary():String')
    end = s.index('    private fun activeTab()', start)
    new_header = r'''    private fun connectionSummary():String{val network=when(lastConnected){true->lastSyncLatencyMs?.let{"$it ms"}?:"Có mạng";false->"Mất kết nối";null->"Chưa kiểm tra"};val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(0);return "Mạng: $network | Đồng bộ: ${if(pending==0)"Hoàn tất" else "Đang chờ đồng bộ"} | Dịch vụ: ${serviceProviderFromRuntime()}"}
    private fun refreshHeaderConnection(){val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(lastProjectionPending);networkStatusText?.text=when(lastConnected){true->lastSyncLatencyMs?.let{"$it ms"}?:"Có mạng";false->"Mất mạng";null->"—"};syncStatusText?.text=if(pending>0)"Đang chờ" else if(lastConnected==true)"Hoàn tất" else "Đang chờ";serviceStatusText?.text=serviceProviderFromRuntime()}
    private fun headerStatusChip(iconRes:Int,label:String,valueView:TextView,click:()->Unit)=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(6),dp(6),dp(6),dp(6));background=round(Color.argb(32,255,255,255),13);isClickable=true;isFocusable=true;setOnClickListener{click()};addView(ImageView(this@OperationsActivity).apply{setImageResource(iconRes);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(2),dp(2),dp(2),dp(2))},size(dp(22),dp(22)));addView(column(Color.TRANSPARENT).apply{addView(txt(label,7.2f,Color.argb(210,255,255,255),false).apply{maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,8,1,android.util.TypedValue.COMPLEX_UNIT_SP)});addView(valueView.apply{maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,10,1,android.util.TypedValue.COMPLEX_UNIT_SP)})},LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(4)})}
    private fun greetingText():String{val h=java.time.LocalTime.now(ZoneId.of("Asia/Ho_Chi_Minh")).hour;val part=when(h){in 5..10->"sáng";in 11..13->"trưa";in 14..17->"chiều";else->"tối"};return "Chào buổi $part, ${name.ifBlank{login}}"}
    private fun appBar(title:String)=column(Color.TRANSPARENT).apply{setPadding(dp(16),dp(11),dp(16),dp(12));background=gradient(navy,accent,0);val identity=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL};if(!isRootScreen())identity.addView(ImageView(this@OperationsActivity).apply{setImageResource(R.drawable.ic_pp_back);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(7),dp(7),dp(7),dp(7));setOnClickListener{navigateBack()}},size(dp(36),dp(36)));identity.addView(txt(greetingText(),16f,Color.WHITE,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END},LinearLayout.LayoutParams(0,-2,1f).apply{if(!isRootScreen())marginStart=dp(3)});identity.addView(ImageView(this@OperationsActivity).apply{contentDescription="Làm mới và đồng bộ dữ liệu";setImageResource(R.drawable.ic_pp_refresh_round);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(7),dp(7),dp(7),dp(7));setOnClickListener{manualRefreshFromHeader(this)}},size(dp(36),dp(36)));addView(identity,matchWrap());addView(gap(10));val statuses=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER};val net=txt("—",9f,Color.WHITE,true);networkStatusText=net;val syn=txt("—",9f,Color.WHITE,true);syncStatusText=syn;val svc=txt("—",9f,Color.WHITE,true);serviceStatusText=svc;statuses.addView(headerStatusChip(R.drawable.ic_pp_network,"Mạng",net){showHeaderStatusDetail("NETWORK")},LinearLayout.LayoutParams(0,dp(44),1f).apply{marginEnd=dp(3)});statuses.addView(headerStatusChip(R.drawable.ic_pp_sync,"Đồng bộ",syn){showHeaderStatusDetail("SYNC")},LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(2);marginEnd=dp(2)});statuses.addView(headerStatusChip(R.drawable.ic_pp_service,"Dịch vụ",svc){showHeaderStatusDetail("SERVICE")},LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3)});addView(statuses,matchWrap());refreshHeaderConnection()}
'''.replace('\\"','"')
    s = s[:start] + new_header + s[end:]

    helper_anchor = '    private fun manualRefreshFromHeader(icon:ImageView){\n'
    helpers = r'''    private fun hideSoftKeyboard(view:View){(getSystemService(android.content.Context.INPUT_METHOD_SERVICE) as? android.view.inputmethod.InputMethodManager)?.hideSoftInputFromWindow(view.windowToken,0)}
    private fun hideKeyboardForResult(root:View,input:EditText){input.clearFocus();root.isFocusableInTouchMode=true;root.requestFocus();input.post{hideSoftKeyboard(input)}}
    private fun bytesVi(v:Long):String=when{v<1024->"$v byte";v<1024L*1024->String.format(java.util.Locale.US,"%.1f KB",v/1024.0);else->String.format(java.util.Locale.US,"%.1f MB",v/(1024.0*1024.0))}
    private fun statusTimeVi(v:Long):String=if(v<=0L)"Chưa có" else runCatching{java.time.Instant.ofEpochMilli(v).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss"))}.getOrDefault("Chưa có")
    private fun authorityViHeader(v:String):String=when(v.uppercase()){ "SERVICE_PRIMARY"->"Cloudflare là dịch vụ chính";"GOOGLE_FALLBACK"->"Google Drive đang dự phòng";"RECONCILING"->"Đang đối chiếu lại dữ liệu";"OFFLINE_LOCAL"->"Chỉ làm việc trên PDA";else->"Chưa xác định" }
    private fun routeViHeader(v:String):String=when(v.uppercase()){ "SERVICE_D1_DIRECT"->"Kết nối trực tiếp Cloudflare";"SERVICE_D1_PENDING"->"Cloudflare đang chờ đồng bộ";"GOOGLE_FALLBACK","GAS_COMPAT"->"Kết nối Google Drive dự phòng";"UNRESOLVED"->"Chưa xác định đường kết nối";else->if(v.isBlank())"Chưa xác định" else "Đang xử lý kết nối" }
    private fun runtimeErrorVi(v:String):String{val x=v.uppercase();return when{v.isBlank()->"Không có lỗi gần nhất";x.contains("SESSION_EXCHANGE")->"Chưa tạo được phiên kết nối tới Cloudflare";x.contains("DISCOVERY_WARMING")->"Ứng dụng đang xác định dịch vụ dữ liệu";x.contains("SERVICE_SESSION_UNAVAILABLE")->"Phiên Cloudflare chưa sẵn sàng";x.contains("AUTHORITY_NOT_SERVICE_PRIMARY")->"Cloudflare hiện không giữ quyền ghi chính";x.contains("NETWORK")||x.contains("TIMEOUT")->"Kết nối mạng tới dịch vụ bị gián đoạn";else->"Có lỗi kết nối gần nhất; bấm làm mới để kiểm tra lại"}}
    private fun showHeaderStatusDetail(kind:String){
        val runtime=api.runtimeStatus();val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(lastProjectionPending);val flow=SyncDirectionTracker.snapshot();val provider=serviceProviderFromRuntime();val network=when(lastConnected){true->"Đang kết nối";false->"Mất kết nối";null->"Chưa kiểm tra"}
        val title=when(kind){"NETWORK"->"Chi tiết Mạng";"SYNC"->"Chi tiết Đồng bộ";else->"Chi tiết Dịch vụ"}
        val rows=when(kind){
            "NETWORK"->listOf("Trạng thái" to network,"Độ trễ" to (lastSyncLatencyMs?.let{"$it mili giây"}?:"Chưa đo"),"Lần kiểm tra gần nhất" to statusTimeVi(lastStatusUpdateAt),"Dịch vụ đang dùng" to provider)
            "SYNC"->listOf("Trạng thái" to (if(pending>0)"Còn dữ liệu chờ đồng bộ" else if(flow.active)flow.label else if(lastConnected==true)"Đã đồng bộ" else "Đang chờ kết nối"),"Mục còn chờ" to pending.toString(),"Hoạt động hiện tại" to flow.label,"Đồng bộ gần nhất" to (lastSyncE2eMs?.let{"$it mili giây"}?:"Chưa đo"),"Dữ liệu đã gửi" to bytesVi(flow.uploadedBytes),"Dữ liệu đã nhận" to bytesVi(flow.downloadedBytes),"Dịch vụ đang dùng" to provider)
            else->listOf("Dịch vụ đang dùng" to provider,"Chế độ dữ liệu" to authorityViHeader(runtime.optString("authority_mode")),"Tuyến kết nối" to routeViHeader(runtime.optString("route")),"Phiên dịch vụ" to (if(runtime.optBoolean("service_session",false))"Đã sẵn sàng" else "Chưa sẵn sàng"),"Tình trạng lỗi" to runtimeErrorVi(runtime.optString("last_error")),"Địa chỉ kết nối" to runtime.optString("service_url").ifBlank{"Không có khi OFFLINE"})
        }
        val note=when(kind){"NETWORK"->"Mạng thể hiện khả năng ứng dụng liên lạc với hệ thống dữ liệu, không chỉ việc PDA có Wi‑Fi hay 4G.";"SYNC"->"Đồng bộ cho biết dữ liệu trên PDA đã được gửi lên và dữ liệu mới từ hệ thống đã được nhận về hay chưa.";else->"Cloudflare là dịch vụ chính; Google Drive là đường dự phòng; OFFLINE nghĩa là hiện tại ứng dụng không liên lạc được với dịch vụ dữ liệu."}
        val box=column(surface).apply{setPadding(dp(14),dp(10),dp(14),dp(8));addView(details(rows),matchWrap());addView(gap(8));addView(info(note),matchWrap())}
        AlertDialog.Builder(this).setTitle(title).setView(ScrollView(this).apply{addView(box)}).setPositiveButton("ĐÓNG",null).show()
    }

'''.replace('\\"','"')
    once(helper_anchor, helpers + helper_anchor, 'status detail helpers')

    provider_start = s.index('    private fun serviceProviderFromRuntime():String{')
    provider_end = s.index('\n    }', provider_start) + len('\n    }')
    provider_new = '''    private fun serviceProviderFromRuntime():String{\n        if(lastConnected==false)return "OFFLINE"\n        val st=api.runtimeStatus();val mode=st.optString("authority_mode");val route=st.optString("route");val url=st.optString("service_url")\n        return when{\n            mode=="GOOGLE_FALLBACK"||route=="GOOGLE_FALLBACK"||route=="GAS_COMPAT"->"Google Drive"\n            mode=="SERVICE_PRIMARY"||mode=="RECONCILING"||route.startsWith("SERVICE_")||url.isNotBlank()->"Cloudflare"\n            else->"OFFLINE"\n        }\n    }'''
    s = s[:provider_start] + provider_new + s[provider_end:]

# Contract validation also runs when the patch is already materialized.
required = [
    MARKER,
    'Triple(R.drawable.ic_pp_staff,"Nhân sự","STAFF")',
    'R.drawable.ic_pp_refresh_round',
    'showHeaderStatusDetail("NETWORK")',
    'showHeaderStatusDetail("SYNC")',
    'showHeaderStatusDetail("SERVICE")',
    'private fun hideKeyboardForResult',
    '->"Google Drive"',
    '->"Cloudflare"',
    'return "OFFLINE"',
]
for token in required:
    if token not in s:
        raise SystemExit(f'S56 missing contract: {token}')
if 'Triple(R.drawable.ic_pp_sync,"Đồng bộ","SYNC")' in s:
    raise SystemExit('S56 sync bottom tab still present')
if s.count('hideKeyboardForResult(root,scan)') != 3:
    raise SystemExit('S56 employee-result keyboard contract mismatch')

PATH.write_text(s)
print('S56 Beta53 owner UI/status patch applied or already present')
