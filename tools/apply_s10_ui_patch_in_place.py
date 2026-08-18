#!/usr/bin/env python3
from pathlib import Path
import runpy
import shutil

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
generated = ROOT / "app/build/generated/s10/vn/pickpack1291/app/beta/PatchedOperationsActivity.kt"

# S10 establishes the approved visual baseline in the ephemeral build workspace.
runpy.run_path(str(ROOT / "tools/apply_s10_ui_patch.py"), run_name="__main__")
if not generated.is_file():
    raise SystemExit("S10 generated OperationsActivity was not created")
shutil.copyfile(generated, source)
# S11 applies the owner-requested compact inner-screen and report composition on top.
runpy.run_path(str(ROOT / "tools/apply_s11_compact_report_patch.py"), run_name="__main__")
print(f"Applied S10 + S11 OperationsActivity patches in build workspace: {source}")
