#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BH_SCRIPT_ID = '12zMDmEl7EXcHOV7skWy8XY95Uk3k3zwSlv2A_aokbRWkyUoc-ArOxu55'
BH_DEPLOYMENT_ID = 'AKfycbwb8Hcdg7tp0jqHLZU6kW5hkEclDC9d29DGvPuwcxvZbR9t9xnrWzaIYe8UZET-D_yI'
STAFF_SHEET_ID = '1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78'
TEST_EMPLOYEE = '909090'
PROP = 'STAFF_BRIDGE_HMAC_SECRET'


def fail(msg):
    raise RuntimeError(msg)


def request(url, *, method='GET', headers=None, data=None, timeout=45):
    payload = None
    if data is not None:
        payload = data if isinstance(data, (bytes, bytearray)) else json.dumps(data, ensure_ascii=False).encode()
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=payload)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8', errors='replace')
            return r.status, raw
    except urllib.error.HTTPError as e:
        # Never print response bodies here: some provider errors can reflect submitted material.
        return e.code, ''


def api_json(token, url, *, method='GET', body=None, ok=(200,)):
    headers = {'Authorization': 'Bearer ' + token}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    code, raw = request(url, method=method, headers=headers, data=body)
    if code not in ok:
        fail(f'GOOGLE_API_HTTP_{code}')
    try:
        return json.loads(raw or '{}')
    except Exception:
        fail('GOOGLE_API_JSON_INVALID')


def oauth_token():
    fields = urllib.parse.urlencode({
        'client_id': os.environ['GOOGLE_OAUTH_CLIENT_ID'],
        'client_secret': os.environ['GOOGLE_OAUTH_CLIENT_SECRET'],
        'refresh_token': os.environ['GOOGLE_OAUTH_REFRESH_TOKEN'],
        'grant_type': 'refresh_token',
    }).encode()
    code, raw = request(
        'https://oauth2.googleapis.com/token', method='POST',
        headers={'Content-Type': 'application/x-www-form-urlencoded'}, data=fields,
    )
    if code != 200:
        fail(f'OAUTH_HTTP_{code}')
    token = json.loads(raw).get('access_token', '')
    if not token:
        fail('OAUTH_TOKEN_MISSING')
    print(f'::add-mask::{token}')
    return token


def norm_deployment(raw):
    raw = ''.join(str(raw or '').split())
    m = re.search(r'/s/([^/]+)', raw)
    return m.group(1) if m else raw


def project_content(token, script_id):
    return api_json(token, f'https://script.googleapis.com/v1/projects/{script_id}/content')


def put_content(token, script_id, content):
    api_json(token, f'https://script.googleapis.com/v1/projects/{script_id}/content', method='PUT', body=content)


def create_version(token, script_id, desc):
    out = api_json(token, f'https://script.googleapis.com/v1/projects/{script_id}/versions', method='POST', body={'description': desc})
    n = int(out.get('versionNumber') or 0)
    if n <= 0:
        fail('VERSION_NUMBER_INVALID')
    return n


def get_deployment(token, script_id, deployment_id):
    return api_json(token, f'https://script.googleapis.com/v1/projects/{script_id}/deployments/{deployment_id}')


def create_temp_deployment(token, script_id, version, desc):
    out = api_json(token, f'https://script.googleapis.com/v1/projects/{script_id}/deployments', method='POST', body={
        'versionNumber': int(version), 'manifestFileName': 'appsscript', 'description': desc,
    })
    dep = str(out.get('deploymentId') or '')
    if not dep:
        fail('TEMP_DEPLOYMENT_ID_MISSING')
    print(f'::add-mask::{dep}')
    for _ in range(15):
        j = get_deployment(token, script_id, dep)
        web = [e.get('webApp', {}) for e in j.get('entryPoints', []) if e.get('entryPointType') == 'WEB_APP']
        if web and web[0].get('url'):
            return dep, web[0]['url']
        time.sleep(2)
    fail('TEMP_WEBAPP_URL_MISSING')


def delete_deployment(token, script_id, deployment_id):
    code, _ = request(
        f'https://script.googleapis.com/v1/projects/{script_id}/deployments/{deployment_id}',
        method='DELETE', headers={'Authorization': 'Bearer ' + token},
    )
    if code not in (200, 204, 404):
        fail(f'DELETE_DEPLOYMENT_HTTP_{code}')


def update_existing_deployment(token, script_id, deployment_id, version, desc):
    api_json(token, f'https://script.googleapis.com/v1/projects/{script_id}/deployments/{deployment_id}', method='PUT', body={
        'deploymentConfig': {
            'scriptId': script_id,
            'versionNumber': int(version),
            'manifestFileName': 'appsscript',
            'description': desc,
        }
    })


def web_post(url, body):
    code, raw = request(url, method='POST', headers={'Content-Type': 'text/plain;charset=UTF-8'}, data=json.dumps(body).encode())
    if code < 200 or code >= 300:
        return {'ok': False, '_http': code}
    try:
        return json.loads(raw or '{}')
    except Exception:
        return {'ok': False, '_json': False}


def poll_post(url, body, predicate, attempts=35):
    last = {}
    for _ in range(attempts):
        last = web_post(url, body)
        if predicate(last):
            return last
        time.sleep(2)
    return last


def server_sources(doc):
    return '\n'.join(f.get('source', '') for f in doc.get('files', []) if f.get('type') == 'SERVER_JS')


def find_main(doc, signature):
    rows = [f for f in doc.get('files', []) if f.get('type') == 'SERVER_JS' and signature in f.get('source', '') and 'function doPost(e)' in f.get('source', '')]
    if len(rows) != 1:
        fail('MAIN_SOURCE_COUNT_MISMATCH')
    return rows[0]


def replace_named_or_signature(doc, *, name, signature, source):
    out = []
    replaced = False
    for f in doc.get('files', []):
        if f.get('type') == 'SERVER_JS' and (f.get('name') == name or signature in f.get('source', '')):
            if not replaced:
                g = dict(f)
                g['name'] = name
                g['source'] = source
                out.append(g)
                replaced = True
            continue
        out.append(f)
    if not replaced:
        out.append({'name': name, 'type': 'SERVER_JS', 'source': source})
    return {'files': out}


def ensure_bh_route(doc):
    main = find_main(doc, "const BH_PROJECT = 'bao-hang-1291';")
    route = "if (action === 'staff-source-ping' || action === 'staff-source-structure-ping') return json_(staffSourceBridgeReceive_(body));"
    if route not in main.get('source', ''):
        anchor = "    const action = String(body.action || '').trim();\n"
        if anchor not in main['source']:
            fail('BH_ROUTE_ANCHOR_MISSING')
        main['source'] = main['source'].replace(anchor, anchor + '    ' + route + '\n', 1)
    return doc


def bootstrap_content(original, signature, json_fn, helper_name, bootstrap_token):
    doc = json.loads(json.dumps(original))
    main = find_main(doc, signature)
    anchor = "    const action = String(body.action || '').trim();\n"
    if anchor not in main['source']:
        fail('BOOTSTRAP_ROUTE_ANCHOR_MISSING')
    route = f"    if (action === '__staff_bridge_secret_bootstrap__') return {json_fn}({helper_name}(body));\n"
    main['source'] = main['source'].replace(anchor, anchor + route, 1)
    helper = f"""const __STAFF_BRIDGE_BOOTSTRAP_TOKEN = '{bootstrap_token}';
function {helper_name}(body) {{
  if (String(body && body.bootstrap_token || '') !== __STAFF_BRIDGE_BOOTSTRAP_TOKEN) throw new Error('BRIDGE_BOOTSTRAP_FORBIDDEN');
  const secret=String(body && body.bridge_secret || '');
  if (secret.length < 64) throw new Error('BRIDGE_SECRET_INVALID');
  const props=PropertiesService.getScriptProperties();
  props.setProperty('{PROP}',secret);
  props.deleteProperty('PP_BH_STAFF_PENDING_V1');
  if (typeof ScriptApp !== 'undefined') {{
    ScriptApp.getProjectTriggers().forEach(function(t) {{ if (t.getHandlerFunction() === 'ppBaoHangStaffBridgeRetry') ScriptApp.deleteTrigger(t); }});
  }}
  return {{ok:true,installed:true,length:secret.length}};
}}
"""
    doc['files'].append({'name': '__STAFF_BRIDGE_BOOTSTRAP', 'type': 'SERVER_JS', 'source': helper})
    return doc


def install_property(token, script_id, original, signature, json_fn, helper_name, secret, boot):
    temp_dep = ''
    try:
        put_content(token, script_id, bootstrap_content(original, signature, json_fn, helper_name, boot))
        v = create_version(token, script_id, 'TEMP staff bridge property bootstrap')
        temp_dep, url = create_temp_deployment(token, script_id, v, 'TEMP DELETE ME staff bridge property bootstrap')
        result = poll_post(url, {
            'action': '__staff_bridge_secret_bootstrap__',
            'bootstrap_token': boot,
            'bridge_secret': secret,
        }, lambda x: x.get('ok') is True and x.get('installed') is True and int(x.get('length') or 0) >= 64)
        if not (result.get('ok') is True and result.get('installed') is True):
            fail('SCRIPT_PROPERTY_BOOTSTRAP_FAILED')
    finally:
        if temp_dep:
            delete_deployment(token, script_id, temp_dep)
        put_content(token, script_id, original)


def production_web_url(token, script_id, deployment_id):
    j = get_deployment(token, script_id, deployment_id)
    web = [e.get('webApp', {}) for e in j.get('entryPoints', []) if e.get('entryPointType') == 'WEB_APP']
    if not web or not web[0].get('url'):
        fail('PRODUCTION_WEBAPP_URL_MISSING')
    return web[0]['url']


def make_probe_content(pp_content, probe_token):
    doc = json.loads(json.dumps(pp_content))
    main = find_main(doc, 'Pick Pack 1291 authoritative API')
    anchor = "    const action = String(body.action || '').trim();\n"
    if anchor not in main['source']:
        fail('PROBE_ROUTE_ANCHOR_MISSING')
    route = f'''    if (action === '__staff_bridge_hmac_probe__' && String(body.probe_token || '') === '{probe_token}') {{
      const sh=ppSheet_(PP.STAFF), vals=sh.getDataRange().getDisplayValues(); let row=0;
      for(let i=1;i<vals.length;i++) if(String(vals[i][0]||'').trim()==='{TEST_EMPLOYEE}') {{ row=i+1; break; }}
      if(!row) return ppJson_({{ok:false,error:'PROBE_EMPLOYEE_MISSING'}});
      const original=vals[row-1].slice(0,12), marker=String(original[1]||'')+' [HMAC-PROBE]';
      const auth={{role:'ADMIN',login_id:String(original[10]||'tamnv2')}};
      const base={{mnv:String(original[0]),phone:String(original[2]),main_position:String(original[3]),supplier:String(original[4]),department:String(original[5]),site:String(original[6]),warehouse:String(original[7]),start_date:String(original[8]),note:String(original[9])}};
      const a=ppStaffUpsert_(auth,Object.assign({{}},base,{{event_id:'hmac-probe-'+Utilities.getUuid(),full_name:marker}}));
      const b=ppStaffUpsert_(auth,Object.assign({{}},base,{{event_id:'hmac-restore-'+Utilities.getUuid(),full_name:String(original[1])}}));
      sh.getRange(row,11,1,2).setValues([[original[10],original[11]]]);
      const current=sh.getRange(row,1,1,12).getDisplayValues()[0];
      return ppJson_({{ok:true,marker_bridge:a&&a.result&&a.result.bao_hang_bridge,restore_bridge:b&&b.result&&b.result.bao_hang_bridge,source_restored:current.join('\\u001f')===original.join('\\u001f')}});
    }}
'''
    main['source'] = main['source'].replace(anchor, anchor + route, 1)
    for f in doc.get('files', []):
        if f.get('type') == 'SERVER_JS' and 'function ppBaoHangBridgeNotifyServiceStaffMutation_' in f.get('source', ''):
            f['source'] = f['source'].replace(
                "return result && result.ok ? 'SENT' : (result && result.queued ? 'QUEUED' : 'FAILED');",
                "return result && result.ok ? result : (result && result.queued ? 'QUEUED' : 'FAILED');", 1)
    return doc


def main():
    root = pathlib.Path.cwd()
    bh_root = pathlib.Path('/tmp/bao-hang')
    if not bh_root.exists():
        fail('BAO_HANG_CHECKOUT_MISSING')

    pp_script = ''.join(os.environ['GAS_SCRIPT_ID'].split())
    pp_deploy = norm_deployment(os.environ['GAS_DEPLOYMENT_ID'])
    if not pp_script or not pp_deploy:
        fail('PICK_PACK_SCOPE_MISSING')
    print(f'::add-mask::{pp_script}')
    print(f'::add-mask::{pp_deploy}')

    token = oauth_token()
    pp_before = project_content(token, pp_script)
    bh_before = project_content(token, BH_SCRIPT_ID)
    pp_live_src = server_sources(pp_before)
    bh_live_src = server_sources(bh_before)
    if 'Pick Pack 1291 authoritative API' not in pp_live_src or STAFF_SHEET_ID not in pp_live_src:
        fail('PICK_PACK_LIVE_SCOPE_MISMATCH')
    if "const BH_PROJECT = 'bao-hang-1291';" not in bh_live_src or 'tiny-boat-19315489' not in bh_live_src:
        fail('BAO_HANG_LIVE_SCOPE_MISMATCH')

    pp_bridge = (root / 'google-apps-script/BAO_HANG_STAFF_BRIDGE.gs').read_text()
    bh_receiver = (bh_root / 'google-apps-script/STAFF_SOURCE_BRIDGE_RECEIVER.gs').read_text()
    if f"HMAC_PROP: '{PROP}'" not in pp_bridge or 'function ppBaoHangBridgeHmacHex_' not in pp_bridge or 'ScriptApp.getOAuthToken()' in pp_bridge:
        fail('PICK_PACK_CANONICAL_HMAC_GATE_FAILED')
    if f"HMAC_PROP: '{PROP}'" not in bh_receiver or 'staffSourceBridgeVerifySender_(body)' not in bh_receiver or 'function staffSourceBridgeHmacHex_' not in bh_receiver:
        fail('BAO_HANG_CANONICAL_HMAC_GATE_FAILED')
    if 'bao_hang_bridge:bridge' not in pp_live_src:
        fail('PICK_PACK_LIVE_SERVICE_BRIDGE_MISSING')

    # Generate once; never persist outside Script Properties or this ephemeral runner.
    bridge_secret = secrets.token_hex(48)
    boot = secrets.token_hex(24)
    print(f'::add-mask::{bridge_secret}')
    print(f'::add-mask::{boot}')

    install_property(token, pp_script, pp_before, 'Pick Pack 1291 authoritative API', 'ppJson_', 'ppBridgeSecretBootstrap_', bridge_secret, boot)
    install_property(token, BH_SCRIPT_ID, bh_before, "const BH_PROJECT = 'bao-hang-1291';", 'json_', 'bhBridgeSecretBootstrap_', bridge_secret, boot)
    print('SCRIPT_PROPERTIES_BOOTSTRAP=PASS')

    # Preserve current live projects; replace only the permanent bridge modules.
    pp_prod = replace_named_or_signature(pp_before, name='BAO_HANG_STAFF_BRIDGE', signature='function ppBaoHangBridgePost_', source=pp_bridge)
    bh_prod = replace_named_or_signature(bh_before, name='STAFF_SOURCE_BRIDGE_RECEIVER', signature='function staffSourceBridgeReceive_', source=bh_receiver)
    bh_prod = ensure_bh_route(bh_prod)

    put_content(token, pp_script, pp_prod)
    pp_ver = create_version(token, pp_script, 'Pick Pack 1291 signed staff bridge')
    update_existing_deployment(token, pp_script, pp_deploy, pp_ver, 'Pick Pack 1291 live API')
    put_content(token, BH_SCRIPT_ID, bh_prod)
    bh_ver = create_version(token, BH_SCRIPT_ID, 'Bao Hang 1291 signed staff receiver')
    update_existing_deployment(token, BH_SCRIPT_ID, BH_DEPLOYMENT_ID, bh_ver, 'Bao Hang 1291 live worker')

    pp_url = production_web_url(token, pp_script, pp_deploy)
    bh_url = production_web_url(token, BH_SCRIPT_ID, BH_DEPLOYMENT_ID)
    pp_health = poll_post(pp_url, {'action': 'health'}, lambda x: x.get('ok') is True and x.get('sheet_read') is True, 25)
    bh_health = poll_post(bh_url, {'action': 'ping'}, lambda x: x.get('ok') is True and x.get('project') == 'bao-hang-1291', 25)
    if not (pp_health.get('ok') is True and pp_health.get('sheet_read') is True):
        fail('PICK_PACK_LIVE_HEALTH_FAILED')
    if not (bh_health.get('ok') is True and bh_health.get('project') == 'bao-hang-1291'):
        fail('BAO_HANG_LIVE_HEALTH_FAILED')
    print('PRODUCTION_DEPLOY_HEALTH=PASS')

    # Isolated runtime probe: exercise exact ppStaffUpsert_ web-app context, then restore source row exactly.
    pp_after = project_content(token, pp_script)
    probe_token = secrets.token_hex(24)
    print(f'::add-mask::{probe_token}')
    temp_dep = ''
    probe_result = {}
    try:
        put_content(token, pp_script, make_probe_content(pp_after, probe_token))
        pv = create_version(token, pp_script, 'TEMP isolated signed staff bridge probe')
        temp_dep, probe_url = create_temp_deployment(token, pp_script, pv, 'TEMP DELETE ME signed staff bridge probe')
        probe_result = poll_post(
            probe_url,
            {'action': '__staff_bridge_hmac_probe__', 'probe_token': probe_token},
            lambda x: x.get('ok') is True,
            35,
        )
    finally:
        if temp_dep:
            delete_deployment(token, pp_script, temp_dep)
        put_content(token, pp_script, pp_after)

    marker = probe_result.get('marker_bridge') if isinstance(probe_result.get('marker_bridge'), dict) else {}
    restore = probe_result.get('restore_bridge') if isinstance(probe_result.get('restore_bridge'), dict) else {}
    if not (probe_result.get('ok') is True and probe_result.get('source_restored') is True):
        fail('SERVICE_PROBE_SOURCE_RESTORE_FAILED')
    if not (marker.get('ok') is True and int(marker.get('changed') or 0) >= 1):
        fail('SERVICE_PROBE_MARKER_BRIDGE_FAILED')
    if not (restore.get('ok') is True and int(restore.get('changed') or 0) >= 1):
        fail('SERVICE_PROBE_RESTORE_BRIDGE_FAILED')
    print('SERVICE_UPSERT_SIGNED_BRIDGE_RUNTIME=PASS')

    proof = {
        'status': 'PASS',
        'mode': 'SIGNED_SOURCE_DRIVEN_STAFF_BRIDGE_V2',
        'secret_location': 'APPS_SCRIPT_PROPERTIES_ONLY',
        'pick_pack_gas_version': pp_ver,
        'bao_hang_gas_version': bh_ver,
        'pick_pack_source_hmac': 'PASS',
        'bao_hang_receiver_hmac': 'PASS',
        'pick_pack_live_health': 'PASS',
        'bao_hang_live_health': 'PASS',
        'service_upsert_runtime': 'PASS',
        'marker_changed': int(marker.get('changed') or 0),
        'restore_changed': int(restore.get('changed') or 0),
        'source_restored': True,
        'temporary_deployments_cleanup': 'PASS',
        'verified_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (root / 'ops/staff-bridge-hmac-live-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, separators=(',', ':')))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Sanitized failure only. Never print provider response bodies or generated secrets.
        print('STAFF_BRIDGE_INSTALL=FAIL stage=' + str(exc)[:180], file=sys.stderr)
        sys.exit(1)
