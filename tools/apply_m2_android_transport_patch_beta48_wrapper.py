#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / "tools/apply_m2_android_transport_patch.py"), run_name="__main__")
runpy.run_path(str(ROOT / "tools/apply_s54b_beta48_settings_log_fix.py"), run_name="__main__")
print("Applied M2 full chain + S54B Beta48 settings/log fix")
