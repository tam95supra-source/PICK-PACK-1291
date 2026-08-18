#!/usr/bin/env python3
from pathlib import Path
import runpy
import shutil

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
generated = ROOT / "app/build/generated/s10/vn/pickpack1291/app/beta/PatchedOperationsActivity.kt"

# The standalone generator validates every important anchor before producing output.
runpy.run_path(str(ROOT / "tools/apply_s10_ui_patch.py"), run_name="__main__")
if not generated.is_file():
    raise SystemExit("S10 generated OperationsActivity was not created")
shutil.copyfile(generated, source)
print(f"Applied S10 patched OperationsActivity in build workspace: {source}")
