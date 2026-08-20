#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S43_FOREGROUND_OUTBOX_WAKE'

s=OPS.read_text(encoding='utf-8')
if MARK not in s:
    # S33 already owns lifecycle and inserts PpForegroundGate.enter() before foregroundSync.start().
    # Patch that stable post-S33 semantic anchor instead of assuming the pre-S33 onStart body.
    anchor='''        PpForegroundGate.enter()
        if (api.token != null) foregroundSync.start()'''
    replacement='''        PpForegroundGate.enter()
        if (api.token != null) {
            // S43_FOREGROUND_OUTBOX_WAKE: if an earlier Service/session outage left durable local
            // events in WorkManager backoff, foregrounding the app wakes that SAME idempotent
            // outbox immediately. No polling and no network dependency is added to PDA hot paths.
            if (runCatching { OperationalDataStore(this).pendingMutationCount() }.getOrDefault(0) > 0) {
                M2WorkScheduler.schedule(this)
            }
            foregroundSync.start()
        }'''
    if anchor not in s:
        raise SystemExit('S43 post-S33 lifecycle anchor missing')
    s=s.replace(anchor,replacement,1)

    # Opening Sync is an explicit operator intent to reconcile. Wake the durable outbox there too;
    # foreground rendering remains local-only and never waits for this worker.
    sync='''    private fun syncScreen(){'''
    if sync not in s:
        raise SystemExit('S43 syncScreen anchor missing')
    s=s.replace(sync,'''    private fun syncScreen(){
        // S43_FOREGROUND_OUTBOX_WAKE: explicit Sync-screen wake, still background-only.
        if (runCatching { OperationalDataStore(this).pendingMutationCount() }.getOrDefault(0) > 0) M2WorkScheduler.schedule(this)''',1)
    OPS.write_text(s,encoding='utf-8')

s=OPS.read_text(encoding='utf-8')
checks=[
    (MARK in s,'foreground marker'),
    ('OperationalDataStore(this).pendingMutationCount()' in s,'pending guard'),
    ('M2WorkScheduler.schedule(this)' in s,'outbox wake'),
    ('foregroundSync.start()' in s,'foreground sync preserved'),
    ('PpForegroundGate.enter()' in s,'S33 foreground gate preserved'),
    ('private fun syncScreen(){' in s,'sync screen preserved'),
]
for ok,label in checks:
    if not ok: raise SystemExit('S43 contract missing: '+label)
if s.count('M2WorkScheduler.schedule(this)') < 2:
    raise SystemExit('S43 expected onStart + Sync-screen wake')
print('Applied S43: post-S33 foreground/Sync wake durable unresolved outbox without polling or hot-path blocking')
