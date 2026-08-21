#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
s=p.read_text()
marker='S24_FCM_LOGOUT_REVOKE_APPLIED'
if marker in s:
    print('S24 FCM logout revoke already applied.')
    raise SystemExit(0)
old='''    fun clearSession() {
        synchronized(sessionLock) { sharedToken = null }
        prefs.edit().remove(KEY_TOKEN).remove(KEY_LOGIN).remove(KEY_NAME).remove(KEY_ROLE).remove(KEY_POSITION).remove(KEY_EMAIL).apply()
        m2Runtime.clear()
    }
'''
if s.count(old)!=1:
    raise SystemExit(f'S24 clearSession transformed anchor mismatch: {s.count(old)}')
new='''    fun clearSession() {
        // S24_FCM_LOGOUT_REVOKE_APPLIED: capture current Service session before clearing auth.
        M2PushRegistration.revoke(appContext)
        synchronized(sessionLock) { sharedToken = null }
        prefs.edit().remove(KEY_TOKEN).remove(KEY_LOGIN).remove(KEY_NAME).remove(KEY_ROLE).remove(KEY_POSITION).remove(KEY_EMAIL).apply()
        m2Runtime.clear()
    }
'''
p.write_text(s.replace(old,new,1))
print('Applied S24 FCM logout revoke.')
