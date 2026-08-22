#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
MARK = "S55_BETA48_LOG_SUMMARY_UI"

s = OPS.read_text(encoding="utf-8")
if MARK not in s:
    la = s.find("        fun loadApp(){")
    lb = s.find("\n        fun load(){", la)
    if la < 0 or lb < 0:
        raise SystemExit("S55 loadApp boundaries not found")
    block = s[la:lb]
    if "LocalLogManager.summary" not in block:
        close = block.rfind("}")
        if close < 0:
            raise SystemExit("S55 loadApp closing brace not found")
        extra = ';appBox.addView(gap(8));appBox.addView(section("NHẬT KÝ"));appBox.addView(details(listOf("Nhật ký trên thiết bị" to LocalLogManager.summary(this))))'
        block = block[:close] + extra + block[close:]
    block = block.replace("fun loadApp(){", "fun loadApp(){/* S55_BETA48_LOG_SUMMARY_UI */", 1)
    s = s[:la] + block + s[lb:]
    OPS.write_text(s, encoding="utf-8")
    print("Applied S55 Beta48 log metadata UI in Sync/Application area")
else:
    print("S55 Beta48 log summary UI already applied")

# Beta49 pre-S56 cleanup: callbacks after session edits/corrections must not re-render
# resource choices from PdaLocalProjection. S56 will still remove the primary editor local source.
runpy.run_path(str(ROOT / "tools/apply_s55c_beta49_no_local_resource_callbacks.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s55d_beta49_stale_resource_context.py"), run_name="__main__")
