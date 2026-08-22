#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
MARK = "S54B_BETA48_SETTINGS_LOG_FIX"

s = OPS.read_text(encoding="utf-8")
if MARK in s:
    print("S54B already applied")
    raise SystemExit(0)

start = s.find("    private fun settingsScreen(){")
end = s.find("\n    private fun ", start + 20)
if start < 0 or end < 0:
    raise SystemExit("S54B settingsScreen boundaries not found")
block = s[start:end]

# Device name now belongs to Sync > ỨNG DỤNG, so remove the old Settings device block.
old_device = '''        body.addView(section("Thiết bị"))
        body.addView(info("Android ${Build.VERSION.RELEASE} • ${Build.MANUFACTURER} ${Build.MODEL}"))
'''
if old_device in block:
    block = block.replace(old_device, "", 1)

# Add useful local log footprint immediately below the Nhật ký heading.
log_heading = '        body.addView(section("Nhật ký"))\n'
if log_heading not in block:
    raise SystemExit("S54B Nhật ký heading not found")
log_details = '        body.addView(details(listOf("Nhật ký trên thiết bị" to LocalLogManager.summary(this))))\n'
if log_details not in block:
    block = block.replace(log_heading, log_heading + log_details, 1)

if 'body.addView(section("Thiết bị"))' in block:
    raise SystemExit("S54B duplicate Settings device section remains")
if "LocalLogManager.summary(this)" not in block:
    raise SystemExit("S54B log summary missing")

block = block.replace("        module=\"SETTINGS\"\n", "        // S54B_BETA48_SETTINGS_LOG_FIX\n        module=\"SETTINGS\"\n", 1)
s = s[:start] + block + s[end:]
OPS.write_text(s, encoding="utf-8")
print("Applied S54B Beta48 Settings/log fix")
