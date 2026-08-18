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
# S11 applies the compact inner-screen/report baseline used by Beta11.
runpy.run_path(str(ROOT / "tools/apply_s11_compact_report_patch.py"), run_name="__main__")
# S12 incorporates real-PDA acceptance feedback: wrapped scanner fields, compact density,
# server-composed report rendering, ping and tappable history detail.
runpy.run_path(str(ROOT / "tools/apply_s12_real_pda_patch.py"), run_name="__main__")
# Compile-only hotfix preserves helper functions that the S12 density block intentionally reuses.
runpy.run_path(str(ROOT / "tools/apply_s12_compile_hotfix.py"), run_name="__main__")
print(f"Applied S10 + S11 + S12 runtime patches in build workspace: {source}")
