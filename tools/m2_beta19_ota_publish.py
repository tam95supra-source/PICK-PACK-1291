#!/usr/bin/env python3
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile

SERVICE_URL = os.environ["SERVICE_URL"].rstrip("/")
GAS_URL = os.environ["GSHEET_API_URL"]
BETA_FOLDER_ID = os.environ["BETA_FOLDER_ID"]
BETA_VERSION = os.environ["BETA_VERSION"]
BETA_VERSION_CODE = os.environ["BETA_VERSION_CODE"]
BETA_PACKAGE = os.environ["BETA_PACKAGE"]
PREVIOUS_BETA_VERSION = os.environ["PREVIOUS_BETA_VERSION"]
STABLE_VERSION = os.environ["STABLE_VERSION"]
EXPECTED_SHA = os.environ["EXPECTED_BETA_SHA256"].lower()
EXPECTED_SIGNER = os.environ["EXPECTED_SIGNER_SHA256"].lower()
ARTIFACT_ID = os.environ["CANDIDATE_ARTIFACT_ID"]
EVIDENCE = Path("m2-beta19-ota-publish-evidence")
EVIDENCE.mkdir(exist_ok=True)

REQUIRED = [
    "GH_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN",
    "GAS_SCRIPT_ID", "GAS_DEPLOYMENT_ID", "SIGNING_STORE_PASSWORD",
]
for key in REQUIRED:
    if not os.environ.get(key):
        raise SystemExit(f"MISSING_REQUIRED_SECRET:{key}")


def sh(args, *, input_bytes=None, check=True, text=True):
    p = subprocess.run(args, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check and p.returncode != 0:
        sys.stderr.write(p.stderr.decode("utf-8", "replace"))
        raise RuntimeError(f"COMMAND_FAILED:{args[0]}:{p.returncode}")
    if text:
        return p.stdout.decode("utf-8", "replace")
    return p.stdout


def http_json(url, *, method="GET", headers=None, payload=None, timeout=60):
    hdr = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode()
        hdr.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def gas_post(payload, timeout=120):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        json.dump(payload, f, separators=(",", ":"))
        name = f.name
    try:
        out = sh([
            "curl", "-fsSL", "--connect-timeout", "5", "--max-time", str(timeout),
            "--retry", "3", "--retry-delay", "2", "--retry-all-errors",
            "-H", "content-type: application/json", GAS_URL, "--data-binary", f"@{name}"
        ])
        return json.loads(out)
    finally:
        Path(name).unlink(missing_ok=True)


def write_json(name, obj):
    (EVIDENCE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def service_health():
    return http_json(SERVICE_URL + "/health", timeout=30)


def assert_production_health(h):
    a = h.get("authority") or {}
    r = h.get("replication") or {}
    if not (h.get("ok") and h.get("environment") == "production" and a.get("scope") == "PRODUCTION" and a.get("mode") == "SERVICE_PRIMARY" and h.get("generation") == os.environ["SERVICE_GENERATION"] and r.get("state") == "HEALTHY" and int(r.get("pending_count") or 0) == 0):
        raise RuntimeError("PRODUCTION_HEALTH_INVALID:" + json.dumps(h))


def assert_discovery(h, g):
    epoch = int((h.get("authority") or {}).get("authority_epoch") or 0)
    ga = g.get("authority") or {}
    if not (g.get("ok") and g.get("authority_mode") == "SERVICE_PRIMARY" and g.get("service_url") == SERVICE_URL and g.get("cutover_configured") is True and int(ga.get("authority_epoch") or 0) == epoch):
        raise RuntimeError("GAS_DISCOVERY_INVALID:" + json.dumps(g))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_candidate():
    url = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts/{ARTIFACT_ID}/zip"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json", "User-Agent": "pick-pack-1291-m2"})
    zpath = Path("/tmp/m2-beta19-candidate.zip")
    with urllib.request.urlopen(req, timeout=120) as r:
        zpath.write_bytes(r.read())
    dest = Path("/tmp/m2-beta19-candidate")
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir()
    with zipfile.ZipFile(zpath) as z:
        z.extractall(dest)
    apks = list(dest.rglob("*.apk"))
    if len(apks) != 1:
        raise RuntimeError(f"CANDIDATE_APK_COUNT:{len(apks)}")
    apk = apks[0]
    got = sha256_file(apk)
    if got != EXPECTED_SHA:
        raise RuntimeError(f"CANDIDATE_SHA_MISMATCH:{got}")
    bt = Path(os.environ["ANDROID_HOME"]) / "build-tools" / "36.0.0"
    aapt = str(bt / "aapt")
    apksigner = str(bt / "apksigner")
    badge = sh([aapt, "dump", "badging", str(apk)])
    (EVIDENCE / "package-badging.txt").write_text(badge)
    if f"package: name='{BETA_PACKAGE}'" not in badge or f"versionCode='{BETA_VERSION_CODE}'" not in badge or f"versionName='{BETA_VERSION}'" not in badge:
        raise RuntimeError("CANDIDATE_PACKAGE_METADATA_INVALID")
    cert = sh([apksigner, "verify", "--verbose", "--print-certs", str(apk)])
    (EVIDENCE / "signer.txt").write_text(cert)
    m = re.search(r"Signer #1 certificate SHA-256 digest:\s*([0-9A-Fa-f:]+)", cert)
    signer = (m.group(1).replace(":", "").lower() if m else "")
    if signer != EXPECTED_SIGNER:
        raise RuntimeError(f"CANDIDATE_SIGNER_MISMATCH:{signer}")
    out = Path("/tmp/beta19.apk")
    shutil.copy2(apk, out)
    return out


def google_token():
    form = urllib.parse.urlencode({
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=form, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read().decode())
    token = j.get("access_token")
    if not token:
        raise RuntimeError("GOOGLE_ACCESS_TOKEN_MISSING")
    return token


def gapi(token, path, *, method="GET", payload=None):
    return http_json("https://script.googleapis.com/v1/" + path.lstrip("/"), method=method, headers={"Authorization": f"Bearer {token}"}, payload=payload, timeout=60)


def deployment_id():
    raw = os.environ["GAS_DEPLOYMENT_ID"].strip()
    m = re.search(r"/s/([^/]+)", raw)
    return m.group(1) if m else raw


def publisher_source(token_hash):
    file_name = f"pick-pack-1291-public-beta-v{BETA_VERSION}.apk"
    sums_name = f"SHA256SUMS-v{BETA_VERSION}-publicbeta.txt"
    cfg = json.dumps({"TOKEN_SHA256": token_hash, "BETA_FOLDER_ID": BETA_FOLDER_ID, "VERSION": BETA_VERSION, "SHA256": EXPECTED_SHA, "FILE_NAME": file_name, "SUMS_NAME": sums_name}, separators=(",", ":"))
    return f'''const PP_M2_OTA_PUBLISH = Object.freeze({cfg});
function ppM2OtaHex_(bytes) {{ return bytes.map(function(b) {{ return ('0'+((b+256)%256).toString(16)).slice(-2); }}).join(''); }}
function ppM2OtaTokenHash_(v) {{ return ppM2OtaHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,String(v||''),Utilities.Charset.UTF_8)); }}
function ppM2OtaAuthorized_(body) {{ return !!body && ppM2OtaTokenHash_(body.publish_token) === PP_M2_OTA_PUBLISH.TOKEN_SHA256; }}
function ppM2OtaUploadId_(body) {{ const id=String(body.upload_id||''); if(!/^[A-Za-z0-9_-]{{8,80}}$/.test(id)) throw new Error('OTA_UPLOAD_ID_INVALID'); return id; }}
function ppM2OtaPartName_(id,i) {{ return '.__m2_beta19_'+id+'_'+('000'+i).slice(-3)+'.part'; }}
function ppM2OtaDeleteNamed_(folder,name) {{ const it=folder.getFilesByName(name); while(it.hasNext()) it.next().setTrashed(true); }}
function ppM2OtaPublishChunk_(body) {{
  if(!ppM2OtaAuthorized_(body)) return {{ok:false,error:'OTA_PUBLISH_UNAUTHORIZED'}};
  if(String(body.version||'')!==PP_M2_OTA_PUBLISH.VERSION) return {{ok:false,error:'OTA_VERSION_LOCK'}};
  const id=ppM2OtaUploadId_(body),idx=Number(body.chunk_index),total=Number(body.total_chunks);
  if(!Number.isInteger(idx)||!Number.isInteger(total)||idx<0||idx>=total||total<1||total>64) return {{ok:false,error:'OTA_CHUNK_RANGE'}};
  const b64=String(body.data_b64||''); if(!b64||b64.length>1000000) return {{ok:false,error:'OTA_CHUNK_SIZE'}};
  const bytes=Utilities.base64Decode(b64),folder=DriveApp.getFolderById(PP_M2_OTA_PUBLISH.BETA_FOLDER_ID),n=ppM2OtaPartName_(id,idx);
  ppM2OtaDeleteNamed_(folder,n); const f=folder.createFile(Utilities.newBlob(bytes,'application/octet-stream',n));
  f.setDescription(JSON.stringify({{upload_id:id,index:idx,total:total,version:PP_M2_OTA_PUBLISH.VERSION}}));
  return {{ok:true,upload_id:id,chunk_index:idx,total_chunks:total,size:bytes.length}};
}}
function ppM2OtaPublishAbort_(body) {{
  if(!ppM2OtaAuthorized_(body)) return {{ok:false,error:'OTA_PUBLISH_UNAUTHORIZED'}};
  const id=ppM2OtaUploadId_(body),folder=DriveApp.getFolderById(PP_M2_OTA_PUBLISH.BETA_FOLDER_ID),files=folder.getFiles(); let n=0;
  while(files.hasNext()) {{ const f=files.next(); if(f.getName().indexOf('.__m2_beta19_'+id+'_')===0) {{ f.setTrashed(true); n++; }} }}
  return {{ok:true,aborted:true,deleted_parts:n}};
}}
function ppM2OtaPublishFinalize_(body) {{
  if(!ppM2OtaAuthorized_(body)) return {{ok:false,error:'OTA_PUBLISH_UNAUTHORIZED'}};
  if(String(body.version||'')!==PP_M2_OTA_PUBLISH.VERSION) return {{ok:false,error:'OTA_VERSION_LOCK'}};
  const id=ppM2OtaUploadId_(body),total=Number(body.total_chunks); if(!Number.isInteger(total)||total<1||total>64) return {{ok:false,error:'OTA_TOTAL_INVALID'}};
  const folder=DriveApp.getFolderById(PP_M2_OTA_PUBLISH.BETA_FOLDER_ID),all=[];
  for(let i=0;i<total;i++) {{ const it=folder.getFilesByName(ppM2OtaPartName_(id,i)); if(!it.hasNext()) return {{ok:false,error:'OTA_PART_MISSING',chunk_index:i}}; const bytes=it.next().getBlob().getBytes(); for(let k=0;k<bytes.length;k++) all.push(bytes[k]); }}
  const got=ppM2OtaHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,all)); if(got!==PP_M2_OTA_PUBLISH.SHA256) return {{ok:false,error:'OTA_SHA256_MISMATCH',sha256:got}};
  ppM2OtaDeleteNamed_(folder,PP_M2_OTA_PUBLISH.FILE_NAME); ppM2OtaDeleteNamed_(folder,PP_M2_OTA_PUBLISH.SUMS_NAME);
  const file=folder.createFile(Utilities.newBlob(all,'application/vnd.android.package-archive',PP_M2_OTA_PUBLISH.FILE_NAME));
  file.setDescription('Pick Pack 1291 Beta '+PP_M2_OTA_PUBLISH.VERSION+' | Service-first M2'); file.setSharing(DriveApp.Access.ANYONE_WITH_LINK,DriveApp.Permission.VIEW);
  folder.createFile(PP_M2_OTA_PUBLISH.SUMS_NAME,got+'  '+PP_M2_OTA_PUBLISH.FILE_NAME+'\\n','text/plain');
  for(let i=0;i<total;i++) ppM2OtaDeleteNamed_(folder,ppM2OtaPartName_(id,i));
  return {{ok:true,published:true,file_id:file.getId(),file_name:file.getName(),version:PP_M2_OTA_PUBLISH.VERSION,size:file.getSize(),sha256:got}};
}}
'''


def patch_live_content(doc, token_hash):
    files = list(doc.get("files") or [])
    main = next((f for f in files if f.get("name") == "PICK_PACK_API"), None)
    if not main:
        raise RuntimeError("PICK_PACK_API_NOT_FOUND_IN_LIVE_PROJECT")
    src = main.get("source", "")
    anchor = "    if (action === 'update_check') return ppJson_(ppUpdateCheck_(body));"
    routes = "\n    if (action === 'm2_ota_publish_chunk') return ppJson_(ppM2OtaPublishChunk_(body));\n    if (action === 'm2_ota_publish_finalize') return ppJson_(ppM2OtaPublishFinalize_(body));\n    if (action === 'm2_ota_publish_abort') return ppJson_(ppM2OtaPublishAbort_(body));"
    if "m2_ota_publish_chunk" not in src:
        if anchor not in src:
            raise RuntimeError("UPDATE_CHECK_ROUTE_ANCHOR_MISSING")
        main["source"] = src.replace(anchor, anchor + routes, 1)
    files = [f for f in files if f.get("name") != "M2_OTA_PUBLISH"]
    files.append({"name": "M2_OTA_PUBLISH", "type": "SERVER_JS", "source": publisher_source(token_hash)})
    return {"files": files}


def wait_publisher(token_value, upload_id, seconds=120):
    end = time.time() + seconds
    while time.time() < end:
        try:
            r = gas_post({"action": "m2_ota_publish_abort", "publish_token": token_value, "upload_id": upload_id}, timeout=30)
            if r.get("ok") is True:
                return
        except Exception:
            pass
        time.sleep(3)
    raise RuntimeError("TEMP_GAS_PUBLISHER_NOT_LIVE")


def wait_discovery(original_health, seconds=120):
    end = time.time() + seconds
    while time.time() < end:
        try:
            d = gas_post({"action": "service_discovery"}, timeout=30)
            assert_discovery(original_health, d)
            return d
        except Exception:
            time.sleep(3)
    raise RuntimeError("PRODUCTION_GAS_NOT_RESTORED")


def upload_apk(apk, token_value):
    data = apk.read_bytes()
    chunk_size = 512 * 1024
    total = math.ceil(len(data) / chunk_size)
    if total > 64:
        raise RuntimeError("APK_TOO_LARGE_FOR_GUARDED_PUBLISHER")
    upload_id = f"beta19-{os.environ['GITHUB_RUN_ID']}"
    for i in range(total):
        part = data[i * chunk_size:(i + 1) * chunk_size]
        r = gas_post({
            "action": "m2_ota_publish_chunk", "publish_token": token_value,
            "upload_id": upload_id, "version": BETA_VERSION,
            "chunk_index": i, "total_chunks": total,
            "data_b64": base64.b64encode(part).decode(),
        }, timeout=90)
        if not (r.get("ok") and int(r.get("chunk_index", -1)) == i):
            raise RuntimeError("OTA_CHUNK_FAILED:" + json.dumps(r))
        print(f"OTA chunk {i+1}/{total} uploaded")
    r = gas_post({
        "action": "m2_ota_publish_finalize", "publish_token": token_value,
        "upload_id": upload_id, "version": BETA_VERSION, "total_chunks": total,
    }, timeout=240)
    if not (r.get("ok") and r.get("published") and r.get("version") == BETA_VERSION and str(r.get("sha256", "")).lower() == EXPECTED_SHA and int(r.get("size") or 0) == len(data)):
        raise RuntimeError("OTA_FINALIZE_FAILED:" + json.dumps(r))
    return upload_id, r


def verify_ota(original_health):
    beta = gas_post({"action": "update_check", "channel": "BETA", "current_version": PREVIOUS_BETA_VERSION}, timeout=60)
    if not (beta.get("ok") and beta.get("available") is True and beta.get("version_name") == BETA_VERSION and str(beta.get("sha256", "")).lower() == EXPECTED_SHA and beta.get("apk_url")):
        raise RuntimeError("BETA18_UPDATE_CHECK_INVALID:" + json.dumps(beta))
    write_json("beta18-update-check.json", beta)
    url = beta["apk_url"]
    dest = Path("/tmp/ota-downloaded.apk")
    sh(["curl", "-fL", "--connect-timeout", "10", "--max-time", "180", "--retry", "5", "--retry-delay", "2", "--retry-all-errors", url, "-o", str(dest)])
    got = sha256_file(dest)
    if got != EXPECTED_SHA:
        raise RuntimeError(f"DOWNLOADED_OTA_SHA_MISMATCH:{got}")
    bt = Path(os.environ["ANDROID_HOME"]) / "build-tools" / "36.0.0"
    badge = sh([str(bt / "aapt"), "dump", "badging", str(dest)])
    if f"package: name='{BETA_PACKAGE}'" not in badge or f"versionCode='{BETA_VERSION_CODE}'" not in badge or f"versionName='{BETA_VERSION}'" not in badge:
        raise RuntimeError("DOWNLOADED_OTA_PACKAGE_INVALID")
    cert = sh([str(bt / "apksigner"), "verify", "--verbose", "--print-certs", str(dest)])
    m = re.search(r"Signer #1 certificate SHA-256 digest:\s*([0-9A-Fa-f:]+)", cert)
    signer = (m.group(1).replace(":", "").lower() if m else "")
    if signer != EXPECTED_SIGNER:
        raise RuntimeError(f"DOWNLOADED_OTA_SIGNER_MISMATCH:{signer}")
    self_check = gas_post({"action": "update_check", "channel": "BETA", "current_version": BETA_VERSION}, timeout=60)
    if not (self_check.get("ok") and self_check.get("available") is False and self_check.get("version_name") == BETA_VERSION):
        raise RuntimeError("BETA19_SELF_CHECK_INVALID:" + json.dumps(self_check))
    stable = gas_post({"action": "update_check", "channel": "STABLE", "current_version": STABLE_VERSION}, timeout=60)
    if not (stable.get("ok") and stable.get("available") is False):
        raise RuntimeError("STABLE_AFTER_INVALID:" + json.dumps(stable))
    after = service_health(); assert_production_health(after)
    if int((after.get("authority") or {}).get("authority_epoch") or 0) != int((original_health.get("authority") or {}).get("authority_epoch") or 0):
        raise RuntimeError("AUTHORITY_EPOCH_CHANGED_DURING_OTA")
    write_json("beta19-self-check.json", self_check)
    write_json("stable-after.json", stable)
    write_json("service-after.json", after)
    (EVIDENCE / "downloaded-apk-sha256.txt").write_text(got + "  beta19.apk\n")
    return beta


def main():
    trigger = Path("ops/m2-beta19-ota-publish-v2-trigger.txt")
    txt = trigger.read_text() if trigger.exists() else ""
    if "confirmation=OWNER_LOCKED_M2_BETA19_OTA_PUBLISH_V2" not in txt or f"target_version={BETA_VERSION}" not in txt:
        raise RuntimeError("OWNER_OTA_V2_TRIGGER_INVALID")

    before = service_health(); assert_production_health(before); write_json("service-before.json", before)
    disc = gas_post({"action": "service_discovery"}, timeout=60); assert_discovery(before, disc); write_json("discovery-before.json", disc)
    stable_before = gas_post({"action": "update_check", "channel": "STABLE", "current_version": STABLE_VERSION}, timeout=60)
    if not (stable_before.get("ok") and stable_before.get("available") is False):
        raise RuntimeError("STABLE_PRECONDITION_CHANGED:" + json.dumps(stable_before))
    write_json("stable-before.json", stable_before)

    apk = download_candidate()
    token = google_token()
    script_id = os.environ["GAS_SCRIPT_ID"].strip()
    dep_id = deployment_id()
    current_content = gapi(token, f"projects/{script_id}/content")
    current_dep = gapi(token, f"projects/{script_id}/deployments/{dep_id}")
    dc = current_dep.get("deploymentConfig") or {}
    previous_version = dc.get("versionNumber")
    if not previous_version:
        raise RuntimeError("PREVIOUS_GAS_DEPLOYMENT_VERSION_MISSING")
    restore_cfg = {"deploymentConfig": {"scriptId": dc.get("scriptId") or script_id, "versionNumber": previous_version, "manifestFileName": dc.get("manifestFileName") or "appsscript", "description": dc.get("description") or "M2 production primary"}}

    publish_token = hashlib.sha256((os.environ["CLOUDFLARE_ACCOUNT_ID"] + "|" + os.environ["SIGNING_STORE_PASSWORD"] + "|pick-pack-1291-m2-ota-publish-v2").encode()).hexdigest()
    token_hash = hashlib.sha256(publish_token.encode()).hexdigest()
    upload_id = f"beta19-{os.environ['GITHUB_RUN_ID']}"
    publisher_deployed = False
    published = False
    publish_result = None
    try:
        patched = patch_live_content(current_content, token_hash)
        gapi(token, f"projects/{script_id}/content", method="PUT", payload=patched)
        ver = gapi(token, f"projects/{script_id}/versions", method="POST", payload={"description": "Temporary guarded Beta19 OTA publisher V2"})
        version_no = ver.get("versionNumber")
        if not version_no:
            raise RuntimeError("TEMP_GAS_VERSION_MISSING")
        gapi(token, f"projects/{script_id}/deployments/{dep_id}", method="PUT", payload={"deploymentConfig": {"scriptId": script_id, "versionNumber": version_no, "manifestFileName": "appsscript", "description": "Temporary guarded Beta19 OTA publisher V2"}})
        publisher_deployed = True
        wait_publisher(publish_token, "readiness_probe", 120)
        upload_id, publish_result = upload_apk(apk, publish_token)
        published = True
        write_json("publish-result.json", publish_result)
    finally:
        if publisher_deployed and not published:
            try:
                gas_post({"action": "m2_ota_publish_abort", "publish_token": publish_token, "upload_id": upload_id}, timeout=60)
            except Exception:
                pass
        # Restore both project HEAD source and the exact production deployment version.
        try:
            gapi(token, f"projects/{script_id}/content", method="PUT", payload={"files": current_content.get("files") or []})
        finally:
            gapi(token, f"projects/{script_id}/deployments/{dep_id}", method="PUT", payload=restore_cfg)

    restored = wait_discovery(before, 120); write_json("discovery-after.json", restored)
    verify_ota(before)
    print(json.dumps({"ok": True, "beta_version": BETA_VERSION, "sha256": EXPECTED_SHA, "published_file_id": (publish_result or {}).get("file_id"), "stable_published": False}, indent=2))


if __name__ == "__main__":
    main()
