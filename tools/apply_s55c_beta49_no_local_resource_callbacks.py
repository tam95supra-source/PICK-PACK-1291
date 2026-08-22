#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S55C_BETA49_NO_LOCAL_RESOURCE_CALLBACKS'

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S55C already applied')
    raise SystemExit(0)

old1='''val next=returnedSessionContext(ctx,r);if(next!=null)renderEmployee(next,PdaLocalProjection.resourceOptions(this,mnv))else loadEmployee(mnv)'''
new1='''loadEmployee(mnv)'''
old2='''val next=returnedSessionContext(ctx,r);if(next!=null)renderEmployee(next,PdaLocalProjection.resourceOptions(this,ses.optString("mnv")))else loadEmployee(ses.optString("mnv"))'''
new2='''loadEmployee(ses.optString("mnv"))'''

n1=s.count(old1);n2=s.count(old2)
if n1!=1:
    raise SystemExit(f'S55C session-work callback anchor mismatch: {n1}')
s=s.replace(old1,new1,1)
if n2==1:
    s=s.replace(old2,new2,1)
elif n2>1:
    raise SystemExit(f'S55C attendance callback anchor mismatch: {n2}')

anchor='class OperationsActivity : Activity() {'
if anchor not in s:
    raise SystemExit('S55C class anchor missing')
s=s.replace(anchor,anchor+'\n    // '+MARK,1)
OPS.write_text(s,encoding='utf-8')
print(f'Applied S55C Beta49 local resource callback removal: session={n1}, attendance={n2}')
