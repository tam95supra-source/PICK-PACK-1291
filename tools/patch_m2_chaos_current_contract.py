from pathlib import Path

TARGET = Path("service/scripts/m2-chaos.mjs")
text = TARGET.read_text(encoding="utf-8")

replacements = [
    (
        "function nextDelta(ws){return new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(new Error('WS_DELTA_TIMEOUT')),5000);const fn=e=>{let j;try{j=JSON.parse(String(e.data))}catch{return}if(j.type==='DELTA'){clearTimeout(t);ws.removeEventListener('message',fn);resolve(j);}};ws.addEventListener('message',fn);});}",
        "function nextInvalidation(ws){return new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(new Error('WS_INVALIDATION_TIMEOUT')),5000);const fn=e=>{let j;try{j=JSON.parse(String(e.data))}catch{return}if(j.type==='DAY_CHANGED'){clearTimeout(t);ws.removeEventListener('message',fn);resolve(j);}};ws.addEventListener('message',fn);});}",
    ),
    (
        "expect('14 45d manifest contains revisions',sync.json.day_revisions&&sync.json.day_revisions['2026-08-19']>=1);",
        "expect('14 sync manifest contains current-day revision',sync.json.day_revisions&&sync.json.day_revisions['2026-08-19']>=1);",
    ),
    (
        "const oldAdmin=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'old-admin',eventDate:'2026-08-17'})});expect('17 admin n-2 rejected',oldAdmin.status===403&&oldAdmin.json.error?.code==='BUSINESS_DATE_NOT_N_N_MINUS_1',JSON.stringify(oldAdmin.json));",
        "const oldAdmin=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'old-admin',eventType:'ATTENDANCE_ENTER',entityType:'ATTENDANCE_SESSION',entityId:'old-admin-session',eventDate:'2026-08-17',payload:{mnv:'E004',shift:'Ca 1',work_choice:'KHONG'},device:'admin-device-2'})});expect('17 admin n-2 rejected',oldAdmin.status===403&&oldAdmin.json.error?.code==='BUSINESS_DATE_NOT_N_N_MINUS_1',JSON.stringify(oldAdmin.json));",
    ),
    (
        "const nMinus1=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'nminus1',eventDate:'2026-08-18',device:'admin-device-2'})});expect('19 admin n-1 allowed',nMinus1.status===201,nMinus1.status);",
        "const nMinus1=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'nminus1',eventType:'ATTENDANCE_ENTER',entityType:'ATTENDANCE_SESSION',entityId:'nminus1-session',eventDate:'2026-08-18',payload:{mnv:'E004',shift:'Ca 1',work_choice:'KHONG'},device:'admin-device-2'})});expect('19 admin n-1 allowed',nMinus1.status===201,nMinus1.status);",
    ),
    (
        "const genBad=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'gen-bad',generation:'stale-generation',device:'admin-device-2'})});expect('32 stale service generation rejected',genBad.status===409&&genBad.json.error?.code==='SERVICE_GENERATION_STALE',JSON.stringify(genBad.json));",
        "const genBad=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'gen-bad',eventType:'ATTENDANCE_ENTER',entityType:'ATTENDANCE_SESSION',entityId:'gen-bad-session',generation:'stale-generation',payload:{mnv:'E006',shift:'Ca 1',work_choice:'KHONG'},device:'admin-device-2'})});expect('32 stale service generation rejected',genBad.status===409&&genBad.json.error?.code==='SERVICE_GENERATION_STALE',JSON.stringify(genBad.json));",
    ),
    (
        "const epochBad=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'epoch-bad',epoch:99,device:'admin-device-2'})});expect('33 stale authority epoch rejected',epochBad.status===409&&epochBad.json.error?.code==='AUTHORITY_EPOCH_STALE',JSON.stringify(epochBad.json));",
        "const epochBad=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'epoch-bad',eventType:'ATTENDANCE_ENTER',entityType:'ATTENDANCE_SESSION',entityId:'epoch-bad-session',epoch:99,payload:{mnv:'E006',shift:'Ca 1',work_choice:'KHONG'},device:'admin-device-2'})});expect('33 stale authority epoch rejected',epochBad.status===409&&epochBad.json.error?.code==='AUTHORITY_EPOCH_STALE',JSON.stringify(epochBad.json));",
    ),
    (
        "const wsA=await openWs(ta.json.ticket),wsS=await openWs(ts.json.ticket),pA=nextDelta(wsA),pS=nextDelta(wsS);const rt=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'realtime-probe',device:'admin-device-2'})});expect('37 realtime trigger mutation committed',rt.status===201);const [dA,dS]=await Promise.all([pA,pS]);expect('38 realtime push reaches two clients',dA.event?.event_id==='realtime-probe'&&dS.event?.event_id==='realtime-probe');wsA.close();wsS.close();",
        "const wsA=await openWs(ta.json.ticket),wsS=await openWs(ts.json.ticket),pA=nextInvalidation(wsA),pS=nextInvalidation(wsS);const rt=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'realtime-probe',eventType:'ATTENDANCE_ENTER',entityType:'ATTENDANCE_SESSION',entityId:'realtime-probe-session',payload:{mnv:'E004',shift:'Ca 1',work_choice:'KHONG'},device:'admin-device-2'})});expect('37 realtime trigger mutation committed',rt.status===201);const [dA,dS]=await Promise.all([pA,pS]);expect('38 INVALIDATION_V1 reaches two clients',dA.type==='DAY_CHANGED'&&dS.type==='DAY_CHANGED'&&dA.event_id==='realtime-probe'&&dS.event_id==='realtime-probe');wsA.close();wsS.close();",
    ),
    (
        "const oldEpochAfter=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'after-failback-old-epoch',epoch:1,device:'admin-device-2'})});expect('47 pre-failback epoch fenced',oldEpochAfter.status===409&&oldEpochAfter.json.error?.code==='AUTHORITY_EPOCH_STALE',JSON.stringify(oldEpochAfter.json));",
        "const oldEpochAfter=await http('/v1/mutations',{method:'POST',token:admin,body:mutation({eventId:'after-failback-old-epoch',eventType:'ATTENDANCE_ENTER',entityType:'ATTENDANCE_SESSION',entityId:'after-failback-old-epoch-session',epoch:1,payload:{mnv:'E006',shift:'Ca 1',work_choice:'KHONG'},device:'admin-device-2'})});expect('47 pre-failback epoch fenced',oldEpochAfter.status===409&&oldEpochAfter.json.error?.code==='AUTHORITY_EPOCH_STALE',JSON.stringify(oldEpochAfter.json));",
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one chaos-contract marker, found {count}: {old[:100]}")
    text = text.replace(old, new)

TARGET.write_text(text, encoding="utf-8")
print(f"Patched {len(replacements)} current-contract assertions in {TARGET}")
