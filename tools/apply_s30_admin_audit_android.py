#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TRANSPORT=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt'
API=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
MARK='S30_DURABLE_ADMIN_AUDIT'

s=TRANSPORT.read_text(encoding='utf-8')
if MARK not in s:
    anchor='''    fun acknowledgeFallback(eventId: String, ok: Boolean, error: String?) {\n'''
    fn='''    // S30_DURABLE_ADMIN_AUDIT: admin/history events use the same durable SQLite outbox.\n    // Only explicit safe fields are copied; raw password/verifier/token values are never serialized.\n    fun queueAdminAudit(action: String, payload: JSONObject, ok: Boolean, error: String?, actorLogin: String) {\n        if (action !in ADMIN_AUDIT_ACTIONS) return\n        val eventId = java.util.UUID.randomUUID().toString()\n        var targetType = "ADMIN_ACTION"\n        var targetId = actorLogin.ifBlank { "SELF" }\n        var targetLabel = ""\n        var detail = if (ok) "Thao tác thành công" else "Thao tác không thành công: ${error.orEmpty().take(160)}"\n        when (action) {\n            "staff_upsert", "staff_delete" -> {\n                targetType = "STAFF"; targetId = payload.optString("mnv").trim().ifBlank { targetId }; targetLabel = payload.optString("full_name").trim()\n                detail = if(action=="staff_delete") "Xóa nhân sự" else "Cập nhật thông tin nhân sự"\n            }\n            "account_upsert" -> {\n                targetType = "ACCOUNT"; targetId = payload.optString("login_id").trim().ifBlank { targetId }; targetLabel = payload.optString("display_name").trim()\n                detail = "Tạo / cập nhật tài khoản • vai trò ${payload.optString("role").take(40)}"\n            }\n            "account_status" -> {\n                targetType = "ACCOUNT"; targetId = payload.optString("login_id").trim().ifBlank { targetId }; detail = "Đổi trạng thái tài khoản thành ${payload.optString("status").take(40)}"\n            }\n            "change_email" -> { targetType = "ACCOUNT"; detail = "Đổi email tài khoản" }\n            "change_password" -> { targetType = "ACCOUNT"; detail = "Đổi mật khẩu tài khoản" }\n            "diagnostic_log" -> { targetType = "DIAGNOSTIC"; detail = "Gửi gói chẩn đoán" }\n        }\n        val safe = JSONObject()\n            .put("action", action)\n            .put("event_id", eventId)\n            .put("target_type", targetType)\n            .put("target_id", targetId)\n            .put("target_label", targetLabel)\n            .put("result", if(ok) "OK" else "FAILED")\n            .put("detail", detail.take(500))\n            .put("device_id", M2DeviceIdentity.id(app))\n        val request = JSONObject().put("action", "admin_audit").put("event_id", eventId).put("device_id", M2DeviceIdentity.id(app)).put("payload", safe)\n        store.enqueueMutation(request, false)\n        M2WorkScheduler.schedule(app)\n    }\n\n'''
    if anchor not in s: raise SystemExit('S30 transport audit function anchor missing')
    s=s.replace(anchor,fn+anchor,1)
    old='''        val items = store.pendingMutations(100)\n        if (items.isEmpty()) return true\n        return try {\n'''
    new='''        val pending = store.pendingMutations(100)\n        if (pending.isEmpty()) return true\n        var auditRetry = false\n        val auditItems = pending.filter { it.body.optString("action") == "admin_audit" }\n        for (item in auditItems) {\n            val safe = item.body.optJSONObject("payload") ?: JSONObject()\n            try {\n                val r = httpJson("$base/v1/admin-audit", safe, token)\n                if (r.code == 401) { prefs.edit().remove(KEY_SERVICE_TOKEN).apply(); return false }\n                if (r.ok) store.markMutationSynced(item.eventId) else {\n                    store.markMutationRetry(item.eventId, r.error ?: "ADMIN_AUDIT_HTTP_${r.code}", retryDelay(item.attemptCount)); auditRetry = true\n                    if (r.code >= 500 || r.code == -1) recordFailure()\n                }\n            } catch (t: Throwable) { store.markMutationRetry(item.eventId, t.message ?: "ADMIN_AUDIT_NETWORK", retryDelay(item.attemptCount)); auditRetry = true; recordFailure() }\n        }\n        val items = pending.filter { it.body.optString("action") != "admin_audit" }\n        if (items.isEmpty()) { if(!auditRetry) closeCircuit(); return !auditRetry }\n        return try {\n'''
    if old not in s: raise SystemExit('S30 transport outbox anchor missing')
    s=s.replace(old,new,1)
    old='''            if (!retryNeeded) closeCircuit()\n            !retryNeeded\n'''
    new='''            if (!retryNeeded && !auditRetry) closeCircuit()\n            !retryNeeded && !auditRetry\n'''
    if old not in s: raise SystemExit('S30 transport retry anchor missing')
    s=s.replace(old,new,1)
    old='''        val OPERATIONAL = setOf("enter", "exit", "resource_change", "labor_start", "labor_finish")\n        val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap")\n'''
    new='''        val OPERATIONAL = setOf("enter", "exit", "resource_change", "labor_start", "labor_finish")\n        val SYNC_ACTIONS = setOf("sync_status", "sync_day", "sync_bootstrap")\n        val ADMIN_AUDIT_ACTIONS = setOf("staff_upsert","staff_delete","account_upsert","account_status","change_email","change_password","diagnostic_log")\n'''
    if old not in s: raise SystemExit('S30 transport companion anchor missing')
    s=s.replace(old,new,1)
    TRANSPORT.write_text(s,encoding='utf-8')

s=API.read_text(encoding='utf-8')
if MARK not in s:
    anchor='''      if (result.code == 401) clearSession()\n'''
    add='''      if (action in M2ServiceTransport.ADMIN_AUDIT_ACTIONS) {\n          val actor = restoredAccount()?.optString("login_id").orEmpty()\n          m2Transport.queueAdminAudit(action, payload, result.ok, result.error, actor)\n      }\n'''
    if anchor not in s: raise SystemExit('S30 API audit anchor missing')
    s=s.replace(anchor,anchor+add,1)
    # Marker must be in API too so idempotence survives repeated Gradle preBuild transforms.
    s=s.replace('class BetaApiClient(context: Context) {','class BetaApiClient(context: Context) {\n    // S30_DURABLE_ADMIN_AUDIT',1)
    API.write_text(s,encoding='utf-8')

print('Applied S30 Android durable sanitized admin audit outbox')
