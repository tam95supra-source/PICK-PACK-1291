#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=p.read_text()
marker='S23_PDA_IMPORT_UI_APPLIED'
if marker in s:
    print('S23 PDA Import UI already applied.')
    raise SystemExit(0)
anchor='''        if(isAdmin()){
            body.addView(gap(7))
            body.addView(primary("QUẢN LÝ TÀI KHOẢN",blue){accountManager()},matchWrap())
        }
'''
if s.count(anchor)!=1:
    raise SystemExit(f'S23 settings account anchor mismatch: {s.count(anchor)}')
addition=anchor+'''        // S23_PDA_IMPORT_UI_APPLIED: SUPERADMIN uses the shared Service Import Engine.
        if(isSuper()){
            body.addView(gap(7))
            body.addView(primary("IMPORT EXCEL",teal){
                startActivity(android.content.Intent(this,PdaImportActivity::class.java))
            },matchWrap())
        }
'''
s=s.replace(anchor,addition,1)
p.write_text(s)
print('Applied S23 SUPERADMIN PDA Import entry.')
