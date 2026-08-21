#!/usr/bin/env python3
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAS_WEB_URL = "https://script.google.com/macros/s/AKfycbzbEoGfbNg6s2HnP-gUpcBJ7mMIkVBtYuQKMndb9seDV2c55lQwSUO1GZ-LtQ2CxMCauA/exec"
OLD_SERVICE_URL = "https://pick-pack-1291-service.pp1291-d79b87776e86.workers.dev"
TARGET_ACCOUNT_SUBDOMAIN = "pp1291"
WORKER_NAME = "pick-pack-1291-service"
TARGET_SERVICE_URL = f"https://{WORKER_NAME}.{TARGET_ACCOUNT_SUBDOMAIN}.workers.dev"
SERVICE_GENERATION = "m2-prod-20260819-001"


def need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"MISSING:{name}")
    return value


def secret_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def run(args, *, input_text=None, check=True):
    p = subprocess.run(args, cwd=ROOT, input=input_text, text=True, capture_output=True)
    if check and p.returncode:
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        raise RuntimeError(f"COMMAND_FAILED:{args[0]}:{p.returncode}")
    return p


def curl_json(url: str, *, method="GET", payload=None, headers=None, fail=True, follow=False):
    args = ["curl", "-sS"]
    if fail:
        args.append("-f")
    if follow:
        args.append("-L")
    args += ["-X", method]
    for k, v in (headers or {}).items():
        args += ["-H", f"{k}: {v}"]
    if payload is not None:
        args += ["-H", "content-type: application/json", "--data-binary", json.dumps(payload, ensure_ascii=False)]
    args.append(url)
    p = run(args, check=False)
    if p.returncode and fail:
        raise RuntimeError(f"HTTP_CURL_FAILED:{url}:{p.stderr.strip()[:240]}")
    try:
        body = json.loads(p.stdout or "{}")
    except Exception:
        body = {"_raw": (p.stdout or "")[:1000]}
    return p.returncode, body


def gas(payload):
    return curl_json(GAS_WEB_URL, method="POST", payload=payload, fail=True, follow=True)[1]


def service(path, base=OLD_SERVICE_URL, *, method="GET", payload=None, headers=None, fail=True):
    return curl_json(base + path, method=method, payload=payload, headers=headers, fail=fail)[1]


def assert_true(cond, code, detail=None):
    if not cond:
        raise RuntimeError(code + (f":{detail}" if detail else ""))


def oauth_token(client_id, client_secret, refresh_token):
    p = run([
        "curl", "-fsS", "https://oauth2.googleapis.com/token",
        "-H", "Content-Type: application/x-www-form-urlencoded",
        "--data-urlencode", f"client_id={client_id}",
        "--data-urlencode", f"client_secret={client_secret}",
        "--data-urlencode", f"refresh_token={refresh_token}",
        "--data-urlencode", "grant_type=refresh_token",
    ])
    token = json.loads(p.stdout).get("access_token", "")
    assert_true(bool(token), "GOOGLE_OAUTH_ACCESS_TOKEN_MISSING")
    print(f"::add-mask::{token}")
    return token


def apps_script_request(url, token, method="GET", payload=None):
    headers = {"Authorization": f"Bearer {token}"}
    return curl_json(url, method=method, payload=payload, headers=headers, fail=True)[1]


def build_recovery_gas_source():
    run(["python3", "tools/apply_s13_service_url_gas_patch.py"])
    api = ROOT / "google-apps-script/PICK_PACK_API.gs"
    s = api.read_text()
    anchor = "    if (action === 'service_discovery') return ppJson_(ppM2Discovery_(body));\n"
    route = "    if (action === 'm2_recovery_internal') return ppJson_(ppM2RecoveryInternal_(body));\n"
    if route not in s:
        assert_true(s.count(anchor) == 1, "RECOVERY_ROUTE_ANCHOR_MISMATCH")
        s = s.replace(anchor, anchor + route, 1)
        api.write_text(s)

    m2 = ROOT / "google-apps-script/SERVICE_MIGRATION_M2.gs"
    s = m2.read_text()
    if "function ppM2RecoveryInternal_" not in s:
        s += r'''

// S13 temporary recovery wrapper. Authority transitions remain implemented by the existing M2
// begin/flush/complete functions; this wrapper only supplies a CI-safe internal authorization gate.
function ppM2RecoveryInternal_(body){
  body=body||{};
  if(String(body.confirmation||'')!=='OWNER_LOCKED_M2_FAILBACK')return {ok:false,error:'FAILBACK_CONFIRMATION_REQUIRED'};
  if(!ppM2BridgeSecret_()||String(body.bridge_secret||'')!==ppM2BridgeSecret_())return {ok:false,error:'RECOVERY_BRIDGE_SECRET_INVALID'};
  const auth={login_id:'S13_RECOVERY',role:'SUPERADMIN',display_name:'S13_RECOVERY'};
  const phase=String(body.phase||'');
  if(phase==='begin')return ppM2BeginReconcile_(auth,body);
  if(phase==='flush')return ppM2FlushFallbackInbox_();
  if(phase==='complete')return ppM2CompleteFailback_(auth,body);
  return {ok:false,error:'RECOVERY_PHASE_INVALID'};
}
'''
        m2.write_text(s)

    for src in (api, m2):
        temp = Path("/tmp") / (src.stem + ".js")
        temp.write_text(src.read_text())
        run(["node", "--check", str(temp)])


def deploy_gas(client_id, client_secret, refresh_token, script_secret, deployment_secret):
    build_recovery_gas_source()
    token = oauth_token(client_id, client_secret, refresh_token)
    script_id = re.sub(r"\s+", "", script_secret)
    raw = re.sub(r"\s+", "", deployment_secret)
    m = re.search(r"/s/([^/]+)", raw)
    deployment_id = m.group(1) if m else raw
    assert_true(bool(script_id and deployment_id), "GAS_IDS_EMPTY")

    gas_dir = ROOT / "google-apps-script"
    files = []
    for p in sorted(gas_dir.glob("*.gs")):
        files.append({"name": p.stem, "type": "SERVER_JS", "source": p.read_text()})
    files.append({"name": "appsscript", "type": "JSON", "source": (gas_dir / "appsscript.json").read_text()})
    base = f"https://script.googleapis.com/v1/projects/{script_id}"
    apps_script_request(base + "/content", token, "PUT", {"files": files})
    version = apps_script_request(base + "/versions", token, "POST", {"description": "S13 fenced authority reconciliation wrapper"})
    version_no = int(version["versionNumber"])
    apps_script_request(
        base + f"/deployments/{deployment_id}", token, "PUT",
        {"deploymentConfig": {"scriptId": script_id, "versionNumber": version_no, "manifestFileName": "appsscript", "description": "Pick Pack 1291 live API S13 authority reconciliation"}},
    )
    print(f"GAS_DEPLOYED_VERSION={version_no}")


def wait_recovery_route(max_seconds=360):
    end = time.time() + max_seconds
    last = {}
    while time.time() < end:
        try:
            last = gas({"action": "m2_recovery_internal", "confirmation": "invalid"})
            if last.get("error") == "FAILBACK_CONFIRMATION_REQUIRED":
                return
        except Exception:
            pass
        time.sleep(3)
    raise RuntimeError(f"RECOVERY_WRAPPER_NOT_PROPAGATED:{json.dumps(last)[:400]}")


def cf_json(account_id, api_token, path, *, method="GET", payload=None):
    return curl_json(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}{path}",
        method=method,
        payload=payload,
        headers={"Authorization": f"Bearer {api_token}"},
        fail=True,
    )[1]


def main():
    cf_token = need("CLOUDFLARE_API_TOKEN")
    account_id = need("CLOUDFLARE_ACCOUNT_ID")
    google_client_id = need("GOOGLE_OAUTH_CLIENT_ID")
    google_client_secret = need("GOOGLE_OAUTH_CLIENT_SECRET")
    google_refresh = need("GOOGLE_OAUTH_REFRESH_TOKEN")
    gas_script_id = need("GAS_SCRIPT_ID")
    gas_deployment_id = need("GAS_DEPLOYMENT_ID")
    signing_store_password = need("SIGNING_STORE_PASSWORD")

    bridge = secret_hash(account_id, google_client_secret, "pick-pack-1291-m2-bridge-v1")
    admin = secret_hash(account_id, signing_store_password, "pick-pack-1291-m2-admin-v1")
    print(f"::add-mask::{bridge}")
    print(f"::add-mask::{admin}")

    svc = service("/v1/authority")
    disc = gas({"action": "service_discovery", "_app_channel": "BETA", "_app_version": "0.4.2-beta.20"})
    sa = svc.get("authority", {})
    smode, sepoch, sgen = sa.get("mode"), int(sa.get("authority_epoch", 0)), sa.get("service_generation")
    gmode = disc.get("authority_mode")
    ga = disc.get("authority", {})
    gepoch, gseq, ggen = int(ga.get("authority_epoch", 0)), int(ga.get("authority_seq", 0)), disc.get("service_generation")
    print(f"INITIAL_SERVICE={smode} epoch={sepoch} generation={sgen}")
    print(f"INITIAL_GAS={gmode} epoch={gepoch} seq={gseq} generation={ggen} url={disc.get('service_url')}")
    assert_true(sgen == SERVICE_GENERATION and ggen == SERVICE_GENERATION, "GENERATION_MISMATCH")

    already_converged = smode == "SERVICE_PRIMARY" and gmode == "SERVICE_PRIMARY" and sepoch == gepoch
    safe_mismatch = smode == "SERVICE_PRIMARY" and gmode == "GOOGLE_FALLBACK" and gepoch == sepoch + 1 and gseq >= 1
    assert_true(already_converged or safe_mismatch, "UNSAFE_AUTHORITY_COMBINATION")

    if safe_mismatch:
        deploy_gas(google_client_id, google_client_secret, google_refresh, gas_script_id, gas_deployment_id)
        wait_recovery_route()

        begin = gas({"action": "m2_recovery_internal", "phase": "begin", "confirmation": "OWNER_LOCKED_M2_FAILBACK", "bridge_secret": bridge})
        print("RECONCILE_BEGIN=" + json.dumps({k: begin.get(k) for k in ("ok", "authority_mode", "authority_epoch", "fallback_seq")}))
        assert_true(begin.get("ok") is True and begin.get("authority_mode") == "RECONCILING", "RECONCILE_BEGIN_FAILED", str(begin)[:400])
        fallback_seq = int(begin.get("fallback_seq", 0))
        assert_true(fallback_seq >= gseq and fallback_seq >= 1, "FALLBACK_SEQUENCE_REGRESSED")

        flush = gas({"action": "m2_recovery_internal", "phase": "flush", "confirmation": "OWNER_LOCKED_M2_FAILBACK", "bridge_secret": bridge})
        print("FALLBACK_FLUSH=" + json.dumps({k: flush.get(k) for k in ("ok", "sent", "pending", "authority_epoch")}))
        assert_true(flush.get("ok") is True and int(flush.get("pending", -1)) == 0, "FALLBACK_FLUSH_FAILED", str(flush)[:500])

        failback_payload = {"fallback_epoch": gepoch, "expected_service_epoch": sepoch, "confirmation": "OWNER_LOCKED_M2_FAILBACK", "initiated_by": "S13_OWNER_RUNTIME_RECOVERY"}
        fb = service("/internal/recovery/failback", method="POST", payload=failback_payload, headers={"x-m1-admin-token": admin})
        print("SERVICE_FAILBACK=" + json.dumps({"ok": fb.get("ok"), "validation": fb.get("validation"), "authority": fb.get("authority")}))
        new_auth = fb.get("authority", {})
        new_epoch = int(new_auth.get("authority_epoch", 0))
        assert_true(fb.get("ok") is True and new_auth.get("mode") == "SERVICE_PRIMARY" and new_epoch == gepoch + 1, "SERVICE_FAILBACK_FAILED", str(fb)[:600])

        complete = gas({"action": "m2_recovery_internal", "phase": "complete", "confirmation": "OWNER_LOCKED_M2_FAILBACK", "bridge_secret": bridge, "authority_epoch": new_epoch, "service_generation": SERVICE_GENERATION, "service_url": OLD_SERVICE_URL})
        print("GAS_FAILBACK_COMPLETE=" + json.dumps({k: complete.get(k) for k in ("ok", "authority_mode", "authority_epoch", "service_generation", "service_url")}))
        assert_true(complete.get("ok") is True and complete.get("authority_mode") == "SERVICE_PRIMARY" and int(complete.get("authority_epoch", 0)) == new_epoch, "GAS_FAILBACK_COMPLETE_FAILED", str(complete)[:500])

    svc2 = service("/v1/authority")
    disc2 = gas({"action": "service_discovery", "_app_channel": "BETA", "_app_version": "0.4.2-beta.20"})
    a2 = svc2.get("authority", {})
    assert_true(a2.get("mode") == "SERVICE_PRIMARY" and disc2.get("authority_mode") == "SERVICE_PRIMARY", "POST_RECOVERY_NOT_PRIMARY")
    assert_true(int(a2.get("authority_epoch", 0)) == int(disc2.get("authority", {}).get("authority_epoch", -1)), "POST_RECOVERY_EPOCH_MISMATCH")
    converged_epoch = int(a2.get("authority_epoch", 0))
    print(f"AUTHORITY_CONVERGED_EPOCH={converged_epoch}")

    scripts = cf_json(account_id, cf_token, "/workers/scripts")
    assert_true(scripts.get("success") is True, "CF_SCRIPTS_QUERY_FAILED")
    names = sorted(x.get("id", "") for x in scripts.get("result", []))
    assert_true(names == [WORKER_NAME], "CF_ACCOUNT_SCOPE_UNSAFE", ",".join(names))
    sub = cf_json(account_id, cf_token, "/workers/subdomain")
    current_sub = (sub.get("result") or {}).get("subdomain", "")
    print(f"CLOUDFLARE_SUBDOMAIN_BEFORE={current_sub}")

    if current_sub != TARGET_ACCOUNT_SUBDOMAIN:
        prepare = gas({"action": "m2_service_url_prepare_internal", "confirmation": "OWNER_LOCKED_M2_SERVICE_URL_ONLY", "bridge_secret": bridge, "service_url": TARGET_SERVICE_URL})
        assert_true(prepare.get("ok") is True and prepare.get("authority_mode") == "SERVICE_PRIMARY", "DOMAIN_PREPARE_FAILED", str(prepare)[:500])
        changed = cf_json(account_id, cf_token, "/workers/subdomain", method="PUT", payload={"subdomain": TARGET_ACCOUNT_SUBDOMAIN})
        assert_true(changed.get("success") is True, "CF_SUBDOMAIN_UPDATE_FAILED", str(changed)[:500])
        print(f"CLOUDFLARE_SUBDOMAIN_CHANGED={TARGET_ACCOUNT_SUBDOMAIN}")

    new_healthy = False
    last_health = {}
    for _ in range(90):
        try:
            last_health = service("/health", base=TARGET_SERVICE_URL)
            new_auth = service("/v1/authority", base=TARGET_SERVICE_URL)
            if last_health.get("ok") is True and new_auth.get("authority", {}).get("mode") == "SERVICE_PRIMARY":
                new_healthy = True
                break
        except Exception:
            pass
        time.sleep(2)

    # Once Cloudflare accepted the account-subdomain change, the old hostname is no longer canonical.
    # Finalize discovery even if health propagation was slow, then fail the verification explicitly.
    finalize = gas({"action": "m2_service_url_update_internal", "confirmation": "OWNER_LOCKED_M2_SERVICE_URL_ONLY", "bridge_secret": bridge, "service_url": TARGET_SERVICE_URL})
    assert_true(finalize.get("ok") is True and finalize.get("authority_mode") == "SERVICE_PRIMARY", "DOMAIN_FINALIZE_FAILED", str(finalize)[:500])
    assert_true(new_healthy, "NEW_WORKERS_DEV_URL_NOT_HEALTHY", str(last_health)[:500])

    final_health = service("/health", base=TARGET_SERVICE_URL)
    final_service = service("/v1/authority", base=TARGET_SERVICE_URL)
    final_gas = gas({"action": "service_discovery", "_app_channel": "BETA", "_app_version": "0.4.2-beta.20"})
    final_sa = final_service.get("authority", {})
    final_ga = final_gas.get("authority", {})
    assert_true(final_sa.get("mode") == "SERVICE_PRIMARY" and final_gas.get("authority_mode") == "SERVICE_PRIMARY", "FINAL_MODE_MISMATCH")
    assert_true(int(final_sa.get("authority_epoch", 0)) == int(final_ga.get("authority_epoch", -1)), "FINAL_EPOCH_MISMATCH")
    assert_true(final_gas.get("service_url") == TARGET_SERVICE_URL, "FINAL_DISCOVERY_URL_MISMATCH")
    assert_true(final_health.get("generation") == SERVICE_GENERATION, "FINAL_GENERATION_MISMATCH")
    repl = final_health.get("replication", {})
    assert_true(repl.get("state") == "HEALTHY" and int(repl.get("pending_count", -1)) == 0, "FINAL_REPLICATION_NOT_HEALTHY", str(repl))
    print(f"FINAL_SERVICE_URL={TARGET_SERVICE_URL}")
    print(f"FINAL_AUTHORITY_EPOCH={final_sa.get('authority_epoch')}")
    print("S13_AUTHORITY_RECOVERY_AND_DOMAIN=PASS")


if __name__ == "__main__":
    main()
