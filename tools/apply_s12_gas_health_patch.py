#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT / "google-apps-script/PICK_PACK_API.gs"
text=path.read_text(encoding="utf-8")
health_old="api_version:'0.4.2',sheet_read:rows.length>1"
health_new="api_version:'0.4.2',report_engine:'S12_CURRENT_DAY',sheet_read:rows.length>1"
get_old="return ppJson_({ok:true, service:'pick-pack-gsheet-api', mode:'APP_GSHEET', business_date:ppBusinessIso_()});"
get_new="return ppJson_({ok:true, service:'pick-pack-gsheet-api', mode:'APP_GSHEET', report_engine:'S12_CURRENT_DAY', business_date:ppBusinessIso_()});"
if text.count(health_old)!=1:
    raise SystemExit(f"S12 GAS health anchor expected 1, got {text.count(health_old)}")
if text.count(get_old)!=1:
    raise SystemExit(f"S12 GAS doGet anchor expected 1, got {text.count(get_old)}")
text=text.replace(health_old,health_new,1).replace(get_old,get_new,1)
path.write_text(text,encoding="utf-8")
print("S12 GAS health + public landing marker applied")
