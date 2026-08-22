#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S55C_BETA49_NO_LOCAL_RESOURCE_CALLBACKS'

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S55C already applied')
    raise SystemExit(0)

# Post-write callbacks must reload through Service instead of rendering stale local resource options.
old1='''val next=returnedSessionContext(ctx,r);if(next!=null)renderEmployee(next,PdaLocalProjection.resourceOptions(this,mnv))else loadEmployee(mnv)'''
new1='''loadEmployee(mnv)'''
old2='''val next=returnedSessionContext(ctx,r);if(next!=null)renderEmployee(next,PdaLocalProjection.resourceOptions(this,ses.optString("mnv")))else loadEmployee(ses.optString("mnv"))'''
new2='''loadEmployee(ses.optString("mnv"))'''
n1=s.count(old1);n2=s.count(old2)
if n1!=1: raise SystemExit(f'S55C session-work callback anchor mismatch: {n1}')
s=s.replace(old1,new1,1)
if n2==1: s=s.replace(old2,new2,1)
elif n2>1: raise SystemExit(f'S55C attendance callback anchor mismatch: {n2}')

# Local employee fast path may show identity/session context, but MUST NOT construct a resource-issuance
# screen from PdaLocalProjection. NOT_ENTERED stays identity-only until S56 Service master_options arrives.
old3='''val masters=if(ctx.optString("state")=="NOT_ENTERED")PdaLocalProjection.resourceOptions(this,mnv) else null
        renderEmployee(ctx,masters)
        return true'''
new3='''if(ctx.optString("state")=="NOT_ENTERED"){
            liveEmployeeMnv=mnv
            renderCachedEmployee(ctx.optJSONObject("employee")?:JSONObject())
        }else renderEmployee(ctx,null)
        return true'''
n3=s.count(old3)
if n3!=1: raise SystemExit(f'S55C local employee resource fast-path anchor mismatch: {n3}')
s=s.replace(old3,new3,1)

anchor='class OperationsActivity : Activity() {'
if anchor not in s: raise SystemExit('S55C class anchor missing')
s=s.replace(anchor,anchor+'\n    // '+MARK,1)
OPS.write_text(s,encoding='utf-8')
print(f'Applied S55C Beta49 no-local-resource: session={n1}, attendance={n2}, employee_fastpath={n3}')
