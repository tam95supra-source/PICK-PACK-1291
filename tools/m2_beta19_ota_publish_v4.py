#!/usr/bin/env python3
import json
from pathlib import Path
import re
import shutil
import subprocess
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
    dest = Path("/tmp/m2-beta19-candidate-v4")
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    p = subprocess.run([
        "gh", "run", "download", ARTIFACT_RUN_ID,
        "--repo", __import__("os").environ["GITHUB_REPOSITORY"],
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
    bt = Path(__import__("os").environ["ANDROID_HOME"]) / "build-tools" / "36.0.0"
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


publisher.service_health = curl_service_health
publisher.download_candidate = gh_download_candidate
publisher.main()
