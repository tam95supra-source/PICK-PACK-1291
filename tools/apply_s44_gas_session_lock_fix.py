#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'google-apps-script/PICK_PACK_API.gs'
s=P.read_text(encoding='utf-8')
MARK='S44_LOGIN_SESSION_LOCK_ISOLATION'
if MARK not in s:
    old="function ppBindSession_(login,deviceId){const lock=LockService.getScriptLock();lock.waitLock(10000);try{const cur=ppActiveSession_(login);const session={session_id:(cur&&cur.device_id===deviceId&&cur.session_id)?cur.session_id:Utilities.getUuid(),device_id:deviceId,issued_at:ppNowIso_()};PropertiesService.getScriptProperties().setProperty(ppSessionKey_(login),JSON.stringify(session));return session;}finally{lock.releaseLock();}}"
    new="function ppBindSession_(login,deviceId){/* S44_LOGIN_SESSION_LOCK_ISOLATION: login/session binding must never contend with the global business Sheet lock. Same-device login reuses the active session; a different device replaces it by last-write-wins PDA semantics. */const cur=ppActiveSession_(login);const session={session_id:(cur&&cur.device_id===deviceId&&cur.session_id)?cur.session_id:Utilities.getUuid(),device_id:deviceId,issued_at:ppNowIso_()};PropertiesService.getScriptProperties().setProperty(ppSessionKey_(login),JSON.stringify(session));return session;}"
    if old not in s: raise SystemExit('S44 GAS ppBindSession anchor missing')
    s=s.replace(old,new,1)
# Publish a non-sensitive live marker so deployment acceptance can prove this exact lock model is live.
if "login_session_lock_model:'S44_LOCK_ISOLATED'" not in s:
    old="auth_session_model:'SINGLE_ACTIVE_DEVICE_V1'"
    if old not in s: raise SystemExit('S44 GAS health marker anchor missing')
    s=s.replace(old,old+",login_session_lock_model:'S44_LOCK_ISOLATED'",1)
P.write_text(s,encoding='utf-8')
o=P.read_text(encoding='utf-8')
if MARK not in o: raise SystemExit('S44 GAS marker missing')
if "login_session_lock_model:'S44_LOCK_ISOLATED'" not in o: raise SystemExit('S44 GAS live health marker missing')
start=o.find('function ppBindSession_(');end=o.find('function ppClearActiveSessionForLogin_',start);block=o[start:end]
if 'getScriptLock' in block or 'waitLock' in block or 'tryLock' in block: raise SystemExit('S44 GAS session bind still uses global ScriptLock')
if 'function ppWithLock_' not in o or 'tryLock(20000)' not in o: raise SystemExit('S44 business mutation lock was accidentally removed')
print('Applied S44 GAS: login/session bind isolated from business ScriptLock; mutation lock preserved; health marker enabled')