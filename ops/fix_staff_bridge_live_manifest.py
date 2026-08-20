#!/usr/bin/env python3
import datetime as dt
import json
import os
import pathlib
import sys

import install_staff_bridge_hmac as base

PROOF=pathlib.Path('ops/staff-bridge-manifest-proof.json')
REQUIRED='https://www.googleapis.com/auth/script.external_request'


def run():
    token=base.oauth_token()
    script=''.join(os.environ['GAS_SCRIPT_ID'].split())
    dep=base.norm_deployment(os.environ['GAS_DEPLOYMENT_ID'])
    print(f'::add-mask::{script}'); print(f'::add-mask::{dep}')
    doc=base.project_content(token,script)
    manifests=[f for f in doc.get('files',[]) if f.get('type')=='JSON' and f.get('name')=='appsscript']
    if len(manifests)!=1: base.fail('LIVE_MANIFEST_COUNT_MISMATCH')
    manifest=json.loads(manifests[0].get('source') or '{}')
    scopes=list(manifest.get('oauthScopes') or [])
    before=REQUIRED in scopes
    if not before:
        scopes.append(REQUIRED)
        manifest['oauthScopes']=scopes
        manifests[0]['source']=json.dumps(manifest,ensure_ascii=False,indent=2)
        base.put_content(token,script,doc)
        v=base.create_version(token,script,'Pick Pack 1291 external request scope for Bao Hang staff bridge')
        base.update_existing_deployment(token,script,dep,v,'Pick Pack 1291 live API')
    else:
        v=0
    after_doc=base.project_content(token,script)
    after_manifest=[f for f in after_doc.get('files',[]) if f.get('type')=='JSON' and f.get('name')=='appsscript'][0]
    after=REQUIRED in (json.loads(after_manifest.get('source') or '{}').get('oauthScopes') or [])
    if not after: base.fail('LIVE_EXTERNAL_REQUEST_SCOPE_MISSING')
    PROOF.write_text(json.dumps({'status':'PASS','scope': 'script.external_request','present_before':before,'present_after':after,'deployment_version_created':v,'verified_at':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')

if __name__=='__main__':
    try: run()
    except Exception as exc:
        PROOF.write_text(json.dumps({'status':'FAIL','stage':str(exc)[:160],'verified_at':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')
        raise
