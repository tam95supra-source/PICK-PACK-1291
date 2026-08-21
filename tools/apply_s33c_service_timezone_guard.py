#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'service/src'
changed=[]
for p in SRC.rglob('*.ts'):
    s=p.read_text(encoding='utf-8')
    n=s.replace('Asia/Bangkok','Asia/Ho_Chi_Minh')
    if n!=s:
        p.write_text(n,encoding='utf-8')
        changed.append(str(p.relative_to(ROOT)))
left=[]
for p in SRC.rglob('*.ts'):
    if 'Asia/Bangkok' in p.read_text(encoding='utf-8'):
        left.append(str(p.relative_to(ROOT)))
if left:
    raise SystemExit('S33C_SERVICE_TIMEZONE_DRIFT:'+','.join(left))
print('S33C Service timezone guard PASS; Asia/Ho_Chi_Minh canonical; changed='+(','.join(changed) if changed else 'none'))
