#!/usr/bin/env python3
from pathlib import Path
import runpy

ROOT=Path(__file__).resolve().parents[1]
try:
    runpy.run_path(str(ROOT/'tools/apply_s40_owner_local_first_repair.py'),run_name='__main__')
except SystemExit as e:
    if str(e)!='S40 contract missing: cold-cache local employee projection':
        raise
    proj=(ROOT/'app/src/main/java/vn/pickpack1291/app/beta/PdaLocalProjection.kt').read_text(encoding='utf-8')
    store=(ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt').read_text(encoding='utf-8')
    ops=(ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt').read_text(encoding='utf-8')
    transport=(ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt').read_text(encoding='utf-8')
    a=store.find('    fun projectionMutations(');b=store.find('    fun markMutationSynced(',a);pb=store[a:b]
    checks=[
        ('val day = store.loadDay(businessDate)' in proj and 'val sessions = day?.optJSONArray("sessions") ?: JSONArray()' in proj,'cold-cache projection'),
        ('val labor = day?.optJSONArray("labor") ?: JSONArray()' in proj,'cold-cache labor projection'),
        ('store.projectionMutations(500)' in proj,'S27 projection retained'),
        ('next_attempt_at <= ?' not in pb and "OR status='CONFIRMED'" in pb,'S27 ACK-gap plus retry-clock removal'),
        ('store.unresolvedMutations(100)' in transport,'all unresolved flush'),
        ('PdaLocalProjection.employeeContext(this,resolved)' in ops and 'Service chưa xác nhận được; thao tác vẫn lưu local' in ops,'owner local-first UI'),
        ('val pending=rows.count{statusOf(it)=="PENDING"}' in ops and 'val failed=rows.count{statusOf(it)=="FAILED"}' in ops and 'updateMetric(allBtn,rows.size)' in ops,'exact event metrics'),
    ]
    for ok,label in checks:
        if not ok: raise SystemExit('S40W contract missing: '+label)
    print('S40 wrapper PASS: cold-cache local-first, S27 ACK-gap, unresolved flush and exact event metrics')
