#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
api=ROOT/'google-apps-script/PICK_PACK_API.gs'
m2=ROOT/'google-apps-script/SERVICE_MIGRATION_M2.gs'

s=api.read_text()
marker="action === 'm2_service_url_update_internal'"
if marker not in s:
    anchor="    if (action === 'service_discovery') return ppJson_(ppM2Discovery_(body));\n"
    if s.count(anchor)!=1: raise SystemExit(f'GAS service_discovery anchor mismatch: {s.count(anchor)}')
    s=s.replace(anchor,anchor+"    if (action === 'm2_service_url_update_internal') return ppJson_(ppM2ServiceUrlUpdateInternal_(body));\n",1)
    api.write_text(s)

s=m2.read_text()
if 'function ppM2ServiceUrlUpdateInternal_' not in s:
    s += r'''

// S13_SERVICE_URL_ONLY_CONTROL — update hostname without changing authority epoch/mode/generation.
// This is intentionally not a general configuration route. It requires the existing GAS bridge
// secret and an owner-locked confirmation string, and it is valid only while SERVICE_PRIMARY.
function ppM2ServiceUrlUpdateInternal_(body){
  body=body||{};
  if(String(body.confirmation||'')!=='OWNER_LOCKED_M2_SERVICE_URL_ONLY')return {ok:false,error:'SERVICE_URL_CONFIRMATION_REQUIRED'};
  if(!ppM2BridgeSecret_()||String(body.bridge_secret||'')!==ppM2BridgeSecret_())return {ok:false,error:'SERVICE_URL_SECRET_INVALID'};
  if(ppM2Mode_()!=='SERVICE_PRIMARY')return {ok:false,error:'SERVICE_URL_UPDATE_REQUIRES_SERVICE_PRIMARY',authority_mode:ppM2Mode_()};
  const url=String(body.service_url||'').replace(/\/+$/,'');
  if(!ppM2ValidServiceUrl_(url))return {ok:false,error:'SERVICE_URL_INVALID'};
  const p=ppM2Props_(),before=ppM2ServiceUrl_();
  p.setProperty('PP_M2_SERVICE_URL',url);
  ppM2ClearServiceFailure_();
  const d=ppM2Discovery_({});
  return {ok:true,changed:before!==url,previous_service_url:before,service_url:d.service_url,authority_mode:d.authority_mode,authority_epoch:d.authority.authority_epoch,service_generation:d.service_generation};
}
'''
    m2.write_text(s)

print('Applied S13 fenced GAS Service URL control patch.')
