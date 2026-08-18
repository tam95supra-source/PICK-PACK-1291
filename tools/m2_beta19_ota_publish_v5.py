#!/usr/bin/env python3
import base64
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import m2_beta19_ota_publish as publisher

ARTIFACT_RUN_ID = "32186998997"
ARTIFACT_NAME = "pick-pack-1291-0.4.2-beta.19-signed-validation"


def curl_service_health():
    p = subprocess.run([
        "curl", "-fsS", "--connect-timeout", "5", "--max-time", "30",
        "--retry", "3", "--retry-delay", "2", "--retry-all-errors",
        publisher.SERVICE_URL + "/health"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode != 0:
        raise RuntimeError("SERVICE_HEALTH_CURL_FAILED:" + p.stderr.decode("utf-8", "replace"))
    return json.loads(p.stdout.decode("utf-8"))


def gh_download_candidate():
    dest = Path("/tmp/m2-beta19-candidate-v5")
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    p = subprocess.run([
        "gh", "run", "download", ARTIFACT_RUN_ID,
        "--repo", os.environ["GITHUB_REPOSITORY"],
        "--name", ARTIFACT_NAME,
        "--dir", str(dest),
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode != 0:
        raise RuntimeError("GH_RUN_DOWNLOAD_FAILED:" + p.stderr.decode("utf-8", "replace"))
    apks = list(dest.rglob("*.apk"))
    if len(apks) != 1:
        raise RuntimeError(f"CANDIDATE_APK_COUNT:{len(apks)}")
    apk = apks[0]
    got = publisher.sha256_file(apk)
    if got != publisher.EXPECTED_SHA:
        raise RuntimeError(f"CANDIDATE_SHA_MISMATCH:{got}")
    bt = Path(os.environ["ANDROID_HOME"]) / "build-tools" / "36.0.0"
    badge = publisher.sh([str(bt / "aapt"), "dump", "badging", str(apk)])
    (publisher.EVIDENCE / "package-badging.txt").write_text(badge)
    if f"package: name='{publisher.BETA_PACKAGE}'" not in badge or f"versionCode='{publisher.BETA_VERSION_CODE}'" not in badge or f"versionName='{publisher.BETA_VERSION}'" not in badge:
        raise RuntimeError("CANDIDATE_PACKAGE_METADATA_INVALID")
    cert = publisher.sh([str(bt / "apksigner"), "verify", "--verbose", "--print-certs", str(apk)])
    (publisher.EVIDENCE / "signer.txt").write_text(cert)
    m = re.search(r"Signer #1 certificate SHA-256 digest:\s*([0-9A-Fa-f:]+)", cert)
    signer = m.group(1).replace(":", "").lower() if m else ""
    if signer != publisher.EXPECTED_SIGNER:
        raise RuntimeError(f"CANDIDATE_SIGNER_MISMATCH:{signer}")
    out = Path("/tmp/beta19.apk")
    shutil.copy2(apk, out)
    return out


def is_temp_route_not_ready(resp):
    error = str((resp or {}).get("error", "")).upper()
    return error in {"UNAUTHORIZED", "OTA_PUBLISH_UNAUTHORIZED", "UNKNOWN_ACTION", "ACTION_UNSUPPORTED"}


def stable_wait_publisher(token_value, upload_id, seconds=240):
    deadline = time.time() + seconds
    consecutive = 0
    attempts = 0
    while time.time() < deadline:
        attempts += 1
        try:
            r = publisher.gas_post({"action": "m2_ota_publish_abort", "publish_token": token_value, "upload_id": upload_id}, timeout=30)
            if r.get("ok") is True:
                consecutive += 1
                print(f"TEMP_PUBLISHER_READY consecutive={consecutive} attempt={attempts}")
                if consecutive >= 8:
                    return
            else:
                consecutive = 0
                print("TEMP_PUBLISHER_NOT_READY " + json.dumps(r, separators=(",", ":")))
        except Exception as e:
            consecutive = 0
            print(f"TEMP_PUBLISHER_PROBE_ERROR:{e}")
        time.sleep(3)
    raise RuntimeError("TEMP_GAS_PUBLISHER_NOT_STABLE")


def post_chunk_with_version_retry(payload, chunk_index):
    last = None
    for attempt in range(1, 31):
        r = publisher.gas_post(payload, timeout=90)
        last = r
        if r.get("ok") is True and int(r.get("chunk_index", -1)) == chunk_index:
            return r
        if is_temp_route_not_ready(r):
            print(f"OTA_CHUNK_ROUTE_PROPAGATION chunk={chunk_index} attempt={attempt} error={r.get('error')}")
            time.sleep(3)
            continue
        raise RuntimeError("OTA_CHUNK_FAILED:" + json.dumps(r))
    raise RuntimeError("OTA_CHUNK_PROPAGATION_TIMEOUT:" + json.dumps(last))


def finalize_with_version_retry(payload):
    last = None
    for attempt in range(1, 31):
        r = publisher.gas_post(payload, timeout=240)
        last = r
        if r.get("ok") is True and r.get("published") is True:
            return r
        if is_temp_route_not_ready(r):
            print(f"OTA_FINALIZE_ROUTE_PROPAGATION attempt={attempt} error={r.get('error')}")
            time.sleep(3)
            continue
        raise RuntimeError("OTA_FINALIZE_FAILED:" + json.dumps(r))
    raise RuntimeError("OTA_FINALIZE_PROPAGATION_TIMEOUT:" + json.dumps(last))


def robust_upload_apk(apk, token_value):
    data = apk.read_bytes()
    chunk_size = 512 * 1024
    total = math.ceil(len(data) / chunk_size)
    if total > 64:
        raise RuntimeError("APK_TOO_LARGE_FOR_GUARDED_PUBLISHER")
    upload_id = f"beta19-{os.environ['GITHUB_RUN_ID']}"
    for i in range(total):
        part = data[i * chunk_size:(i + 1) * chunk_size]
        payload = {
            "action": "m2_ota_publish_chunk", "publish_token": token_value,
            "upload_id": upload_id, "version": publisher.BETA_VERSION,
            "chunk_index": i, "total_chunks": total,
            "data_b64": base64.b64encode(part).decode(),
        }
        post_chunk_with_version_retry(payload, i)
        print(f"OTA chunk {i+1}/{total} uploaded")
    result = finalize_with_version_retry({
        "action": "m2_ota_publish_finalize", "publish_token": token_value,
        "upload_id": upload_id, "version": publisher.BETA_VERSION, "total_chunks": total,
    })
    if not (result.get("ok") and result.get("published") and result.get("version") == publisher.BETA_VERSION and str(result.get("sha256", "")).lower() == publisher.EXPECTED_SHA and int(result.get("size") or 0) == len(data)):
        raise RuntimeError("OTA_FINALIZE_IDENTITY_INVALID:" + json.dumps(result))
    return upload_id, result


publisher.service_health = curl_service_health
publisher.download_candidate = gh_download_candidate
publisher.wait_publisher = stable_wait_publisher
publisher.upload_apk = robust_upload_apk
publisher.main()
