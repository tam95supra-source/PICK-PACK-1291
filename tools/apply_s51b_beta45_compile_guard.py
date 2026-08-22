#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
UPD = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/UpdateManager.kt"
MARK = "S51B_BETA45_COMPILE_GUARD"

s = OPS.read_text(encoding="utf-8")
old = "            val network=networkHeaderText()\n"
new = "            val net=DeviceNetworkStatus.snapshot(this)\n            val network=net.header(lastLatencyMs)\n"
if old in s:
    s = s.replace(old, new, 1)
elif "val net=DeviceNetworkStatus.snapshot(this)" not in s:
    raise SystemExit("S51B network status anchor missing")

if MARK not in s:
    anchor = "    // S51_BETA45_MANUAL_UPDATE_SYNC_DETAIL_VI: detailed Vietnamese sync view shared by all roles.\n"
    if anchor not in s:
        raise SystemExit("S51B S51 marker missing")
    s = s.replace(anchor, "    // " + MARK + "\n" + anchor, 1)
OPS.write_text(s, encoding="utf-8")

# Fail closed across the entire materialized Android source: no automatic updater call may survive.
for path in (ROOT / "app/src/main/java").rglob("*.kt"):
    if path == UPD:
        continue
    text = path.read_text(encoding="utf-8")
    if "UpdateManager.check(" in text:
        raise SystemExit("S51B automatic update call still present: " + str(path))

out = OPS.read_text(encoding="utf-8")
if "val net=DeviceNetworkStatus.snapshot(this)" not in out or "val network=net.header(lastLatencyMs)" not in out:
    raise SystemExit("S51B detailed Sync network contract missing")
if "networkHeaderText()" in out:
    raise SystemExit("S51B obsolete network helper still present")
print("Applied S51B Beta45 compile guard: existing network snapshot + global no-auto-update gate")
