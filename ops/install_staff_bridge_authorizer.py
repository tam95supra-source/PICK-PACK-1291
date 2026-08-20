#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import sys

import install_staff_bridge_hmac as base

PROOF=pathlib.Path('ops/staff-bridge-authorizer-proof.json')


def run():
    token=base.oauth_token()
    script=''.join(os.environ['GAS_SCRIPT_ID'].split())
    print(f'::add-mask::{script}')
    live=base.project_content(token,script)
    helper=pathlib.Path('google-apps-script/BAO_HANG_STAFF_BRIDGE_AUTHORIZE.gs').read_text()
    out=[]; replaced=False
    for f in live.get('files',[]):
        if f.get('type')=='SERVER_JS' and (f.get('name')=='BAO_HANG_STAFF_BRIDGE_AUTHORIZE' or 'function authorizeBaoHangStaffBridgeTransport()' in f.get('source','')):
            if not replaced:
                g=dict(f); g['name']='BAO_HANG_STAFF_BRIDGE_AUTHORIZE'; g['source']=helper; out.append(g); replaced=True
            continue
        out.append(f)
    if not replaced:
        out.append({'name':'BAO_HANG_STAFF_BRIDGE_AUTHORIZE','type':'SERVER_JS','source':helper})
    base.put_content(token,script,{'files':out})
    after=base.project_content(token,script)
    src=base.server_sources(after)
    if 'function authorizeBaoHangStaffBridgeTransport()' not in src:
        base.fail('AUTHORIZER_NOT_LIVE')
    PROOF.write_text(json.dumps({'status':'PASS','function':'authorizeBaoHangStaffBridgeTransport','data_mutation':False,'verified_at':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')

if __name__=='__main__':
    try: run()
    except Exception as exc:
        PROOF.write_text(json.dumps({'status':'FAIL','stage':str(exc)[:160],'verified_at':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')
        raise
