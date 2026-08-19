#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "tools/apply_s10_ui_patch_in_place.py"), run_name="__main__")

path = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt"
s = path.read_text()
marker = "M2_SERVICE_TRANSPORT_APPLIED"
if marker in s:
    print("M2 Android transport already applied; composing S19/S20/S21/S22/S23/S24/S25/S27/S29/S30/S31/S31B runtime fixes.")
    runpy.run_path(str(ROOT / "tools/apply_s19_m2_runtime_fix.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s20_pack_identity_fix.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s21_labor_shift_fix.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s22_pda_local_first_observability_wrapper.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s23_pda_import_ui.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s24_fcm_logout_patch.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s25_cache_sync_web_pda_fixes.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s27_projection_ack_gap_fix.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s29_owner_localfirst_history.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s30_canonical_admin_audit.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s31_service_first_hotpath.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "tools/apply_s31b_preserve_admin_audit.py"), run_name="__main__")
    raise SystemExit(0)

anchor = "    private val executor = Executors.newSingleThreadExecutor()\n"
if s.count(anchor) != 1:
    raise SystemExit(f"M2 patch anchor executor mismatch: {s.count(anchor)}")
s = s.replace(anchor, anchor + "    // M2_SERVICE_TRANSPORT_APPLIED: dynamic Service primary + GAS fallback.\n    private val m2Transport = M2ServiceTransport(appContext)\n", 1)

anchor = "    init {\n        synchronized(sessionLock) {\n            if (sharedToken == null) sharedToken = prefs.getString(KEY_TOKEN, null)\n        }\n    }\n"
if s.count(anchor) != 1:
    raise SystemExit(f"M2 patch init anchor mismatch: {s.count(anchor)}")
s = s.replace(anchor, "    init {\n        synchronized(sessionLock) {\n            if (sharedToken == null) sharedToken = prefs.getString(KEY_TOKEN, null)\n        }\n        M2ConnectivityMonitor.start(appContext)\n        M2WorkScheduler.schedule(appContext)\n    }\n", 1)

anchor = "                    if (newToken != null) persistSession(newToken, result.json.optJSONObject(\"account\"))\n"
if s.count(anchor) != 1:
    raise SystemExit(f"M2 patch login anchor mismatch: {s.count(anchor)}")
s = s.replace(anchor, anchor + "                    m2Transport.loginFromPassword(login, password)\n", 1)

old = '''      val result = when (action) {
          "change_password" -> changePassword(payload)
          "account_upsert" -> accountUpsert(payload)
          else -> post(JSONObject(payload.toString()).apply { put("action", action) }, authenticated = true)
      }
'''
if s.count(old) != 1:
    start = s.find('      val result = when (action) {')
    end = s.find('      if (result.ok) {', start)
    if start < 0 or end < 0:
        raise SystemExit("M2 patch call structural anchors missing")
    candidate = s[start:end]
    required = ['"change_password" -> changePassword(payload)', '"account_upsert" -> accountUpsert(payload)', 'else -> post(JSONObject(payload.toString()).apply { put("action", action) }, authenticated = true)']
    if not all(x in candidate for x in required):
        raise SystemExit("M2 patch call structural contract mismatch")
    old = candidate
new = '''      val m2 = when {
          action in M2ServiceTransport.OPERATIONAL -> m2Transport.operational(action, payload)
          action in M2ServiceTransport.SYNC_ACTIONS -> m2Transport.sync(action, payload)
          else -> null
      }
      val result = if (m2?.handled == true) {
          Result(m2.ok, m2.code, m2.json, m2.error)
      } else when (action) {
          "change_password" -> changePassword(payload)
          "account_upsert" -> accountUpsert(payload)
          else -> post(JSONObject(payload.toString()).apply { put("action", action) }, authenticated = true)
      }
'''
s = s.replace(old, new, 1)

path.write_text(s)
runpy.run_path(str(ROOT / "tools/apply_s19_m2_runtime_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s20_pack_identity_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s21_labor_shift_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s22_pda_local_first_observability_wrapper.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s23_pda_import_ui.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s24_fcm_logout_patch.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s25_cache_sync_web_pda_fixes.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s27_projection_ack_gap_fix.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s29_owner_localfirst_history.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s30_canonical_admin_audit.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s31_service_first_hotpath.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s31b_preserve_admin_audit.py"), run_name="__main__")
print(f"Applied M2 dynamic Service transport + S19/S20/S21/S22/S23/S24/S25/S27/S29/S30/S31/S31B runtime patches: {path}")
