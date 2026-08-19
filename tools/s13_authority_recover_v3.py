#!/usr/bin/env python3
import json
import os
import subprocess
import time
import urllib.parse

import s13_authority_recover as core

SHEET_ID = "1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78"
FALLBACK_TAB = "__PP_M2_FALLBACK_EVENTS"


def curl_json_fixed(url: str, *, method="GET", payload=None, headers=None, fail=True, follow=False):
    args = ["curl", "-sS"]
    if fail:
        args.append("-f")
    if follow:
        args.append("-L")
    if not (method == "POST" and payload is not None):
        args += ["-X", method]
    for k, v in (headers or {}).items():
        args += ["-H", f"{k}: {v}"]
    if payload is not None:
        args += ["-H", "content-type: application/json", "--data-binary", json.dumps(payload, ensure_ascii=False)]
    args.append(url)
    p = subprocess.run(args, cwd=core.ROOT, text=True, capture_output=True)
    if p.returncode and fail:
        raise RuntimeError(f"HTTP_CURL_FAILED:{url}:{p.stderr.strip()[:300]}")
    try:
        body = json.loads(p.stdout or "{}")
    except Exception:
        body = {"_raw": (p.stdout or "")[:1000]}
    return p.returncode, body


core.curl_json = curl_json_fixed


def sheets_get(token: str, range_a1: str):
    encoded = urllib.parse.quote(range_a1, safe="")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{encoded}?majorDimension=ROWS"
    return core.curl_json(url, headers={"Authorization": f"Bearer {token}"})[1]


def sheets_put(token: str, range_a1: str, values):
    encoded = urllib.parse.quote(range_a1, safe="")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{encoded}?valueInputOption=RAW"
    return core.curl_json(url, method="PUT", payload={"range": range_a1, "majorDimension": "ROWS", "values": values}, headers={"Authorization": f"Bearer {token}"})[1]


def current_state():
    svc = core.service("/v1/authority")
    disc = core.gas({"action": "service_discovery", "_app_channel": "BETA", "_app_version": "0.4.2-beta.20"})
    sa = svc.get("authority", {})
    ga = disc.get("authority", {})
    return svc, disc, str(sa.get("mode")), int(sa.get("authority_epoch", 0)), str(disc.get("authority_mode")), int(ga.get("authority_epoch", 0)), int(ga.get("authority_seq", 0))


def ingest_sheet_ledger(token: str, bridge: str, fallback_epoch: int):
    data = sheets_get(token, f"'{FALLBACK_TAB}'!A:M")
    rows = data.get("values", [])
    expected_header = ["event_id","authority_epoch","authority_seq","service_generation","action","business_date","actor","role","device_id","occurred_at","payload_json","checksum","ingest_status"]
    core.assert_true(bool(rows) and rows[0][:13] == expected_header, "FALLBACK_SHEET_HEADER_MISMATCH")
    candidates = []
    for sheet_row, row in enumerate(rows[1:], start=2):
        row = list(row) + [""] * (13 - len(row))
        if int(row[1] or 0) != fallback_epoch:
            continue
        candidates.append((sheet_row, row[:13]))
    core.assert_true(bool(candidates), "FALLBACK_EPOCH_ROWS_MISSING")
    seqs = sorted(int(r[1][2]) for r in candidates)
    core.assert_true(seqs == list(range(1, max(seqs) + 1)), "FALLBACK_SEQUENCE_NOT_CONTIGUOUS", str(seqs))

    sent = 0
    for sheet_row, r in sorted(candidates, key=lambda x: int(x[1][2])):
        status = str(r[12] or "")
        if status == "INGESTED":
            continue
        core.assert_true(status == "PENDING", "FALLBACK_ROW_STATUS_UNSAFE", f"row={sheet_row},status={status}")
        payload = {
            "event_id": r[0],
            "authority_epoch": int(r[1]),
            "authority_seq": int(r[2]),
            "service_generation": r[3],
            "event": {
                "action": r[4], "business_date": r[5], "actor": r[6], "role": r[7],
                "device_id": r[8], "occurred_at": r[9], "payload_json": r[10],
            },
            "checksum": r[11],
        }
        result = core.service("/internal/fallback/ingest", method="POST", payload=payload, headers={"x-gas-bridge-secret": bridge})
        core.assert_true(result.get("ok") is True and int(result.get("authority_epoch", 0)) == fallback_epoch and int(result.get("authority_seq", 0)) == int(r[2]), "DIRECT_FALLBACK_INGEST_FAILED", str(result)[:600])
        sheets_put(token, f"'{FALLBACK_TAB}'!M{sheet_row}:M{sheet_row}", [["INGESTED"]])
        sent += 1
        print(f"INGESTED_FALLBACK_SEQ={r[2]}")

    verify = sheets_get(token, f"'{FALLBACK_TAB}'!A:M").get("values", [])
    pending = []
    for row in verify[1:]:
        row = list(row) + [""] * (13 - len(row))
        if int(row[1] or 0) == fallback_epoch and str(row[12] or "") == "PENDING":
            pending.append(int(row[2]))
    core.assert_true(not pending, "FALLBACK_PENDING_REMAINS", str(pending))
    print(f"DIRECT_FALLBACK_INGEST_SENT={sent}")
    print(f"DIRECT_FALLBACK_INGEST_TOTAL={len(candidates)}")
    return len(candidates)


def shorten_domain(account_id: str, cf_token: str, bridge: str):
    scripts = core.cf_json(account_id, cf_token, "/workers/scripts")
    names = sorted(x.get("id", "") for x in scripts.get("result", []))
    core.assert_true(scripts.get("success") is True and names == [core.WORKER_NAME], "CF_ACCOUNT_SCOPE_UNSAFE", ",".join(names))
    current_sub = (core.cf_json(account_id, cf_token, "/workers/subdomain").get("result") or {}).get("subdomain", "")
    print(f"CLOUDFLARE_SUBDOMAIN_BEFORE={current_sub}")
    if current_sub != core.TARGET_ACCOUNT_SUBDOMAIN:
        prepared = core.gas({"action": "m2_service_url_prepare_internal", "confirmation": "OWNER_LOCKED_M2_SERVICE_URL_ONLY", "bridge_secret": bridge, "service_url": core.TARGET_SERVICE_URL})
        core.assert_true(prepared.get("ok") is True and prepared.get("authority_mode") == "SERVICE_PRIMARY", "DOMAIN_PREPARE_FAILED", str(prepared)[:500])
        changed = core.cf_json(account_id, cf_token, "/workers/subdomain", method="PUT", payload={"subdomain": core.TARGET_ACCOUNT_SUBDOMAIN})
        core.assert_true(changed.get("success") is True, "CF_SUBDOMAIN_UPDATE_FAILED", str(changed)[:500])
        print(f"CLOUDFLARE_SUBDOMAIN_CHANGED={core.TARGET_ACCOUNT_SUBDOMAIN}")

    healthy = False
    last = {}
    for _ in range(90):
        try:
            h = core.service("/health", base=core.TARGET_SERVICE_URL)
            a = core.service("/v1/authority", base=core.TARGET_SERVICE_URL)
            last = {"health": h, "authority": a}
            if h.get("ok") is True and a.get("authority", {}).get("mode") == "SERVICE_PRIMARY":
                healthy = True
                break
        except Exception as e:
            last = {"error": str(e)}
        time.sleep(2)

    finalized = core.gas({"action": "m2_service_url_update_internal", "confirmation": "OWNER_LOCKED_M2_SERVICE_URL_ONLY", "bridge_secret": bridge, "service_url": core.TARGET_SERVICE_URL})
    core.assert_true(finalized.get("ok") is True and finalized.get("authority_mode") == "SERVICE_PRIMARY", "DOMAIN_FINALIZE_FAILED", str(finalized)[:500])
    core.assert_true(healthy, "NEW_WORKERS_DEV_URL_NOT_HEALTHY", str(last)[:700])


def main():
    cf_token = core.need("CLOUDFLARE_API_TOKEN")
    account_id = core.need("CLOUDFLARE_ACCOUNT_ID")
    google_client_id = core.need("GOOGLE_OAUTH_CLIENT_ID")
    google_client_secret = core.need("GOOGLE_OAUTH_CLIENT_SECRET")
    google_refresh = core.need("GOOGLE_OAUTH_REFRESH_TOKEN")
    signing_store_password = core.need("SIGNING_STORE_PASSWORD")
    bridge = core.secret_hash(account_id, google_client_secret, "pick-pack-1291-m2-bridge-v1")
    admin = core.secret_hash(account_id, signing_store_password, "pick-pack-1291-m2-admin-v1")
    print(f"::add-mask::{bridge}")
    print(f"::add-mask::{admin}")
    token = core.oauth_token(google_client_id, google_client_secret, google_refresh)

    svc, disc, smode, sepoch, gmode, gepoch, gseq = current_state()
    print(f"RECOVERY_START_SERVICE={smode} epoch={sepoch}")
    print(f"RECOVERY_START_GAS={gmode} epoch={gepoch} seq={gseq}")
    core.assert_true(svc.get("authority", {}).get("service_generation") == core.SERVICE_GENERATION and disc.get("service_generation") == core.SERVICE_GENERATION, "GENERATION_MISMATCH")

    if smode == "SERVICE_PRIMARY" and gmode == "GOOGLE_FALLBACK" and gepoch == sepoch + 1:
        begin = core.gas({"action": "m2_recovery_internal", "phase": "begin", "confirmation": "OWNER_LOCKED_M2_FAILBACK", "bridge_secret": bridge})
        core.assert_true(begin.get("ok") is True and begin.get("authority_mode") == "RECONCILING", "RECONCILE_BEGIN_FAILED", str(begin)[:500])
        gmode = "RECONCILING"
        gseq = int(begin.get("fallback_seq", gseq))
    elif smode == "SERVICE_PRIMARY" and gmode == "RECONCILING" and gepoch == sepoch + 1:
        pass
    elif smode == "SERVICE_PRIMARY" and gmode == "SERVICE_PRIMARY" and gepoch == sepoch:
        print("AUTHORITY_ALREADY_CONVERGED")
        shorten_domain(account_id, cf_token, bridge)
        final_verify()
        return
    elif smode == "SERVICE_PRIMARY" and gmode == "RECONCILING" and sepoch == gepoch + 1:
        # Service failback finished on an earlier attempt; only GAS completion remains.
        complete = core.gas({"action": "m2_recovery_internal", "phase": "complete", "confirmation": "OWNER_LOCKED_M2_FAILBACK", "bridge_secret": bridge, "authority_epoch": sepoch, "service_generation": core.SERVICE_GENERATION, "service_url": core.OLD_SERVICE_URL})
        core.assert_true(complete.get("ok") is True, "GAS_FAILBACK_COMPLETE_FAILED", str(complete)[:500])
        shorten_domain(account_id, cf_token, bridge)
        final_verify()
        return
    else:
        raise RuntimeError(f"UNSAFE_RECOVERY_STATE:service={smode}/{sepoch},gas={gmode}/{gepoch}")

    total = ingest_sheet_ledger(token, bridge, gepoch)
    core.assert_true(total >= gseq and gseq >= 1, "FALLBACK_LEDGER_COUNT_MISMATCH", f"total={total},gas_seq={gseq}")

    fb = core.service("/internal/recovery/failback", method="POST", payload={"fallback_epoch": gepoch, "expected_service_epoch": sepoch, "confirmation": "OWNER_LOCKED_M2_FAILBACK", "initiated_by": "S13_OWNER_RUNTIME_RECOVERY"}, headers={"x-m1-admin-token": admin})
    print("SERVICE_FAILBACK=" + json.dumps({"ok": fb.get("ok"), "validation": fb.get("validation"), "authority": fb.get("authority")}))
    new_auth = fb.get("authority", {})
    new_epoch = int(new_auth.get("authority_epoch", 0))
    core.assert_true(fb.get("ok") is True and new_auth.get("mode") == "SERVICE_PRIMARY" and new_epoch == gepoch + 1, "SERVICE_FAILBACK_FAILED", str(fb)[:700])

    complete = core.gas({"action": "m2_recovery_internal", "phase": "complete", "confirmation": "OWNER_LOCKED_M2_FAILBACK", "bridge_secret": bridge, "authority_epoch": new_epoch, "service_generation": core.SERVICE_GENERATION, "service_url": core.OLD_SERVICE_URL})
    core.assert_true(complete.get("ok") is True and complete.get("authority_mode") == "SERVICE_PRIMARY" and int(complete.get("authority_epoch", 0)) == new_epoch, "GAS_FAILBACK_COMPLETE_FAILED", str(complete)[:700])
    print(f"AUTHORITY_RECONCILED_EPOCH={new_epoch}")

    shorten_domain(account_id, cf_token, bridge)
    final_verify()


def final_verify():
    h = core.service("/health", base=core.TARGET_SERVICE_URL)
    s = core.service("/v1/authority", base=core.TARGET_SERVICE_URL)
    g = core.gas({"action": "service_discovery", "_app_channel": "BETA", "_app_version": "0.4.2-beta.20"})
    sa, ga = s.get("authority", {}), g.get("authority", {})
    core.assert_true(sa.get("mode") == "SERVICE_PRIMARY" and g.get("authority_mode") == "SERVICE_PRIMARY", "FINAL_MODE_MISMATCH")
    core.assert_true(int(sa.get("authority_epoch", 0)) == int(ga.get("authority_epoch", -1)), "FINAL_EPOCH_MISMATCH")
    core.assert_true(g.get("service_url") == core.TARGET_SERVICE_URL, "FINAL_URL_MISMATCH", str(g.get("service_url")))
    core.assert_true(h.get("generation") == core.SERVICE_GENERATION, "FINAL_GENERATION_MISMATCH")
    repl = h.get("replication", {})
    core.assert_true(repl.get("state") == "HEALTHY" and int(repl.get("pending_count", -1)) == 0, "FINAL_REPLICATION_NOT_HEALTHY", str(repl))
    print(f"FINAL_SERVICE_URL={core.TARGET_SERVICE_URL}")
    print(f"FINAL_AUTHORITY_EPOCH={sa.get('authority_epoch')}")
    print("S13_AUTHORITY_RECOVERY_AND_DOMAIN=PASS")


main()
