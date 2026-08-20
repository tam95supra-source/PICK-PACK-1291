#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'service/src/mobile_hotfix.ts'
MARK = 'S41_SERVICE_SESSION_BRIDGE_FIX'

s = TARGET.read_text(encoding='utf-8')
if MARK not in s:
    old = '''  if(!account||account.status!=="ACTIVE"||account.role!==String(payload.r)||account.verifier_hash!==String(payload.v))return apiError("SESSION_EXCHANGE_ACCOUNT_MISMATCH","AUTH",401);'''
    new = '''  // S41_SERVICE_SESSION_BRIDGE_FIX: GAS already validated the signed, active GAS session above.\n  // D1 is a replica for account verifier material and may lag a password/verifier update; requiring\n  // byte-for-byte verifier equality here can deadlock every PDA background outbox while both GAS\n  // and Service are healthy. Keep the authoritative security checks: active GAS token, ACTIVE D1\n  // account and matching role. Do not make replica verifier freshness a transport availability gate.\n  if(!account||account.status!=="ACTIVE"||account.role!==String(payload.r))return apiError("SESSION_EXCHANGE_ACCOUNT_MISMATCH","AUTH",401);'''
    if old not in s:
        raise SystemExit('S41 session exchange anchor missing')
    s = s.replace(old, new, 1)
    TARGET.write_text(s, encoding='utf-8')

s = TARGET.read_text(encoding='utf-8')
if MARK not in s:
    raise SystemExit('S41 marker missing')
if 'account.verifier_hash!==String(payload.v)' in s:
    raise SystemExit('S41 verifier equality gate survived')
if 'account.status!=="ACTIVE"||account.role!==String(payload.r)' not in s:
    raise SystemExit('S41 active/role gate missing')
if 'const discovery=await validateGasSession(gasToken,payload);' not in s:
    raise SystemExit('S41 GAS token validation missing')
print('Applied S41: GAS-validated session exchange no longer blocked by replica verifier drift')
