#!/usr/bin/env python3
import datetime as dt
import json
import pathlib
import sys

import install_staff_bridge_hmac as installer

proof_path = pathlib.Path('ops/staff-bridge-hmac-live-proof.json')
try:
    installer.main()
except Exception as exc:
    proof = {
        'status': 'FAIL',
        'stage': str(exc)[:180],
        'verified_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    proof_path.write_text(json.dumps(proof, indent=2) + '\n')
    print('STAFF_BRIDGE_INSTALL=FAIL ' + proof['stage'], file=sys.stderr)
    sys.exit(1)
