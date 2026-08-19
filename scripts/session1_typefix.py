from pathlib import Path

def replace(path, old, new):
    p=Path(path); s=p.read_text()
    if new in s: print('already',path); return
    if old not in s: raise SystemExit(f'anchor missing {path}: {old[:120]!r}')
    p.write_text(s.replace(old,new)); print('patched',path)

replace('service/src/index.ts',
'''  const hub=env.REALTIME_HUB.getByName(`business:${e.business_date}`);try{return await hub.broadcast(e);}catch(err){''',
'''  const hub=env.REALTIME_HUB.getByName(`business:${e.business_date}`) as unknown as {broadcast(event:typeof e):Promise<number>};try{return await hub.broadcast(e);}catch(err){''')
replace('service/src/correction.ts',
'''try{await env.REALTIME_HUB.getByName(`business:${event.business_date}`).invalidate({type:"DAY_CHANGED",business_date:event.business_date,day_revision:event.authority_seq,authority_epoch:event.authority_epoch,authority_seq:event.authority_seq});}catch{}''',
'''try{const hub=env.REALTIME_HUB.getByName(`business:${event.business_date}`) as unknown as {invalidate(message:Record<string,unknown>):Promise<number>};await hub.invalidate({type:"DAY_CHANGED",business_date:event.business_date,day_revision:event.authority_seq,authority_epoch:event.authority_epoch,authority_seq:event.authority_seq});}catch{}''')
replace('service/src/import_atomic.ts',
'''try{await env.REALTIME_HUB.getByName("master:global").invalidate({type:"MASTER_CHANGED",namespace:dataset,revision,authority_epoch:a.authority_epoch,authority_seq:a.authority_seq,service_generation:a.service_generation});}catch(e){''',
'''try{const hub=env.REALTIME_HUB.getByName("master:global") as unknown as {invalidate(message:Record<string,unknown>):Promise<number>};await hub.invalidate({type:"MASTER_CHANGED",namespace:dataset,revision,authority_epoch:a.authority_epoch,authority_seq:a.authority_seq,service_generation:a.service_generation});}catch(e){''')
replace('service/src/index.ts',
'''try{const response=await route(request,env);response.headers.set("x-request-id",requestId);console.log(JSON.stringify({level:"info",kind:"request_complete",request_id:requestId,route:path,method:request.method,status:response.status,wall_ms:Date.now()-started}));return response;}catch(e){''',
'''try{const response=await route(request,env);if(response.status!==101)response.headers.set("x-request-id",requestId);console.log(JSON.stringify({level:"info",kind:"request_complete",request_id:requestId,route:path,method:request.method,status:response.status,wall_ms:Date.now()-started}));return response;}catch(e){''')

p=Path('service/public/app.js');s=p.read_text()
if "\"':'&quot'," in s:
    s=s.replace("\"':'&quot',", "\"':'&quot;',")
if "m.type==='DELTA'" in s:
    raise SystemExit('PWA still consumes legacy DELTA websocket payload')
if "m.type==='DAY_CHANGED'" not in s or "INVALIDATION_V1" not in s:
    raise SystemExit('PWA invalidation contract missing')
p.write_text(s)
print('SESSION1_PWA_INVALIDATION_GUARD=PASS')
print('SESSION1_TYPEFIX_APPLIED')
