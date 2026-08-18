#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
# Preserve every approved UI/runtime transform before adding M2 transport behavior.
runpy.run_path(str(ROOT / "tools/apply_s10_ui_patch_in_place.py"), run_name="__main__")

path = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt"
s = path.read_text()
marker = "M2_SERVICE_TRANSPORT_APPLIED"
if marker in s:
    print("M2 Android transport already applied; skip.")
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
s = s.replace(anchor, anchor + "                    // Establish a parallel Service session only when dynamic discovery says Service is primary.\n                    m2Transport.loginFromPassword(login, password)\n", 1)

old = '''      val result = when (action) {
          "change_password" -> changePassword(payload)
          "account_upsert" -> accountUpsert(payload)
          else -> post(JSONObject(payload.toString()).apply { put("action", action) }, authenticated = true)
      }
'''
if s.count(old) != 1:
    raise SystemExit(f"M2 patch call anchor mismatch: {s.count(old)}")
new = '''      val m2 = if (action in M2ServiceTransport.OPERATIONAL) m2Transport.operational(action, payload) else null
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
print(f"Applied M2 dynamic Service transport patch: {path}")
