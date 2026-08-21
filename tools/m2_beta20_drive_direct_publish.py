#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

SERVICE_URL=os.environ['SERVICE_URL'].rstrip('/')
GAS_URL=os.environ['GSHEET_API_URL']
FOLDER_ID=os.environ['BETA_FOLDER_ID']
VERSION=os.environ['BETA_VERSION']
VERSION_CODE=os.environ['BETA_VERSION_CODE']
PACKAGE=os.environ['BETA_PACKAGE']
EXPECTED_SHA=os.environ['EXPECTED_BETA_SHA256'].lower()
EXPECTED_SIGNER=os.environ['EXPECTED_SIGNER_SHA256'].lower()
ARTIFACT_RUN=os.environ['CANDIDATE_RUN_ID']
ARTIFACT_NAME=os.environ['CANDIDATE_ARTIFACT_NAME']
FILE_NAME=f'pick-pack-1291-public-beta-v{VERSION}.apk'
SUMS_NAME=f'SHA256SUMS-v{VERSION}-publicbeta.txt'
EVIDENCE=Path('m2-beta20-drive-direct-evidence'); EVIDENCE.mkdir(exist_ok=True)

for k in ['GH_TOKEN','GOOGLE_OAUTH_CLIENT_ID','GOOGLE_OAUTH_CLIENT_SECRET','GOOGLE_OAUTH_REFRESH_TOKEN']:
    if not os.environ.get(k): raise SystemExit('MISSING:'+k)

def write(name,obj):
    p=EVIDENCE/name
    if isinstance(obj,(dict,list)): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2))
    else: p.write_text(str(obj))

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def sh(args):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if p.returncode:
        sys.stderr.write(p.stderr.decode('utf-8','replace'))
        raise RuntimeError('COMMAND_FAILED:'+args[0])
    return p.stdout.decode('utf-8','replace')

def json_req(url,method='GET',headers=None,payload=None,timeout=60):
    data=None; h=dict(headers or {})
    if payload is not None:
        data=json.dumps(payload,separators=(',',':')).encode(); h.setdefault('Content-Type','application/json')
    req=urllib.request.Request(url,data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read(); return json.loads(raw.decode()) if raw else {}, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        raise RuntimeError(f'HTTP_{e.code}:{raw[:500]}')

def gas(payload):
    with tempfile.NamedTemporaryFile('w',delete=False) as f:
        json.dump(payload,f,separators=(',',':')); n=f.name
    try:
        out=sh(['curl','-fsSL','--retry','4','--retry-delay','2','-H','content-type: application/json',GAS_URL,'--data-binary','@'+n])
        return json.loads(out)
    finally: Path(n).unlink(missing_ok=True)

def service_health():
    out=sh(['curl','-fsS','--retry','4','--retry-delay','2',SERVICE_URL+'/health'])
    return json.loads(out)

def assert_health(h):
    a=h.get('authority') or {}; r=h.get('replication') or {}
    if not (h.get('ok') and h.get('environment')=='production' and a.get('mode')=='SERVICE_PRIMARY' and a.get('scope')=='PRODUCTION' and int(a.get('authority_epoch') or 0)==4 and h.get('generation')==os.environ['SERVICE_GENERATION'] and r.get('state')=='HEALTHY' and int(r.get('pending_count') or 0)==0):
        raise RuntimeError('SERVICE_HEALTH_INVALID:'+json.dumps(h))

def token():
    form=urllib.parse.urlencode({'client_id':os.environ['GOOGLE_OAUTH_CLIENT_ID'],'client_secret':os.environ['GOOGLE_OAUTH_CLIENT_SECRET'],'refresh_token':os.environ['GOOGLE_OAUTH_REFRESH_TOKEN'],'grant_type':'refresh_token'}).encode()
    req=urllib.request.Request('https://oauth2.googleapis.com/token',data=form,method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req,timeout=30) as r: j=json.loads(r.read().decode())
    if not j.get('access_token'): raise RuntimeError('GOOGLE_ACCESS_TOKEN_MISSING')
    return j['access_token']

def drive_list(tok,name=None):
    q=[f"'{FOLDER_ID}' in parents","trashed = false"]
    if name is not None: q.append("name = '"+name.replace("'","\\'")+"'")
    params=urllib.parse.urlencode({'q':' and '.join(q),'fields':'files(id,name,size,mimeType,modifiedTime)','pageSize':'1000','supportsAllDrives':'true','includeItemsFromAllDrives':'true'})
    j,_=json_req('https://www.googleapis.com/drive/v3/files?'+params,headers={'Authorization':'Bearer '+tok})
    return j.get('files') or []

def drive_download(tok,file_id,out):
    req=urllib.request.Request(f'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true',headers={'Authorization':'Bearer '+tok})
    with urllib.request.urlopen(req,timeout=180) as r, open(out,'wb') as f: shutil.copyfileobj(r,f)

def drive_upload_resumable(tok,path,name,mime,description):
    meta={'name':name,'parents':[FOLDER_ID],'description':description}
    body=json.dumps(meta,separators=(',',':')).encode()
    url='https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true&fields=id,name,size,mimeType,modifiedTime'
    req=urllib.request.Request(url,data=body,method='POST',headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json; charset=UTF-8','X-Upload-Content-Type':mime,'X-Upload-Content-Length':str(path.stat().st_size)})
    try:
        with urllib.request.urlopen(req,timeout=60) as r: location=r.headers.get('Location')
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'DRIVE_RESUMABLE_INIT_{e.code}:'+e.read().decode('utf-8','replace')[:500])
    if not location: raise RuntimeError('DRIVE_RESUMABLE_LOCATION_MISSING')
    data=path.read_bytes()
    req2=urllib.request.Request(location,data=data,method='PUT',headers={'Content-Type':mime,'Content-Length':str(len(data))})
    try:
        with urllib.request.urlopen(req2,timeout=300) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'DRIVE_UPLOAD_{e.code}:'+e.read().decode('utf-8','replace')[:500])

def make_public(tok,file_id):
    payload={'type':'anyone','role':'reader'}
    try:
        j,_=json_req(f'https://www.googleapis.com/drive/v3/files/{file_id}/permissions?supportsAllDrives=true',method='POST',headers={'Authorization':'Bearer '+tok},payload=payload)
        return j
    except RuntimeError as e:
        if 'already' in str(e).lower(): return {'already_public':True}
        raise

def download_candidate():
    dest=Path('/tmp/beta20-direct'); shutil.rmtree(dest,ignore_errors=True); dest.mkdir()
    p=subprocess.run(['gh','run','download',ARTIFACT_RUN,'--repo',os.environ['GITHUB_REPOSITORY'],'--name',ARTIFACT_NAME,'--dir',str(dest)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if p.returncode: raise RuntimeError('GH_DOWNLOAD:'+p.stderr.decode('utf-8','replace'))
    apks=list(dest.rglob('*.apk'))
    if len(apks)!=1: raise RuntimeError('APK_COUNT:'+str(len(apks)))
    apk=apks[0]
    if sha256(apk)!=EXPECTED_SHA: raise RuntimeError('APK_SHA_MISMATCH:'+sha256(apk))
    bt=Path(os.environ['ANDROID_HOME'])/'build-tools'/'36.0.0'
    badge=sh([str(bt/'aapt'),'dump','badging',str(apk)]); write('package-badging.txt',badge)
    if f"package: name='{PACKAGE}'" not in badge or f"versionCode='{VERSION_CODE}'" not in badge or f"versionName='{VERSION}'" not in badge: raise RuntimeError('APK_METADATA_INVALID')
    cert=sh([str(bt/'apksigner'),'verify','--verbose','--print-certs',str(apk)]); write('signer.txt',cert)
    m=re.search(r'Signer #1 certificate SHA-256 digest:\s*([0-9A-Fa-f:]+)',cert); got=(m.group(1).replace(':','').lower() if m else '')
    if got!=EXPECTED_SIGNER: raise RuntimeError('SIGNER_MISMATCH:'+got)
    return apk

def ensure_file(tok,path,name,mime,description,expected_sha=None,expected_text=None):
    found=drive_list(tok,name)
    if len(found)>1: raise RuntimeError('DUPLICATE_TARGET_BEFORE:'+name)
    if found:
        f=found[0]; tmp=Path('/tmp/existing-'+re.sub(r'[^A-Za-z0-9_.-]','_',name)); drive_download(tok,f['id'],tmp)
        if expected_sha and sha256(tmp)!=expected_sha: raise RuntimeError('EXISTING_TARGET_SHA_MISMATCH:'+name)
        if expected_text is not None and tmp.read_text()!=expected_text: raise RuntimeError('EXISTING_TARGET_TEXT_MISMATCH:'+name)
        return f,False
    f=drive_upload_resumable(tok,path,name,mime,description)
    make_public(tok,f['id'])
    return f,True

def main():
    before=service_health(); assert_health(before); write('service-before.json',before)
    discovery=gas({'action':'service_discovery','_app_channel':'BETA','_app_version':'0.4.2-beta.19'}); write('discovery-before.json',discovery)
    if not (discovery.get('ok') and discovery.get('authority_mode')=='SERVICE_PRIMARY' and discovery.get('service_url')==SERVICE_URL and int((discovery.get('authority') or {}).get('authority_epoch') or 0)==4): raise RuntimeError('DISCOVERY_INVALID')
    stable_before=gas({'action':'update_check','channel':'STABLE','current_version':os.environ['STABLE_VERSION']}); write('stable-before.json',stable_before)
    beta_before=gas({'action':'update_check','channel':'BETA','current_version':'0.4.2-beta.19'}); write('beta-before.json',beta_before)

    apk=download_candidate(); tok=token()
    # Read-only Drive scope fence before any upload.
    listing=drive_list(tok); write('drive-folder-before.json',listing)

    apk_file,created=ensure_file(tok,apk,FILE_NAME,'application/vnd.android.package-archive',f'Pick Pack 1291 Beta {VERSION} | Service-first M2',expected_sha=EXPECTED_SHA)
    make_public(tok,apk_file['id'])
    sums_text=f'{EXPECTED_SHA}  {FILE_NAME}\n'; sums_path=Path('/tmp/'+SUMS_NAME); sums_path.write_text(sums_text)
    sums_file,sums_created=ensure_file(tok,sums_path,SUMS_NAME,'text/plain',f'SHA256 for {FILE_NAME}',expected_text=sums_text)
    make_public(tok,sums_file['id'])
    write('drive-publish.json',{'apk':apk_file,'apk_created':created,'sums':sums_file,'sums_created':sums_created})

    # Authenticated round-trip byte verification.
    dl=Path('/tmp/beta20-drive-roundtrip.apk'); drive_download(tok,apk_file['id'],dl)
    if sha256(dl)!=EXPECTED_SHA: raise RuntimeError('DRIVE_ROUNDTRIP_SHA_MISMATCH')

    beta=None
    for _ in range(30):
        beta=gas({'action':'update_check','channel':'BETA','current_version':'0.4.2-beta.19'})
        if beta.get('ok') and beta.get('available') and beta.get('version_name')==VERSION and str(beta.get('sha256','')).lower()==EXPECTED_SHA: break
        time.sleep(2)
    write('beta-after.json',beta)
    if not (beta and beta.get('ok') and beta.get('available') and beta.get('version_name')==VERSION and str(beta.get('sha256','')).lower()==EXPECTED_SHA and beta.get('apk_url')): raise RuntimeError('BETA_UPDATE_CHECK_INVALID:'+json.dumps(beta))
    selfcheck=gas({'action':'update_check','channel':'BETA','current_version':VERSION}); write('beta-self.json',selfcheck)
    if not (selfcheck.get('ok') and selfcheck.get('available') is False and selfcheck.get('version_name')==VERSION): raise RuntimeError('BETA_SELF_CHECK_INVALID')
    stable_after=gas({'action':'update_check','channel':'STABLE','current_version':os.environ['STABLE_VERSION']}); write('stable-after.json',stable_after)
    if stable_after.get('version_name')!=stable_before.get('version_name') or stable_after.get('available')!=stable_before.get('available'): raise RuntimeError('STABLE_CHANNEL_CHANGED')
    after=service_health(); assert_health(after); write('service-after.json',after)
    if int((after.get('authority') or {}).get('authority_epoch') or 0)!=int((before.get('authority') or {}).get('authority_epoch') or 0): raise RuntimeError('AUTHORITY_EPOCH_CHANGED')
    print(json.dumps({'ok':True,'published_version':VERSION,'sha256':EXPECTED_SHA,'apk_file_id':apk_file['id'],'sums_file_id':sums_file['id'],'stable_unchanged':True,'authority_epoch':4},separators=(',',':')))

if __name__=='__main__': main()
