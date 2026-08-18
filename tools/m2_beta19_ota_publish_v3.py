#!/usr/bin/env python3
import json
import subprocess
import m2_beta19_ota_publish as publisher


def curl_service_health():
    p = subprocess.run([
        "curl", "-fsS", "--connect-timeout", "5", "--max-time", "30",
        "--retry", "3", "--retry-delay", "2", "--retry-all-errors",
        publisher.SERVICE_URL + "/health"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode != 0:
        raise RuntimeError("SERVICE_HEALTH_CURL_FAILED:" + p.stderr.decode("utf-8", "replace"))
    return json.loads(p.stdout.decode("utf-8"))


publisher.service_health = curl_service_health
publisher.main()
