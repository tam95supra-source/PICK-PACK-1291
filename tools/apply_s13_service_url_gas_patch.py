#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
api=ROOT/'google-apps-script/PICK_PACK_API.gs'
m2=ROOT/'google-apps-script/SERVICE_MIGRATION_M2.gs'

s=api.read_text()
if "action === 'm2_service_url_update_internal'" not in s:
    anchor="    if (action === 'service_discovery') return ppJson_(ppM2Discovery_(body));\n"
    if s.count(anchor)!=1: raise SystemExit(f'GAS service_discovery anchor mismatch: {s.count(anchor)}')
    s=s.replace(anchor,anchor+
        "    if (action === 'm2_service_url_prepare_internal') return ppJson_(ppM2ServiceUrlPrepareInternal_(body));\n"+
        "    if (action === 'm2_service_url_update_internal') return ppJson_(ppM2ServiceUrlUpdateInternal_(body));\n",1)
    api.write_text(s)

s=m2.read_text()
if 'S13_DUAL_SERVICE_URL_BRIDGE' not in s:
    old="""function ppM2ServiceFetch_(path,payload){
  const url=ppM2ServiceUrl_(),secret=ppM2BridgeSecret_();
  if(!ppM2ValidServiceUrl_(url)||!secret)throw new Error('SERVICE_PRIMARY_NOT_CONFIGURED');
  const response=UrlFetchApp.fetch(url+path,{
    method:'post',contentType:'application/json',muteHttpExceptions:true,
    headers:{'x-gas-bridge-secret':secret},payload:JSON.stringify(payload||{})
  });
  const code=response.getResponseCode(),text=response.getContentText()||'{}';let json={};
  try{json=JSON.parse(text);}catch(_){json={ok:false,error:'SERVICE_BAD_JSON'};}
  return {code:code,json:json};
}
"""
    if s.count(old)!=1: raise SystemExit(f'GAS ppM2ServiceFetch anchor mismatch: {s.count(old)}')
    new="""// S13_DUAL_SERVICE_URL_BRIDGE: preserve Service-primary writes while workers.dev account hostname changes.
function ppM2NextServiceUrl_(){return String(ppM2Props_().getProperty('PP_M2_SERVICE_URL_NEXT')||'').replace(/\\/+$/,'');}
function ppM2ServiceFetch_(path,payload){
  const secret=ppM2BridgeSecret_(),urls=[ppM2ServiceUrl_(),ppM2NextServiceUrl_()].filter(function(v,i,a){return ppM2ValidServiceUrl_(v)&&a.indexOf(v)===i;});
  if(!urls.length||!secret)throw new Error('SERVICE_PRIMARY_NOT_CONFIGURED');
  let last=null;
  for(let i=0;i<urls.length;i++){
    try{
      const response=UrlFetchApp.fetch(urls[i]+path,{
        method:'post',contentType:'application/json',muteHttpExceptions:true,
        headers:{'x-gas-bridge-secret':secret},payload:JSON.stringify(payload||{})
      });
      const code=response.getResponseCode(),text=response.getContentText()||'{}';let json={};
      try{json=JSON.parse(text);}catch(_){json={ok:false,error:'SERVICE_BAD_JSON'};}
      last={code:code,json:json};
      if(code!==404&&code<500)return last;
    }catch(err){last={code:599,json:{ok:false,error:'SERVICE_NETWORK_ERROR',detail:String(err).slice(0,160)}};}
  }
  return last||{code:599,json:{ok:false,error:'SERVICE_UNAVAILABLE'}};
}
"""
    s=s.replace(old,new,1)

if 'function ppM2ServiceUrlPrepareInternal_' not in s:
    s += r'''

// S13_SERVICE_URL_ONLY_CONTROL — hostname switch only; never changes authority epoch/mode/generation.
function ppM2ServiceUrlControlAuth_(body){
  body=body||{};
  if(String(body.confirmation||'')!=='OWNER_LOCKED_M2_SERVICE_URL_ONLY')return 'SERVICE_URL_CONFIRMATION_REQUIRED';
  if(!ppM2BridgeSecret_()||String(body.bridge_secret||'')!==ppM2BridgeSecret_())return 'SERVICE_URL_SECRET_INVALID';
  if(ppM2Mode_()!=='SERVICE_PRIMARY')return 'SERVICE_URL_UPDATE_REQUIRES_SERVICE_PRIMARY';
  return '';
}
function ppM2ServiceUrlPrepareInternal_(body){
  const err=ppM2ServiceUrlControlAuth_(body);if(err)return {ok:false,error:err,authority_mode:ppM2Mode_()};
  const url=String((body||{}).service_url||'').replace(/\/+$/,'');if(!ppM2ValidServiceUrl_(url))return {ok:false,error:'SERVICE_URL_INVALID'};
  ppM2Props_().setProperty('PP_M2_SERVICE_URL_NEXT',url);
  return {ok:true,prepared:true,current_service_url:ppM2ServiceUrl_(),next_service_url:ppM2NextServiceUrl_(),authority_mode:ppM2Mode_(),authority_epoch:ppM2Epoch_(),service_generation:ppM2Generation_()};
}
function ppM2ServiceUrlUpdateInternal_(body){
  const err=ppM2ServiceUrlControlAuth_(body);if(err)return {ok:false,error:err,authority_mode:ppM2Mode_()};
  const url=String((body||{}).service_url||'').replace(/\/+$/,'');if(!ppM2ValidServiceUrl_(url))return {ok:false,error:'SERVICE_URL_INVALID'};
  const p=ppM2Props_(),before=ppM2ServiceUrl_();p.setProperty('PP_M2_SERVICE_URL',url);p.deleteProperty('PP_M2_SERVICE_URL_NEXT');ppM2ClearServiceFailure_();
  const d=ppM2Discovery_({});
  return {ok:true,changed:before!==url,previous_service_url:before,service_url:d.service_url,authority_mode:d.authority_mode,authority_epoch:d.authority.authority_epoch,service_generation:d.service_generation};
}
'''

m2.write_text(s)
print('Applied S13 fenced dual-URL GAS Service hostname patch.')
