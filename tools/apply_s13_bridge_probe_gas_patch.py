#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
api=ROOT/'google-apps-script/PICK_PACK_API.gs'
m2=ROOT/'google-apps-script/SERVICE_MIGRATION_M2.gs'

s=api.read_text()
route="    if (action === 'm2_bridge_probe_internal') return ppJson_(ppM2BridgeProbeInternal_(body));\n"
if route not in s:
    anchor="    if (action === 'service_discovery') return ppJson_(ppM2Discovery_(body));\n"
    if s.count(anchor)!=1: raise SystemExit(f'bridge probe route anchor mismatch: {s.count(anchor)}')
    s=s.replace(anchor,anchor+route,1)
    api.write_text(s)

s=m2.read_text()
replacement=r'''function ppM2BridgeProbeInternal_(body){
  body=body||{};
  if(String(body.confirmation||'')!=='OWNER_LOCKED_M2_BRIDGE_PROBE')return {ok:false,error:'BRIDGE_PROBE_CONFIRMATION_REQUIRED'};
  if(!ppM2BridgeSecret_()||String(body.bridge_secret||'')!==ppM2BridgeSecret_())return {ok:false,error:'BRIDGE_PROBE_CALLER_SECRET_INVALID'};
  const result=ppM2ServiceFetch_('/internal/gas-bridge-probe',{});
  return {
    ok:result.code===200&&!!(result.json&&result.json.ok),
    service_http_code:result.code,
    service_ok:!!(result.json&&result.json.ok),
    service_authority_mode:String(result.json&&result.json.authority&&result.json.authority.mode||''),
    service_authority_epoch:Number(result.json&&result.json.authority&&result.json.authority.authority_epoch||0),
    service_generation:String(result.json&&result.json.service_generation||''),
    service_error:String(result.json&&result.json.error||'').slice(0,120),
    service_detail:String(result.json&&result.json.detail||'').slice(0,180)
  };
}'''
start=s.find('function ppM2BridgeProbeInternal_(body){')
if start>=0:
    end=s.find('\n}',start)
    if end<0: raise SystemExit('bridge probe function end not found')
    end+=2
    s=s[:start]+replacement+s[end:]
else:
    s += '\n\n// S13 safe diagnostic: sanitized transport metadata only; no secret is returned.\n'+replacement+'\n'
m2.write_text(s)
print('Applied S13 safe GAS bridge probe with sanitized transport diagnostics.')
