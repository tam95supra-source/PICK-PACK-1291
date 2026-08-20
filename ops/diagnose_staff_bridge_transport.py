#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import secrets
import sys

import install_staff_bridge_hmac as base

PROOF = pathlib.Path('ops/staff-bridge-transport-proof.json')


def add_pp_diag(doc, token):
    out=json.loads(json.dumps(doc)); main=base.find_main(out,'Pick Pack 1291 authoritative API')
    anchor="    const action = String(body.action || '').trim();\n"
    if anchor not in main['source']: base.fail('PP_DIAG_ANCHOR_MISSING')
    route=f'''    if (action === '__staff_bridge_transport_diag__' && String(body.diag_token || '') === '{token}') {{
      const secret=String(PropertiesService.getScriptProperties().getProperty('STAFF_BRIDGE_HMAC_SECRET')||'');
      const sig=secret?Utilities.computeHmacSha256Signature('bridge-selftest-v1',secret,Utilities.Charset.UTF_8).map(function(b){{return ('0'+((b+256)%256).toString(16)).slice(-2);}}).join(''):'';
      const sh=ppSheet_(PP.STAFF), vals=sh.getDataRange().getDisplayValues(); let row=0;
      for(let i=1;i<vals.length;i++) if(String(vals[i][0]||'').trim()==='909090') {{row=i+1;break;}}
      if(!row) return ppJson_({{ok:false,diag_error:'PROBE_EMPLOYEE_MISSING',secret_len:secret.length,selftest:sig}});
      const payload={{action:'staff-source-ping',event_id:'diag-'+Utilities.getUuid(),source_id:PP_BH_STAFF_BRIDGE.SOURCE_ID,source_tab:PP_BH_STAFF_BRIDGE.SOURCE_TAB,change_type:'DIAGNOSTIC_NOOP',row_start:row,row_end:row,col_start:1,col_end:6,old_codes:{{}},at:new Date().toISOString(),sent_at:new Date().toISOString()}};
      payload.hmac_sha256=ppBaoHangBridgeHmacHex_(payload,secret);
      try {{
        const res=UrlFetchApp.fetch(PP_BH_STAFF_BRIDGE.TARGET_URL,{{method:'post',contentType:'application/json',payload:JSON.stringify(payload),followRedirects:true,muteHttpExceptions:true}});
        const http=res.getResponseCode(); const text=String(res.getContentText()||''); let parsed={{}}; try{{parsed=JSON.parse(text||'{{}}');}}catch(_){{}}
        const err=String(parsed.error||'').slice(0,180).replace(/[^A-Za-z0-9_:. -]/g,'');
        return ppJson_({{ok:true,http:http,bridge_ok:parsed&&parsed.ok===true,changed:Number(parsed&&parsed.changed||0),bridge_error:err,response_json:!!parsed&&Object.keys(parsed).length>0,secret_len:secret.length,selftest:sig}});
      }} catch(err) {{ return ppJson_({{ok:false,diag_error:String(err&&err.message||err).slice(0,180).replace(/[^A-Za-z0-9_:. -]/g,''),secret_len:secret.length,selftest:sig}}); }}
    }}
'''
    main['source']=main['source'].replace(anchor,anchor+route,1); return out


def add_bh_diag(doc, token):
    out=json.loads(json.dumps(doc)); main=base.find_main(out,"const BH_PROJECT = 'bao-hang-1291';")
    anchor="    const action = String(body.action || '').trim();\n"
    if anchor not in main['source']: base.fail('BH_DIAG_ANCHOR_MISSING')
    route=f'''    if (action === '__staff_bridge_transport_diag__' && String(body.diag_token || '') === '{token}') {{
      const secret=String(PropertiesService.getScriptProperties().getProperty('STAFF_BRIDGE_HMAC_SECRET')||'');
      const sig=secret?Utilities.computeHmacSha256Signature('bridge-selftest-v1',secret,Utilities.Charset.UTF_8).map(function(b){{return ('0'+((b+256)%256).toString(16)).slice(-2);}}).join(''):'';
      return json_({{ok:true,secret_len:secret.length,selftest:sig}});
    }}
'''
    main['source']=main['source'].replace(anchor,anchor+route,1); return out


def temp_call(token, script_id, original, modified, route_token, desc):
    dep=''
    try:
        base.put_content(token,script_id,modified)
        v=base.create_version(token,script_id,desc)
        dep,url=base.create_temp_deployment(token,script_id,v,'TEMP DELETE ME '+desc)
        result=base.poll_post(url,{'action':'__staff_bridge_transport_diag__','diag_token':route_token},lambda x:'selftest' in x,30)
        return result
    finally:
        if dep: base.delete_deployment(token,script_id,dep)
        base.put_content(token,script_id,original)


def run():
    token=base.oauth_token(); pp_script=''.join(os.environ['GAS_SCRIPT_ID'].split())
    print(f'::add-mask::{pp_script}')
    pp=base.project_content(token,pp_script); bh=base.project_content(token,base.BH_SCRIPT_ID)
    ptoken=secrets.token_hex(24); btoken=secrets.token_hex(24); print(f'::add-mask::{ptoken}');print(f'::add-mask::{btoken}')
    bh_res=temp_call(token,base.BH_SCRIPT_ID,bh,add_bh_diag(bh,btoken),btoken,'BH staff bridge transport diagnostic')
    pp_res=temp_call(token,pp_script,pp,add_pp_diag(pp,ptoken),ptoken,'PP staff bridge transport diagnostic')
    secret_match=bool(pp_res.get('selftest')) and pp_res.get('selftest')==bh_res.get('selftest')
    proof={
      'status':'DIAGNOSED',
      'pp_secret_present':int(pp_res.get('secret_len') or 0)>=64,
      'bh_secret_present':int(bh_res.get('secret_len') or 0)>=64,
      'secret_match':secret_match,
      'receiver_http':int(pp_res.get('http') or 0),
      'receiver_noop_ok':pp_res.get('bridge_ok') is True,
      'receiver_changed':int(pp_res.get('changed') or 0),
      'receiver_error':str(pp_res.get('bridge_error') or pp_res.get('diag_error') or '')[:180],
      'response_json':pp_res.get('response_json') is True,
      'temporary_deployments_cleanup':'PASS',
      'verified_at':dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    PROOF.write_text(json.dumps(proof,indent=2)+'\n'); print(json.dumps(proof,separators=(',',':')))

if __name__=='__main__':
    try: run()
    except Exception as exc:
        PROOF.write_text(json.dumps({'status':'FAIL','stage':str(exc)[:160],'verified_at':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')
        print('TRANSPORT_DIAG=FAIL '+str(exc)[:160],file=sys.stderr);sys.exit(1)
