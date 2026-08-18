#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT / "google-apps-script/PICK_PACK_API.gs"
text=path.read_text(encoding="utf-8")
old="api_version:'0.4.2',sheet_read:rows.length>1"
new="api_version:'0.4.2',report_engine:'S12_CURRENT_DAY',sheet_read:rows.length>1"
if text.count(old)!=1:
    raise SystemExit(f"S12 GAS health anchor expected 1, got {text.count(old)}")
path.write_text(text.replace(old,new,1),encoding="utf-8")
print("S12 GAS health marker applied")
