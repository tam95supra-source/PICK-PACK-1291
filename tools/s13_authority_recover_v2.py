#!/usr/bin/env python3
import json
import subprocess
import sys

import s13_authority_recover as core


def curl_json_fixed(url: str, *, method="GET", payload=None, headers=None, fail=True, follow=False):
    args = ["curl", "-sS"]
    if fail:
        args.append("-f")
    if follow:
        args.append("-L")
    # Do not force -X POST when a body is present. Apps Script returns a redirect and curl must be
    # allowed to follow its normal POST->GET redirect semantics. Explicit PUT/GET remain explicit.
    if not (method == "POST" and payload is not None):
        args += ["-X", method]
    for k, v in (headers or {}).items():
        args += ["-H", f"{k}: {v}"]
    if payload is not None:
        args += ["-H", "content-type: application/json", "--data-binary", json.dumps(payload, ensure_ascii=False)]
    args.append(url)
    p = subprocess.run(args, cwd=core.ROOT, text=True, capture_output=True)
    if p.returncode and fail:
        raise RuntimeError(f"HTTP_CURL_FAILED:{url}:{p.stderr.strip()[:240]}")
    try:
        body = json.loads(p.stdout or "{}")
    except Exception:
        body = {"_raw": (p.stdout or "")[:1000]}
    return p.returncode, body


core.curl_json = curl_json_fixed
core.main()
