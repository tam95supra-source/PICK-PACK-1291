#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import secrets
import sys

import install_staff_bridge_hmac as base

PROOF = pathlib.Path('ops/staff-bridge-final-proof.json')
TEST_EMPLOYEE = '909090'
RESTORE_NAME = '1111q'


def add_finalize_route(doc, token):
    out = json.loads(json.dumps(doc))
    main = base.find_main(out, 'Pick Pack 1291 authoritative API')
    anchor = "    const action = String(body.action || '').trim();\n"
    if anchor not in main['source']:
        base.fail('FINALIZE_ROUTE_ANCHOR_MISSING')
    route = f'''    if (action === '__staff_bridge_finalize__' && String(body.finalize_token || '') === '{token}') {{
      const props=PropertiesService.getScriptProperties();
      props.deleteProperty('PP_BH_STAFF_PENDING_V1');
      ScriptApp.getProjectTriggers().forEach(function(t){{ if(t.getHandlerFunction()==='ppBaoHangStaffBridgeRetry') ScriptApp.deleteTrigger(t); }});
      const sh=ppSheet_(PP.STAFF), vals=sh.getDataRange().getDisplayValues(); let row=0;
      for(let i=1;i<vals.length;i++) if(String(vals[i][0]||'').trim()==='{TEST_EMPLOYEE}'){{row=i+1;break;}}
      if(!row) return ppJson_({{ok:false,error:'FINALIZE_EMPLOYEE_MISSING'}});
      const original=vals[row-1].slice(0,12);
      const auth={{role:'ADMIN',login_id:'staff-bridge-cleanup'}};
      const payload={{event_id:'staff-bridge-cleanup-'+Utilities.getUuid(),mnv:String(original[0]),full_name:'{RESTORE_NAME}',phone:String(original[2]),main_position:String(original[3]),supplier:String(original[4]),department:String(original[5]),site:String(original[6]),warehouse:String(original[7]),start_date:String(original[8]),note:String(original[9])}};
      const result=ppStaffUpsert_(auth,payload);
      SpreadsheetApp.flush();
      props.deleteProperty('PP_BH_STAFF_PENDING_V1');
      ScriptApp.getProjectTriggers().forEach(function(t){{ if(t.getHandlerFunction()==='ppBaoHangStaffBridgeRetry') ScriptApp.deleteTrigger(t); }});
      const current=sh.getRange(row,1,1,12).getDisplayValues()[0];
      const retryLeft=ScriptApp.getProjectTriggers().filter(function(t){{return t.getHandlerFunction()==='ppBaoHangStaffBridgeRetry';}}).length;
      return ppJson_({{ok:true,bridge:String(result&&result.result&&result.result.bao_hang_bridge||''),full_name:String(current[1]||''),pending_cleared:!props.getProperty('PP_BH_STAFF_PENDING_V1'),retry_triggers:retryLeft}});
    }}
'''
    main['source'] = main['source'].replace(anchor, anchor + route, 1)
    return out


def clean_authorizer(doc):
    out=[]
    for f in doc.get('files',[]):
        src=f.get('source','')
        if f.get('type')=='SERVER_JS' and (f.get('name')=='BAO_HANG_STAFF_BRIDGE_AUTHORIZE' or 'function authorizeBaoHangStaffBridgeTransport' in src):
            continue
        out.append(f)
    return {'files':out}


def run():
    token=base.oauth_token()
    pp_script=''.join(os.environ['GAS_SCRIPT_ID'].split())
    pp_dep=base.norm_deployment(os.environ['GAS_DEPLOYMENT_ID'])
    print(f'::add-mask::{pp_script}'); print(f'::add-mask::{pp_dep}')
    live=base.project_content(token,pp_script)
    src=base.server_sources(live)
    if "HMAC_PROP: 'STAFF_BRIDGE_HMAC_SECRET'" not in src or 'SpreadsheetApp.flush();const bridge=ppBaoHangBridgeNotifyServiceStaffMutation_' not in src:
        base.fail('FINALIZE_LIVE_BRIDGE_GATE_FAILED')
    route_token=secrets.token_hex(24); print(f'::add-mask::{route_token}')
    dep=''; result={}
    try:
        base.put_content(token,pp_script,add_finalize_route(live,route_token))
        v=base.create_version(token,pp_script,'TEMP staff bridge final cleanup')
        dep,url=base.create_temp_deployment(token,pp_script,v,'TEMP DELETE ME staff bridge final cleanup')
        result=base.poll_post(url,{'action':'__staff_bridge_finalize__','finalize_token':route_token},lambda x:x.get('ok') is True,30)
    finally:
        if dep: base.delete_deployment(token,pp_script,dep)
        # Restore clean production source without the owner-only authorizer helper.
        cleaned=clean_authorizer(live)
        base.put_content(token,pp_script,cleaned)

    if not (result.get('ok') is True and result.get('bridge')=='SENT' and result.get('full_name')==RESTORE_NAME and result.get('pending_cleared') is True and int(result.get('retry_triggers') or 0)==0):
        base.fail('FINALIZE_RUNTIME_FAILED')

    cv=base.create_version(token,pp_script,'Pick Pack 1291 final signed staff bridge')
    base.update_existing_deployment(token,pp_script,pp_dep,cv,'Pick Pack 1291 live API')
    url=base.production_web_url(token,pp_script,pp_dep)
    health=base.poll_post(url,{'action':'health'},lambda x:x.get('ok') is True and x.get('sheet_read') is True,25)
    if not (health.get('ok') is True and health.get('sheet_read') is True): base.fail('FINALIZE_HEALTH_FAILED')
    current=base.project_content(token,pp_script)
    current_src=base.server_sources(current)
    proof={
      'status':'PASS',
      'mode':'SIGNED_SOURCE_DRIVEN_STAFF_BRIDGE_V2',
      'pick_pack_gas_version':cv,
      'service_restore_bridge':'PASS',
      'restored_employee':TEST_EMPLOYEE,
      'restored_full_name':RESTORE_NAME,
      'pending_queue_cleared':True,
      'retry_trigger_cleared':True,
      'authorizer_helper_removed':'authorizeBaoHangStaffBridgeTransport' not in current_src,
      'live_health':'PASS',
      'temporary_deployment_cleanup':'PASS',
      'verified_at':dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    PROOF.write_text(json.dumps(proof,indent=2)+'\n')
    if not proof['authorizer_helper_removed']: base.fail('FINALIZE_AUTHORIZER_STILL_PRESENT')
    print(json.dumps(proof,separators=(',',':')))

if __name__=='__main__':
    try: run()
    except Exception as exc:
        if not PROOF.exists(): PROOF.write_text(json.dumps({'status':'FAIL','stage':str(exc)[:180],'verified_at':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')
        print('FINALIZE_STAFF_BRIDGE=FAIL '+str(exc)[:180],file=sys.stderr); sys.exit(1)
