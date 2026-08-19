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

# Tighten public mutation type boundary; shadow probe is SUPERADMIN-only.
replace('service/src/core.ts',
'''  if (!Number.isInteger(req.base_version) || req.base_version < 0) throw new CoreError("BASE_VERSION_INVALID", "VALIDATION", 400);
  if (req.schema_version !== 1) throw new CoreError("SCHEMA_VERSION_UNSUPPORTED", "SCHEMA", 409);''',
'''  if (!Number.isInteger(req.base_version) || req.base_version < 0) throw new CoreError("BASE_VERSION_INVALID", "VALIDATION", 400);
  if (!["ATTENDANCE_ENTER","ATTENDANCE_EXIT","RESOURCE_CHANGE","LABOR_START","LABOR_FINISH","M1_SHADOW_PROBE"].includes(String(req.event_type))) throw new CoreError("EVENT_TYPE_UNSUPPORTED","VALIDATION",400);
  if (req.schema_version !== 1) throw new CoreError("SCHEMA_VERSION_UNSUPPORTED", "SCHEMA", 409);''')
replace('service/src/core.ts',
'''  const req=normalizeMutation(input),preflightStatements:D1PreparedStatement[]=[''',
'''  const req=normalizeMutation(input);if(req.event_type==="M1_SHADOW_PROBE"&&auth.role!=="SUPERADMIN")throw new CoreError("SHADOW_PROBE_SUPERADMIN_REQUIRED","PERMISSION",403);const preflightStatements:D1PreparedStatement[]=[''')

# Import catalog/select validation and schema metadata.
replace('service/src/import_engine.ts',
'import { apiError, json, nowIso, readJsonBody, sha256Hex } from "./util";',
'import { apiError, json, nowIso, readJsonBody, sha256Hex } from "./util";\nimport { importRuleError, loadImportRules, selectValuesForDataset } from "./import_rules";')
replace('service/src/import_engine.ts',
'pack_table:{headers:["pack_table","shift","user_pack","label","available"],key:r=>`${String(r.pack_table||"").trim()}|${String(r.shift||"").trim()}`,required:["pack_table","shift"]},',
'pack_table:{headers:["pack_table","shift","user_pack","label","status_label","available"],key:r=>`${String(r.pack_table||"").trim()}|${String(r.shift||"").trim()}`,required:["pack_table","shift","status_label"]},')
replace('service/src/import_engine.ts',
'''const def=SCHEMAS[dataset];return json({ok:true,dataset,template_version:VERSION,schema_checksum:await schemaChecksum(dataset),headers:def.headers,required:def.required,upsert_policy:"MATCH_KEY_UPDATE_MISSING_INSERT_OMITTED_NO_ACTION",credential_columns_forbidden:true});''',
'''const def=SCHEMAS[dataset],rules=await loadImportRules(env.DB);return json({ok:true,dataset,template_version:VERSION,schema_checksum:await schemaChecksum(dataset),headers:def.headers,required:def.required,select_values:selectValuesForDataset(rules,dataset),upsert_policy:"MATCH_KEY_UPDATE_MISSING_INSERT_OMITTED_NO_ACTION",credential_columns_forbidden:true});''')
replace('service/src/import_engine.ts',
'''const existing=await existingMap(env.DB,meta.dataset),seen=new Set<string>(),audit:D1PreparedStatement[]=[];''',
'''const existing=await existingMap(env.DB,meta.dataset),rules=await loadImportRules(env.DB),seen=new Set<string>(),audit:D1PreparedStatement[]=[];''')
replace('service/src/import_engine.ts','let error=rowError(meta.dataset,row);','let error=rowError(meta.dataset,row)||importRuleError(rules,meta.dataset,row);')
replace('service/src/import_engine.ts',
'''db.prepare("INSERT INTO resources(resource_type,resource_id,status_label,available,metadata_json,source_row,source_checksum) VALUES('PACK_TABLE',?1,?2,?3,'{}',0,?4) ON CONFLICT(resource_type,resource_id) DO UPDATE SET status_label=excluded.status_label,available=excluded.available,source_checksum=excluded.source_checksum").bind(row.pack_table,row.label||"",row.available,checksum)''',
'''db.prepare("INSERT INTO resources(resource_type,resource_id,status_label,available,metadata_json,source_row,source_checksum) VALUES('PACK_TABLE',?1,?2,?3,'{}',0,?4) ON CONFLICT(resource_type,resource_id) DO UPDATE SET status_label=excluded.status_label,available=excluded.available,source_checksum=excluded.source_checksum").bind(row.pack_table,row.status_label||"",row.available,checksum)''')

# D1 batch is transactional: never split a logical import commit across independent batch() calls.
replace('service/src/import_engine.ts',
'''try{for(let i=0;i<stmts.length;i+=100)await env.DB.batch(stmts.slice(i,i+100));}catch(e){return apiError("IMPORT_COMMIT_CONFLICT","TRANSIENT",409,true,String(e).slice(0,180));}''',
'''try{await env.DB.batch(stmts);}catch(e){return apiError("IMPORT_COMMIT_CONFLICT","TRANSIENT",409,true,String(e).slice(0,180));}''')
replace('service/src/import_engine.ts',
'''try{for(let i=0;i<stmts.length;i+=100)await env.DB.batch(stmts.slice(i,i+100));}catch(e){return apiError("IMPORT_ROLLBACK_CONFLICT","TRANSIENT",409,true,String(e).slice(0,180));}''',
'''try{await env.DB.batch(stmts);}catch(e){return apiError("IMPORT_ROLLBACK_CONFLICT","TRANSIENT",409,true,String(e).slice(0,180));}''')

# Projection checksum is transport metadata; immutable audit before/after remains the canonical row.
replace('service/src/import_atomic.ts',
'''const after=JSON.parse(x.after_json) as Record<string,unknown>,before=x.before_json?JSON.parse(x.before_json) as Record<string,unknown>:null;after._checksum=await sha256Hex(JSON.stringify(after));const e=await buildEvent(a,auth,m.dataset,x.business_key,id,x.row_no,before,after,revision,++seq,"MASTER_IMPORT_UPSERT");events.push(e);rows.push(after);links.push({row_no:x.row_no,event_id:e.event_id});''',
'''const after=JSON.parse(x.after_json) as Record<string,unknown>,before=x.before_json?JSON.parse(x.before_json) as Record<string,unknown>:null,projection={...after,_checksum:await sha256Hex(JSON.stringify(after))};const e=await buildEvent(a,auth,m.dataset,x.business_key,id,x.row_no,before,after,revision,++seq,"MASTER_IMPORT_UPSERT");events.push(e);rows.push(projection);links.push({row_no:x.row_no,event_id:e.event_id});''')
replace('service/src/import_atomic.ts',
'''const before=JSON.parse(x.before_json!) as Record<string,unknown>,after=JSON.parse(x.after_json) as Record<string,unknown>;before._checksum=await sha256Hex(JSON.stringify(before));events.push(await buildEvent(a,auth,m.dataset,x.business_key,id,x.row_no,after,before,revision,++seq,"MASTER_IMPORT_ROLLBACK"));rows.push(before);''',
'''const before=JSON.parse(x.before_json!) as Record<string,unknown>,after=JSON.parse(x.after_json) as Record<string,unknown>,projection={...before,_checksum:await sha256Hex(JSON.stringify(before))};events.push(await buildEvent(a,auth,m.dataset,x.business_key,id,x.row_no,after,before,revision,++seq,"MASTER_IMPORT_ROLLBACK"));rows.push(projection);''')
replace('service/src/import_atomic.ts',"json_extract(value,'$.label'),CAST(json_extract(value,'$.available') AS INTEGER),'{}',0,json_extract(value,'$._checksum')","json_extract(value,'$.status_label'),CAST(json_extract(value,'$.available') AS INTEGER),'{}',0,json_extract(value,'$._checksum')")

# Canonical master changes must project back to the production Google operational replica.
replace('service/src/replication.ts','import { nowIso } from "./util";','import { nowIso } from "./util";\nimport { replicateMasterProjection } from "./master_replication";')
replace('service/src/replication.ts',
'''async function replicateOperational(db:D1Database,env:Env,token:string,events:EventRow[]):Promise<number>{
  const a=await db.prepare("SELECT scope FROM authority_state WHERE singleton_id=1").first<{scope:string}>();if(a?.scope!=="PRODUCTION")return 0;const index=await loadOperationalIndex(env,token);let n=0;''',
'''async function replicateOperational(db:D1Database,env:Env,token:string,events:EventRow[]):Promise<number>{
  const a=await db.prepare("SELECT scope FROM authority_state WHERE singleton_id=1").first<{scope:string}>();if(a?.scope!=="PRODUCTION")return 0;const master=await replicateMasterProjection(db,env,token,events),index=await loadOperationalIndex(env,token);let n=0;''')
replace('service/src/replication.ts','''  return n;
}

function retryDelaySeconds''','''  return n+master;
}

function retryDelaySeconds''')

print('SESSION1_FOLLOWUP_APPLIED')
