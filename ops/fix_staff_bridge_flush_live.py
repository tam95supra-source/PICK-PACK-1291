#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import secrets
import sys

import install_staff_bridge_hmac as base

PROOF = pathlib.Path('ops/staff-bridge-hmac-live-proof.json')


def ensure_flush(doc):
    main = base.find_main(doc, 'Pick Pack 1291 authoritative API')
    src = main['source']
    start = src.index('function ppStaffUpsert_(auth,body){')
    mid = src.index('\nfunction ppStaffDelete_(auth,body){', start)
    end = src.index('\nfunction ppAuthenticate_(body)', mid)
    up, de = src[start:mid], src[mid:end]
    ua = "const bridge=ppBaoHangBridgeNotifyServiceStaffMutation_(eventId,row,oldCode,'UPSERT');"
    da = "const bridge=ppBaoHangBridgeNotifyServiceStaffMutation_(eventId,row,mnv,'DELETE');"
    if ua not in up or da not in de:
        base.fail('LIVE_BRIDGE_CALL_MISSING')
    if 'SpreadsheetApp.flush();' not in up:
        up = up.replace(ua, 'SpreadsheetApp.flush();' + ua, 1)
    if 'SpreadsheetApp.flush();' not in de:
        de = de.replace(da, 'SpreadsheetApp.flush();' + da, 1)
    main['source'] = src[:start] + up + de + src[end:]
    return doc


def probe_content(doc, probe_token):
    out = json.loads(json.dumps(doc))
    main = base.find_main(out, 'Pick Pack 1291 authoritative API')
    anchor = "    const action = String(body.action || '').trim();\n"
    if anchor not in main['source']:
        base.fail('PROBE_ROUTE_ANCHOR_MISSING')
    route = f'''    if (action === '__staff_bridge_flush_probe__' && String(body.probe_token || '') === '{probe_token}') {{
      const sh=ppSheet_(PP.STAFF), vals=sh.getDataRange().getDisplayValues(); let row=0;
      for(let i=1;i<vals.length;i++) if(String(vals[i][0]||'').trim()==='{base.TEST_EMPLOYEE}') {{ row=i+1; break; }}
      if(!row) return ppJson_({{ok:false,error:'PROBE_EMPLOYEE_MISSING'}});
      const original=vals[row-1].slice(0,12), marker=String(original[1]||'')+' [HMAC-FLUSH-PROBE]';
      const auth={{role:'ADMIN',login_id:String(original[10]||'tamnv2')}};
      const common={{mnv:String(original[0]),phone:String(original[2]),main_position:String(original[3]),supplier:String(original[4]),department:String(original[5]),site:String(original[6]),warehouse:String(original[7]),start_date:String(original[8]),note:String(original[9])}};
      const a=ppStaffUpsert_(auth,Object.assign({{}},common,{{event_id:'flush-probe-'+Utilities.getUuid(),full_name:marker}}));
      const b=ppStaffUpsert_(auth,Object.assign({{}},common,{{event_id:'flush-restore-'+Utilities.getUuid(),full_name:String(original[1])}}));
      sh.getRange(row,11,1,2).setValues([[original[10],original[11]]]); SpreadsheetApp.flush();
      const current=sh.getRange(row,1,1,12).getDisplayValues()[0];
      return ppJson_({{ok:true,marker_bridge:a&&a.result&&a.result.bao_hang_bridge,restore_bridge:b&&b.result&&b.result.bao_hang_bridge,source_restored:current.join('\\u001f')===original.join('\\u001f')}});
    }}
'''
    main['source'] = main['source'].replace(anchor, anchor + route, 1)
    changed = False
    for f in out.get('files', []):
        if f.get('type') == 'SERVER_JS' and 'function ppBaoHangBridgeNotifyServiceStaffMutation_' in f.get('source', ''):
            old = "return result && result.ok ? 'SENT' : (result && result.queued ? 'QUEUED' : 'FAILED');"
            if old in f['source']:
                f['source'] = f['source'].replace(old, 'return result;', 1)
                changed = True
    if not changed:
        base.fail('PROBE_RESULT_PATCH_MISSING')
    return out


def sanitize_bridge(value):
    if not isinstance(value, dict):
        return {'type': type(value).__name__, 'ok': False, 'changed': 0, 'queued': value == 'QUEUED'}
    raw_error = str(value.get('error') or '')
    known = ''
    for code in ['STAFF_BRIDGE_HMAC_INVALID','STAFF_BRIDGE_HMAC_STALE','STAFF_BRIDGE_OAUTH_REQUIRED','BH_BRIDGE_HMAC_NOT_CONFIGURED','STAFF_BRIDGE_SOURCE_MISMATCH']:
        if code in raw_error:
            known = code
            break
    return {
        'type': 'object',
        'ok': value.get('ok') is True,
        'changed': int(value.get('changed') or 0),
        'updated': int(value.get('updated') or 0),
        'created': int(value.get('created') or 0),
        'deactivated': int(value.get('deactivated') or 0),
        'queued': value.get('queued') is True,
        'error_code': known,
    }


def run():
    token = base.oauth_token()
    pp_script = ''.join(os.environ['GAS_SCRIPT_ID'].split())
    pp_dep = base.norm_deployment(os.environ['GAS_DEPLOYMENT_ID'])
    print(f'::add-mask::{pp_script}')
    print(f'::add-mask::{pp_dep}')

    live = base.project_content(token, pp_script)
    bh_live = base.project_content(token, base.BH_SCRIPT_ID)
    ps = base.server_sources(live)
    bs = base.server_sources(bh_live)
    if "HMAC_PROP: 'STAFF_BRIDGE_HMAC_SECRET'" not in ps or 'function ppBaoHangBridgeHmacHex_' not in ps:
        base.fail('LIVE_PICK_PACK_HMAC_MISSING')
    if "HMAC_PROP: 'STAFF_BRIDGE_HMAC_SECRET'" not in bs or 'staffSourceBridgeVerifySender_(body)' not in bs:
        base.fail('LIVE_BAO_HANG_HMAC_MISSING')

    patched = ensure_flush(json.loads(json.dumps(live)))
    base.put_content(token, pp_script, patched)
    version = base.create_version(token, pp_script, 'Pick Pack 1291 flush before signed staff bridge')
    base.update_existing_deployment(token, pp_script, pp_dep, version, 'Pick Pack 1291 live API')
    pp_url = base.production_web_url(token, pp_script, pp_dep)
    bh_url = base.production_web_url(token, base.BH_SCRIPT_ID, base.BH_DEPLOYMENT_ID)
    hp = base.poll_post(pp_url, {'action':'health'}, lambda x:x.get('ok') is True and x.get('sheet_read') is True, 25)
    hb = base.poll_post(bh_url, {'action':'ping'}, lambda x:x.get('ok') is True and x.get('project')=='bao-hang-1291', 25)
    if not (hp.get('ok') is True and hp.get('sheet_read') is True): base.fail('PICK_PACK_HEALTH_AFTER_FLUSH_FAILED')
    if not (hb.get('ok') is True and hb.get('project')=='bao-hang-1291'): base.fail('BAO_HANG_HEALTH_AFTER_FLUSH_FAILED')

    canonical = base.project_content(token, pp_script)
    probe_token = secrets.token_hex(24)
    print(f'::add-mask::{probe_token}')
    temp_dep = ''
    response = {}
    try:
        base.put_content(token, pp_script, probe_content(canonical, probe_token))
        pv = base.create_version(token, pp_script, 'TEMP signed staff flush probe')
        temp_dep, url = base.create_temp_deployment(token, pp_script, pv, 'TEMP DELETE ME signed staff flush probe')
        response = base.poll_post(url, {'action':'__staff_bridge_flush_probe__','probe_token':probe_token}, lambda x:x.get('ok') is True, 35)
    finally:
        if temp_dep:
            base.delete_deployment(token, pp_script, temp_dep)
        base.put_content(token, pp_script, canonical)

    marker = sanitize_bridge(response.get('marker_bridge'))
    restore = sanitize_bridge(response.get('restore_bridge'))
    proof = {
        'status': 'PASS' if response.get('ok') is True and response.get('source_restored') is True and marker['ok'] and marker['changed'] >= 1 and restore['ok'] and restore['changed'] >= 1 else 'FAIL',
        'mode': 'SIGNED_SOURCE_DRIVEN_STAFF_BRIDGE_V2_FLUSHED',
        'pick_pack_gas_version': version,
        'pick_pack_live_health': 'PASS',
        'bao_hang_live_health': 'PASS',
        'service_upsert_runtime': 'PASS' if marker['ok'] and marker['changed'] >= 1 else 'FAIL',
        'restore_runtime': 'PASS' if restore['ok'] and restore['changed'] >= 1 else 'FAIL',
        'marker': marker,
        'restore': restore,
        'source_restored': response.get('source_restored') is True,
        'temporary_deployments_cleanup': 'PASS',
        'verified_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    PROOF.write_text(json.dumps(proof, indent=2) + '\n')
    if proof['status'] != 'PASS':
        base.fail('FLUSH_RUNTIME_PROBE_FAILED')
    print(json.dumps(proof, separators=(',', ':')))


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        if not PROOF.exists():
            PROOF.write_text(json.dumps({'status':'FAIL','stage':str(exc)[:180],'verified_at':dt.datetime.now(dt.timezone.utc).isoformat()}, indent=2)+'\n')
        print('STAFF_BRIDGE_FLUSH=FAIL ' + str(exc)[:180], file=sys.stderr)
        sys.exit(1)
