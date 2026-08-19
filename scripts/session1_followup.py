from pathlib import Path

def replace(path, old, new):
    p=Path(path); s=p.read_text()
    if old in s:
        p.write_text(s.replace(old,new)); print('patched',path)
    elif new in s: print('already',path)
    else: raise SystemExit(f'anchor missing {path}: {old[:120]!r}')

replace('service/src/index.ts',
'import { importChunk, importCommit, importHistory, importPreview, importRollback, importSchema, importStart } from "./import_engine";',
'import { importChunk, importHistory, importPreview, importSchema, importStart } from "./import_engine";\nimport { importCommitAtomic, importRollbackAtomic } from "./import_atomic";')
replace('service/src/index.ts','return importCommit(request,env,id);','return importCommitAtomic(request,env,id);')
replace('service/src/index.ts','return importRollback(request,env,id);','return importRollbackAtomic(request,env,id);')

replace('service/src/index.ts',
'''async function realtimeTicket(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),u=new URL(request.url),date=u.searchParams.get("business_date")||"";if(!/^\\d{4}-\\d{2}-\\d{2}$/.test(date))return apiError("BUSINESS_DATE_INVALID","VALIDATION",400);
  const ticket=crypto.randomUUID(),expires=Date.now()+120_000,createdAt=nowIso();''',
'''async function realtimeTicket(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),u=new URL(request.url),scope=u.searchParams.get("scope")==="master"?"master":"day",requested=u.searchParams.get("business_date")||"",date=scope==="master"?"__MASTER__":requested;if(scope==="day"&&!/^\\d{4}-\\d{2}-\\d{2}$/.test(date))return apiError("BUSINESS_DATE_INVALID","VALIDATION",400);
  const ticket=crypto.randomUUID(),expires=Date.now()+120_000,createdAt=nowIso();''')
replace('service/src/index.ts','return json({ok:true,ticket,expires_at:expires});','return json({ok:true,ticket,expires_at:expires,scope,business_date:scope==="day"?date:null});')
replace('service/src/index.ts',
'const hub=env.REALTIME_HUB.getByName(`business:${row.business_date}`),target=new URL(request.url);',
'const hub=env.REALTIME_HUB.getByName(row.business_date==="__MASTER__"?"master:global":`business:${row.business_date}`),target=new URL(request.url);')

replace('service/src/index.ts',
'''async function bootstrapSnapshot(request:Request,env:Env):Promise<Response>{
  await requireAuth(request,env);const u=new URL(request.url),date=u.searchParams.get("business_date")||"";
  const results=await env.DB.batch([''',
'''async function bootstrapSnapshot(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),u=new URL(request.url),date=u.searchParams.get("business_date")||"";
  if(date&&!(auth.role==="SUPERADMIN"&&u.searchParams.get("client_source")==="WEB")){const allowed=await env.DB.prepare("SELECT 1 x FROM (SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT 7) WHERE business_date=?1").bind(date).first();if(!allowed)return apiError("BUSINESS_DATE_OUTSIDE_VIEW_WINDOW","PERMISSION",403);}
  const results=await env.DB.batch([''')

# D1 batch is transactional: never split a logical import commit across independent batch() calls.
replace('service/src/import_engine.ts',
'''try{for(let i=0;i<stmts.length;i+=100)await env.DB.batch(stmts.slice(i,i+100));}catch(e){return apiError("IMPORT_COMMIT_CONFLICT","TRANSIENT",409,true,String(e).slice(0,180));}''',
'''try{await env.DB.batch(stmts);}catch(e){return apiError("IMPORT_COMMIT_CONFLICT","TRANSIENT",409,true,String(e).slice(0,180));}''')
replace('service/src/import_engine.ts',
'''try{for(let i=0;i<stmts.length;i+=100)await env.DB.batch(stmts.slice(i,i+100));}catch(e){return apiError("IMPORT_ROLLBACK_CONFLICT","TRANSIENT",409,true,String(e).slice(0,180));}''',
'''try{await env.DB.batch(stmts);}catch(e){return apiError("IMPORT_ROLLBACK_CONFLICT","TRANSIENT",409,true,String(e).slice(0,180));}''')

# Projection checksum is transport metadata; immutable audit before/after remains the user-visible canonical row.
replace('service/src/import_atomic.ts',
'''const after=JSON.parse(x.after_json) as Record<string,unknown>,before=x.before_json?JSON.parse(x.before_json) as Record<string,unknown>:null;after._checksum=await sha256Hex(JSON.stringify(after));const e=await buildEvent(a,auth,m.dataset,x.business_key,id,x.row_no,before,after,revision,++seq,"MASTER_IMPORT_UPSERT");events.push(e);rows.push(after);links.push({row_no:x.row_no,event_id:e.event_id});''',
'''const after=JSON.parse(x.after_json) as Record<string,unknown>,before=x.before_json?JSON.parse(x.before_json) as Record<string,unknown>:null,projection={...after,_checksum:await sha256Hex(JSON.stringify(after))};const e=await buildEvent(a,auth,m.dataset,x.business_key,id,x.row_no,before,after,revision,++seq,"MASTER_IMPORT_UPSERT");events.push(e);rows.push(projection);links.push({row_no:x.row_no,event_id:e.event_id});''')
replace('service/src/import_atomic.ts',
'''const before=JSON.parse(x.before_json!) as Record<string,unknown>,after=JSON.parse(x.after_json) as Record<string,unknown>;before._checksum=await sha256Hex(JSON.stringify(before));events.push(await buildEvent(a,auth,m.dataset,x.business_key,id,x.row_no,after,before,revision,++seq,"MASTER_IMPORT_ROLLBACK"));rows.push(before);''',
'''const before=JSON.parse(x.before_json!) as Record<string,unknown>,after=JSON.parse(x.after_json) as Record<string,unknown>,projection={...before,_checksum:await sha256Hex(JSON.stringify(before))};events.push(await buildEvent(a,auth,m.dataset,x.business_key,id,x.row_no,after,before,revision,++seq,"MASTER_IMPORT_ROLLBACK"));rows.push(projection);''')

print('SESSION1_FOLLOWUP_APPLIED')
