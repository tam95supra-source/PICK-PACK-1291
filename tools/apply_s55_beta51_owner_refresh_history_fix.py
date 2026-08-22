#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
MARK = "S55_BETA51_OWNER_REFRESH_HISTORY_FIX"

s = OPS.read_text(encoding="utf-8")
if MARK in s:
    print("S55 already applied")
    raise SystemExit(0)


def replace_once(old: str, new: str, name: str) -> None:
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"S55 {name} structural mismatch: {n}")
    s = s.replace(old, new, 1)


replace_once(
    "class OperationsActivity : Activity() {\n    // S54_BETA48_OWNER_10_FIXES",
    "class OperationsActivity : Activity() {\n    // S55_BETA51_OWNER_REFRESH_HISTORY_FIX\n    // S54_BETA48_OWNER_10_FIXES",
    "marker",
)

replace_once(
    "    private var historyLastCanonicalRefreshAt=0L\n",
    "    private var historyLastCanonicalRefreshAt=0L\n    private var manualRefreshInFlight=false\n",
    "refresh-state",
)

old_refresh = '''    private fun refreshHistoryCanonical(){
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
'''
new_refresh = '''    private fun refreshHistoryCanonical(force:Boolean=false){
        if(historySyncInFlight)return
        val now=System.currentTimeMillis();if(!force&&now-historyLastCanonicalRefreshAt<60_000L)return
        val before=operationalStore.revisions().toString()
        historySyncInFlight=true
        Thread{
            val ok=runCatching{M2BackgroundSync.catchUp(applicationContext)}.getOrDefault(false)
            val changed=ok&&before!=operationalStore.revisions().toString()
            runOnUiThread{
                historySyncInFlight=false;historyLastCanonicalRefreshAt=System.currentTimeMillis()
                if(ok&&screenState=="HISTORY"&&(force||changed))historyScreen()
            }
        }.start()
    }
'''
replace_once(old_refresh, new_refresh, "history-canonical-force")

replace_once(
    'addView(txt("Mã nhân viên $id • ${dash(e.optString("main_position"))}",10.7f,navy,true))',
    'addView(txt("$id • ${dash(e.optString("main_position"))}",10.7f,navy,true))',
    "staff-list-label",
)

replace_once(
    'val p=JSONObject().put("session_id",ses.optString("session_id")).put("idempotency_key",UUID.randomUUID().toString())',
    'val p=JSONObject().put("session_id",ses.optString("session_id")).put("mnv",mnv).put("idempotency_key",UUID.randomUUID().toString())',
    "work-mnv-fallback",
)
replace_once(
    'api.call("session_exit_guarded",JSONObject().put("session_id",ses.optString("session_id")).put("pda_exit_status",statusNow).put("idempotency_key",UUID.randomUUID().toString()))',
    'api.call("session_exit_guarded",JSONObject().put("session_id",ses.optString("session_id")).put("mnv",mnv).put("pda_exit_status",statusNow).put("idempotency_key",UUID.randomUUID().toString()))',
    "exit-mnv-fallback",
)

replace_once(
    '            e.contains("RESOURCE_CONFLICT")->"Tài nguyên vừa được người khác nhận. Hãy chọn tài nguyên khác."',
    '            e.contains("EXCLUSIVE_RESOURCE_CONFLICT")->"Tài nguyên vừa bị phiên hoặc máy khác giữ / dùng trước. Bản ghi cũ được dừng để tránh cấp trùng; hãy đồng bộ lại rồi tạo thao tác mới với tài nguyên còn trống."\n            e.contains("RESOURCE_CONFLICT")->"Tài nguyên vừa được người khác nhận. Hãy chọn tài nguyên khác."',
    "history-friendly-conflict",
)

# The current owner request removes the STAFF bottom navigation tab. Staff management remains reachable from admin flows.
replace_once(
    '            Triple(R.drawable.ic_pp_staff,"Nhân sự","STAFF"),\n',
    '',
    "remove-staff-tab",
)

manual = '''    private fun manualRefreshFromHeader(icon:ImageView){
        if(manualRefreshInFlight)return
        manualRefreshInFlight=true;icon.isEnabled=false;icon.alpha=.55f
        M2ImmediateOutbox.kick(this);foregroundSync.requestSync();refreshMasterCache();historyLastCanonicalRefreshAt=0L
        Thread{
            val ok=runCatching{M2BackgroundSync.catchUp(applicationContext)}.getOrDefault(false)
            runOnUiThread{
                manualRefreshInFlight=false;icon.isEnabled=true;icon.alpha=1f;historyLastCanonicalRefreshAt=System.currentTimeMillis()
                when(screenState){
                    "HISTORY"->historyScreen()
                    "SYNC"->syncScreen()
                    "EMPLOYEE","EMPLOYEE_LOADING","EMPLOYEE_LOOKUP_ERROR"->if(liveEmployeeMnv.isNotBlank())loadEmployee(liveEmployeeMnv)
                    "REPORT"->reportScreen()
                    else->refreshHeaderConnection()
                }
                TopNotice.show(this,if(ok)"Đã đồng bộ lại dữ liệu từ Service." else "Đã yêu cầu đồng bộ; dữ liệu sẽ tiếp tục gửi lại khi kết nối phù hợp.",if(ok)TopNotice.Kind.SUCCESS else TopNotice.Kind.WARNING)
            }
        }.start()
    }

'''
anchor = "    private fun serviceProviderFromRuntime():String{"
if s.count(anchor) != 1:
    raise SystemExit("S55 manual refresh anchor mismatch")
s = s.replace(anchor, manual + anchor, 1)

replace_once(
    ';addView(identity,matchWrap());addView(gap(10));val statuses=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER};',
    ';identity.addView(ImageView(this@OperationsActivity).apply{contentDescription="Đồng bộ lại dữ liệu";setImageResource(R.drawable.ic_pp_sync);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(8),dp(8),dp(8),dp(8));setOnClickListener{manualRefreshFromHeader(this)}},size(dp(36),dp(36)));addView(identity,matchWrap());addView(gap(10));val statuses=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER};',
    "header-refresh-icon",
)

# Expand current Service/direct-call errors into actionable Vietnamese messages instead of raw UNKNOWN-like codes.
error_anchor = 'private fun showError(raw:String){val msg=when{'
if s.count(error_anchor) != 1:
    raise SystemExit("S55 showError anchor mismatch")
insert = '''private fun showError(raw:String){val msg=when{
raw.contains("EXCLUSIVE_RESOURCE_CONFLICT")->"Tài nguyên vừa bị phiên hoặc máy khác giữ / dùng trước. Bản ghi này không tự gửi lại để tránh cấp trùng. Hãy bấm đồng bộ, quét lại nhân sự và chọn tài nguyên còn trống.";
raw.contains("PDA_IN_USE")->"PDA này đang được một phiên khác giữ. Hãy đồng bộ lại và chọn PDA khác.";
raw.contains("USER_PICK_IN_USE")->"User Pick này đang được phiên khác giữ. Hãy chọn User Pick khác.";
raw.contains("USER_PACK_IN_USE")->"User Pack này đang được phiên khác giữ. Hãy chọn User Pack khác.";
raw.contains("PACK_TABLE_IN_USE")->"Bàn Pack này đang được phiên khác giữ. Hãy chọn bàn khác.";
raw.contains("USER_PICK_ALREADY_USED_TODAY")->"User Pick này đã dùng hôm nay. Nếu hiện đã rảnh, dùng nút Phát lại user pick.";
raw.contains("USER_PACK_ALREADY_USED_TODAY")->"User Pack này đã dùng hôm nay. Nếu hiện đã rảnh, dùng nút Phát lại user pack.";
raw.contains("PACK_MAPPING_INVALID")->"Bàn Pack và User Pack không còn khớp cấu hình hiện tại. Hãy đồng bộ và chọn lại.";
raw.contains("OPEN_LABOR_BLOCKS_EXIT")->"Còn công nhật đang làm. Hoàn thành công nhật trước khi ra ca.";
raw.contains("PDA_EXIT_STATUS_REQUIRED")->"Cần chọn tình trạng PDA hiện tại trước khi ra ca.";
raw.contains("SESSION_NOT_FOUND")->"Phiên trên PDA chưa khớp phiên Service. Bấm đồng bộ rồi quét lại nhân sự.";
raw.contains("SESSION_NOT_ACTIVE")->"Phiên này không còn ACTIVE trên Service. Bấm đồng bộ rồi quét lại nhân sự.";
raw.contains("SESSION_WORK_CONFLICT")->"Phiên vừa thay đổi trên máy khác. Dữ liệu cũ không bị ghi đè; hãy đồng bộ rồi sửa lại.";
raw.contains("SESSION_EXIT_CONFLICT")->"Phiên vừa thay đổi trên máy khác nên chưa thể ra ca. Hãy đồng bộ rồi quét lại.";
raw.contains("SERVICE_DISCOVERY_UNAVAILABLE")->"Chưa lấy được địa chỉ Service. Kiểm tra mạng rồi bấm đồng bộ lại.";
raw.contains("SERVICE_NOT_WRITE_AUTHORITY")->"Service hiện chưa ở quyền ghi chính. Hãy đồng bộ lại trước khi thao tác.";
raw.contains("SUPERADMIN_REQUIRED")->"Thao tác này hiện yêu cầu quyền Superadmin trên Service.";
raw.contains("CORRECTION_TARGET_NOT_FOUND")->"Không tìm thấy bản ghi gốc cần sửa trên Service. Hãy đồng bộ lịch sử rồi mở lại.";
raw.contains("CORRECTION_CONFLICT")->"Bản ghi vừa thay đổi trên máy khác. Hãy đồng bộ rồi sửa lại.";
raw.isBlank()||raw.equals("UNKNOWN",true)->"Service chưa trả mã lỗi cụ thể. Hãy bấm đồng bộ và thử lại; nếu còn lỗi hãy gửi log.";
'''
s = s.replace(error_anchor, insert, 1)

OPS.write_text(s, encoding="utf-8")

# Contract gates for this patch.
out = OPS.read_text(encoding="utf-8")
checks = [
    MARK,
    'contentDescription="Đồng bộ lại dữ liệu"',
    'private fun manualRefreshFromHeader',
    'private fun refreshHistoryCanonical(force:Boolean=false)',
    'put("mnv",mnv).put("idempotency_key"',
    'raw.contains("EXCLUSIVE_RESOURCE_CONFLICT")',
]
for x in checks:
    if x not in out:
        raise SystemExit(f"S55 contract missing: {x}")
if 'Triple(R.drawable.ic_pp_staff,"Nhân sự","STAFF")' in out:
    raise SystemExit("S55 staff bottom tab still present")
if 'addView(txt("Mã nhân viên $id •' in out:
    raise SystemExit("S55 staff list prefix still present")
print("S55 source patch PASS")
