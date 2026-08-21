#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

# Legacy Admin rows used column C as the role namespace before the explicit account-status
# column was introduced. Blank explicit status therefore means ACTIVE, not DISABLED.
for rel in ['service/src/bootstrap.ts','service/src/bootstrap_resumable.ts']:
    p=ROOT/rel
    s=p.read_text()
    old='activeStatus(r["Trạng thái tài khoản"]||r["Tình trạng"]||"")'
    new='activeStatus((r["Trạng thái tài khoản"]||"").trim()||"ACTIVE")'
    if new in s:
        continue
    if s.count(old)!=1:
        raise SystemExit(f'S14 account import anchor mismatch {rel}: {s.count(old)}')
    p.write_text(s.replace(old,new,1))

# If Apps Script has not yet been re-authorized for script.external_request, that is a
# control-plane permission fault, not evidence that the Worker is unavailable. Do not
# advance the authority epoch and create a false Google fallback in that case.
p=ROOT/'google-apps-script/SERVICE_MIGRATION_M2.gs'
s=p.read_text()
marker='S14_EXTERNAL_REQUEST_AUTHORITY_GUARD'
if marker not in s:
    old="""    try{return ppM2BridgeMutation_(auth,body,action);}catch(err){
      const failures=ppM2RegisterServiceFailure_();
"""
    new="""    try{return ppM2BridgeMutation_(auth,body,action);}catch(err){
      // S14_EXTERNAL_REQUEST_AUTHORITY_GUARD: missing Apps Script OAuth permission is not a Worker outage.
      const detail=String(err&&err.message||err||'');
      if(detail.indexOf('script.external_request')>=0||detail.indexOf('permission to call UrlFetchApp.fetch')>=0){
        return {ok:false,error:'SERVICE_BRIDGE_PERMISSION_REQUIRED',retryable:true};
      }
      const failures=ppM2RegisterServiceFailure_();
"""
    if s.count(old)!=1:
        raise SystemExit(f'S14 GAS authority guard anchor mismatch: {s.count(old)}')
    p.write_text(s.replace(old,new,1))

print('Applied S14 authority/account integrity guards.')
