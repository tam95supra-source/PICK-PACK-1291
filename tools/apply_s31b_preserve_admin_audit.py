#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT=Path(__file__).resolve().parents[1]
M2=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt'
s=M2.read_text(encoding='utf-8')
MARK='S31B_PRESERVE_ADMIN_AUDIT'
if MARK not in s:
    anchor='    fun acknowledgeFallback(eventId: String, ok: Boolean, error: String?) {'
    if anchor not in s: raise SystemExit('S31B audit insert anchor missing')
    fn='''    // S31B_PRESERVE_ADMIN_AUDIT / S30_CANONICAL_ADMIN_AUDIT: sanitized admin audit uses the same durable outbox.\n    fun audit(action:String,payload:JSONObject){\n        if(action !in ADMIN_AUDIT_ACTIONS)return\n        val eventId=java.util.UUID.randomUUID().toString()\n        val targetId=when(action){\n            "staff_upsert","staff_delete"->payload.optString("mnv")\n            "account_upsert","account_status","change_email","change_password"->payload.optString("login_id").ifBlank{payload.optString("target_login_id")}\n            else->""\n        }\n        val targetLabel=payload.optString("full_name").ifBlank{payload.optString("display_name")}.take(180)\n        val detail=when(action){\n            "staff_upsert"->"Thêm / cập nhật hồ sơ nhân sự"\n            "staff_delete"->"Xóa hồ sơ nhân sự"\n            "account_upsert"->"Tạo / cập nhật tài khoản"\n            "account_status"->"Thay đổi trạng thái tài khoản"\n            "change_email"->"Thay đổi email tài khoản"\n            "change_password"->"Thay đổi mật khẩu"\n            else->"Thao tác quản trị"\n        }\n        val body=JSONObject()\n            .put("action","admin_audit")\n            .put("event_id",eventId)\n            .put("target_type",if(action.startsWith("staff_"))"STAFF" else "ACCOUNT")\n            .put("target_id",targetId.take(180))\n            .put("target_label",targetLabel)\n            .put("result","OK")\n            .put("detail",detail)\n            .put("device_id",M2DeviceIdentity.id(app))\n            .put("occurred_at",java.time.Instant.now().toString())\n        store.enqueueMutation(body,false)\n        M2WorkScheduler.schedule(app)\n    }\n\n'''
    s=s.replace(anchor,fn+anchor,1)
    companion='val OPERATIONAL = setOf("enter", "exit", "resource_change", "labor_start", "labor_finish"); val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap")'
    if companion not in s: raise SystemExit('S31B companion anchor missing')
    s=s.replace(companion,'val ADMIN_AUDIT_ACTIONS = setOf("staff_upsert","staff_delete","account_upsert","account_status","change_email","change_password"); '+companion,1)
    M2.write_text(s,encoding='utf-8')

if 'fun audit(action:String,payload:JSONObject)' not in M2.read_text(encoding='utf-8'):
    raise SystemExit('S31B audit preservation failed')
print('Applied S31B: preserved canonical admin audit after strict Service-first transport rewrite')

runpy.run_path(str(ROOT/'tools/apply_s31d_runtime_bridge_compile_fix.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s32_local_history_flush_fix.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s33_owner_ui_sync_resources_wrapper.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s34_owner_six_requests.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s34b_compile_hotfix.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s34c_site1291_local_report.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s34d_compile_fixes.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s35_owner_ui_history_consistency_wrapper.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s36_perf_history_report_service.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s36b_compile_hotfix.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s37_move_service_telemetry_to_sync.py'),run_name='__main__')
runpy.run_path(str(ROOT/'tools/apply_s38_attendance_ui.py'),run_name='__main__')
