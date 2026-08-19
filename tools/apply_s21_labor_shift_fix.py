#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=p.read_text()
MARK='S21_LABOR_SHIFT_APPLIED'
if MARK in s:
    print('S21 labor shift already applied.')
    raise SystemExit(0)

# Patch the currently generated labor_start payload after S10..S20 composition.
# Keep the anchor narrow so UI refactors around the button do not invalidate the transform.
old='.put("mnv",e.optString("mnv")).put("labor_type",typeSpinner.selectedItem.toString())'
new='.put("mnv",e.optString("mnv")).put("shift",s.optString("shift"))/* S21_LABOR_SHIFT_APPLIED */.put("labor_type",typeSpinner.selectedItem.toString())'
if s.count(old)!=1:
    raise SystemExit(f'S21 labor_start payload anchor mismatch: {s.count(old)}')
s=s.replace(old,new,1)
p.write_text(s)
print('Applied S21 labor shift fix.')
