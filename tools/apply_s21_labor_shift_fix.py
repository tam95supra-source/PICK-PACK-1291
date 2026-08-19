#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=p.read_text()
MARK='S21_LABOR_SHIFT_APPLIED'
if MARK in s:
    print('S21 labor shift already applied.')
    raise SystemExit(0)

old='''val p=JSONObject().put("mnv",mnv).put("labor_type",type.selectedItem.toString()).put("time_marker",marker.selectedItem.toString()).put("deduct_staff",deduct.isChecked).put("note",note.text.toString().trim())'''
new='''// S21_LABOR_SHIFT_APPLIED: Service canonical LABOR_START requires the ACTIVE attendance shift.\n                val p=JSONObject().put("mnv",mnv).put("shift",s.optString("shift")).put("labor_type",type.selectedItem.toString()).put("time_marker",marker.selectedItem.toString()).put("deduct_staff",deduct.isChecked).put("note",note.text.toString().trim())'''
if s.count(old)!=1:
    raise SystemExit(f'S21 labor_start payload anchor mismatch: {s.count(old)}')
s=s.replace(old,new,1)
p.write_text(s)
print('Applied S21 labor shift fix.')
