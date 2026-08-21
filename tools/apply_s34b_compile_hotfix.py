#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=OPS.read_text(encoding='utf-8')
if 'S34_OWNER_SIX_REQUESTS' not in s:
    raise SystemExit('S34B requires S34 first')
s=s.replace('{scanScreen()}','{employeeScan()}')
if 'scanScreen()' in s:
    raise SystemExit('S34B unknown scanScreen reference remains')
OPS.write_text(s,encoding='utf-8')
print('Applied S34B compile hotfix: business QR card uses employeeScan')
