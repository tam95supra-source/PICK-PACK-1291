#!/usr/bin/env python3
import json, os, subprocess, sys

ACCOUNT=os.environ['CLOUDFLARE_ACCOUNT_ID']
TOKEN=os.environ['CLOUDFLARE_API_TOKEN']
NAME='pick-pack-1291-service-prod'
BASE=f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}'
H=['-H',f'Authorization: Bearer {TOKEN}','-H','Content-Type: application/json']

def curl(args):
    p=subprocess.run(['curl','-fsS',*args],text=True,capture_output=True)
    if p.returncode:
        print(p.stderr,file=sys.stderr);raise SystemExit(p.returncode)
    return json.loads(p.stdout)

dbs=curl([*H,f'{BASE}/d1/database'])
items=dbs.get('result',[])
db=next((x for x in items if x.get('name')==NAME),None)
if not db: raise SystemExit('PROD_D1_NOT_FOUND')
id=db.get('uuid') or db.get('id')
print('D1_ID_RESOLVED=true')

def query(sql):
    body=json.dumps({'sql':sql,'params':[]})
    out=curl(['-X','POST',*H,'--data-binary',body,f'{BASE}/d1/database/{id}/query'])
    if not out.get('success'): raise RuntimeError(out)
    rs=out.get('result') or []
    return (rs[0].get('results') if rs else []) or []

checks={
 'AUTHORITY':"SELECT authority_epoch,authority_seq,mode,service_generation,updated_at FROM authority_state WHERE singleton_id=1",
 'LOCK':"SELECT key,value,updated_at FROM system_meta WHERE key='m2_reconciling'",
 'BUSINESS_DATES':"SELECT business_date,sequence_no,source FROM business_dates ORDER BY sequence_no DESC LIMIT 5",
 'RECOVERY':"SELECT recovery_id,status,error,source_authority_epoch,source_authority_seq,target_authority_epoch,validation_json,started_at,completed_at FROM recovery_runs WHERE recovery_type='FAILBACK' ORDER BY started_at DESC LIMIT 5",
 'INBOX':"SELECT event_id,authority_epoch,authority_seq,ingest_status,last_error FROM fallback_event_inbox WHERE authority_epoch=3 ORDER BY authority_seq",
 'EVENTS':"SELECT event_id,event_type,authority_epoch,authority_seq,business_date FROM events WHERE authority_epoch=3 ORDER BY authority_seq",
 'INBOX_ACTIONS':"SELECT event_id,authority_seq,json_extract(event_json,'$.action') AS action,json_extract(event_json,'$.role') AS role,json_extract(event_json,'$.business_date') AS business_date FROM fallback_event_inbox WHERE authority_epoch=3 ORDER BY authority_seq"
}
for label,sql in checks.items():
    rows=query(sql)
    print(label+'='+json.dumps(rows,ensure_ascii=False,separators=(',',':')))
