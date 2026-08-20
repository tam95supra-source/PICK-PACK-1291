#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
WORKER=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2OutboxWorker.kt'
TRANSPORT=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt'
MARK='S43_FOREGROUND_OUTBOX_WAKE'

# 1) Add an in-process, non-blocking immediate flush lane. SQLite commit still happens first;
# WorkManager remains the durable retry backup if this immediate attempt cannot finish.
w=WORKER.read_text(encoding='utf-8')
if 'object M2ImmediateOutbox' not in w:
    if 'import java.util.concurrent.Executors' not in w:
        imp='import java.util.concurrent.TimeUnit\n'
        if imp not in w: raise SystemExit('S43 Worker import anchor missing')
        w=w.replace(imp,imp+'import java.util.concurrent.Executors\n',1)
    anchor='object M2WorkScheduler {'
    if anchor not in w: raise SystemExit('S43 WorkScheduler anchor missing')
    immediate=r'''/**
 * S43_FOREGROUND_OUTBOX_WAKE: fast background lane for a foreground PDA action.
 * The business event is already durable in SQLite before kick() is called. Network work never runs
 * on the UI thread. WorkManager remains the retry/durability path when this immediate attempt fails.
 */
object M2ImmediateOutbox {
    private val running = AtomicBoolean(false)
    private val executor = Executors.newSingleThreadExecutor()

    fun kick(context: Context) {
        val app = context.applicationContext
        if (!running.compareAndSet(false, true)) return
        executor.execute {
            try {
                if (!M2ServiceTransport(app).flushOutbox()) M2WorkScheduler.schedule(app)
            } catch (_: Throwable) {
                M2WorkScheduler.schedule(app)
            } finally {
                running.set(false)
            }
        }
    }
}

'''
    w=w.replace(anchor,immediate+anchor,1)
    WORKER.write_text(w,encoding='utf-8')

# 2) Every operational event: durable SQLite enqueue first, WorkManager backup second, immediate
# background flush third. This does not change the 202/local-first UI result.
t=TRANSPORT.read_text(encoding='utf-8')
operational='''        store.enqueueMutation(request, exclusive)
        M2WorkScheduler.schedule(app)'''
if 'M2ImmediateOutbox.kick(app)' not in t:
    if operational not in t: raise SystemExit('S43 operational enqueue anchor missing')
    t=t.replace(operational,operational+'\n        M2ImmediateOutbox.kick(app)',1)
# Admin audit uses the same durable outbox and receives the same immediate/background treatment.
audit='''        store.enqueueMutation(body,false)
        M2WorkScheduler.schedule(app)'''
if audit in t and audit+'\n        M2ImmediateOutbox.kick(app)' not in t:
    t=t.replace(audit,audit+'\n        M2ImmediateOutbox.kick(app)',1)
TRANSPORT.write_text(t,encoding='utf-8')

# 3) Foreground/recovery wake. S33 already owns lifecycle and inserts PpForegroundGate.enter().
s=OPS.read_text(encoding='utf-8')
if MARK not in s:
    anchor='''        PpForegroundGate.enter()
        if (api.token != null) foregroundSync.start()'''
    replacement='''        PpForegroundGate.enter()
        if (api.token != null) {
            // S43_FOREGROUND_OUTBOX_WAKE: old unresolved events are flushed immediately on a
            // background executor after the activity becomes visible. No polling and no UI wait.
            if (runCatching { OperationalDataStore(this).pendingMutationCount() }.getOrDefault(0) > 0) {
                M2ImmediateOutbox.kick(this)
            }
            foregroundSync.start()
        }'''
    if anchor not in s: raise SystemExit('S43 post-S33 lifecycle anchor missing')
    s=s.replace(anchor,replacement,1)

    sync='''    private fun syncScreen(){'''
    if sync not in s: raise SystemExit('S43 syncScreen anchor missing')
    s=s.replace(sync,'''    private fun syncScreen(){
        // S43_FOREGROUND_OUTBOX_WAKE: explicit Sync-screen wake, still background/non-blocking.
        if (runCatching { OperationalDataStore(this).pendingMutationCount() }.getOrDefault(0) > 0) M2ImmediateOutbox.kick(this)''',1)
    OPS.write_text(s,encoding='utf-8')

# Release-critical contract checks.
s=OPS.read_text(encoding='utf-8');w=WORKER.read_text(encoding='utf-8');t=TRANSPORT.read_text(encoding='utf-8')
checks=[
    (MARK in s,'foreground marker'),
    ('OperationalDataStore(this).pendingMutationCount()' in s,'pending guard'),
    (s.count('M2ImmediateOutbox.kick(this)')>=2,'onStart + Sync immediate wake'),
    ('foregroundSync.start()' in s,'foreground sync preserved'),
    ('PpForegroundGate.enter()' in s,'S33 foreground gate preserved'),
    ('object M2ImmediateOutbox' in w and 'Executors.newSingleThreadExecutor()' in w,'immediate executor'),
    ('M2ServiceTransport(app).flushOutbox()' in w,'immediate flush'),
    ('M2WorkScheduler.schedule(app)' in w,'WorkManager retry backup'),
    ('store.enqueueMutation(request, exclusive)' in t and 'M2ImmediateOutbox.kick(app)' in t,'SQLite-first operational immediate kick'),
]
for ok,label in checks:
    if not ok: raise SystemExit('S43 contract missing: '+label)
print('Applied S43: SQLite-first + immediate background Service flush + WorkManager retry, foreground recovery wake, no polling')
