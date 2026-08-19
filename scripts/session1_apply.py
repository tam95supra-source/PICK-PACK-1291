from pathlib import Path


def replace(path, old, new):
    p=Path(path); s=p.read_text()
    if old in s:
        p.write_text(s.replace(old,new))
        print('patched',path)
    elif new in s:
        print('already',path)
    else:
        raise SystemExit(f'anchor missing: {path}: {old[:100]!r}')

# Việc số 0: technical replica row order must exactly match REPLICA_HEADERS.
replace('service/src/replication.ts',
'function eventValues(e:EventRow):unknown[]{return[e.event_id,e.event_type,e.entity_type,e.entity_id,e.business_date,e.authority_epoch,e.authority_seq,e.service_generation,e.base_version,e.new_version,e.actor_id,e.actor_role,e.device_id,e.occurred_at,e.committed_at,e.payload_json,e.idempotency_key,e.origin,e.schema_version,e.checksum];}',
'function eventValues(e:EventRow):unknown[]{return[e.event_id,e.event_type,e.entity_type,e.entity_id,e.business_date,e.authority_epoch,e.authority_seq,e.service_generation,e.base_version,e.new_version,e.actor_id,e.actor_role,e.device_id,e.occurred_at,e.committed_at,e.idempotency_key,e.origin,e.schema_version,e.checksum,e.payload_json];}')

replace('service/src/domain.ts',
'  schema_version: 1;\n}',
'  schema_version: 1;\n  client_source?: "PDA" | "WEB" | "FILE_IMPORT";\n}')

# Canonical payload redaction + backend time-window enforcement.
replace('service/src/core.ts',
'''function text(payload: Record<string, unknown>, key: string, max = 240): string {\n  return String(payload[key] ?? "").trim().slice(0, max);\n}\n''',
'''function text(payload: Record<string, unknown>, key: string, max = 240): string {\n  return String(payload[key] ?? "").trim().slice(0, max);\n}\n\nconst SENSITIVE_KEY=/(^|_)(token|password|verifier|secret|authorization|cookie|oauth)(_|$)/i;\nexport function sanitizeSensitive(value: unknown): unknown {\n  if(Array.isArray(value))return value.map(sanitizeSensitive);\n  if(value&&typeof value==="object"){const out:Record<string,unknown>={};for(const [k,v] of Object.entries(value as Record<string,unknown>)){if(SENSITIVE_KEY.test(k))continue;out[k]=sanitizeSensitive(v);}return out;}\n  return value;\n}\n''')
replace('service/src/core.ts',
'''    timestamp: String(req.timestamp || nowIso()),\n    payload: req.payload && typeof req.payload === "object" ? req.payload : {},\n  };''',
'''    timestamp: String(req.timestamp || nowIso()),\n    payload: sanitizeSensitive(req.payload && typeof req.payload === "object" ? req.payload : {}) as Record<string,unknown>,\n    client_source: req.client_source === "WEB" || req.client_source === "FILE_IMPORT" ? req.client_source : "PDA",\n  };''')
replace('service/src/core.ts',
'''  if(auth.role!=="SUPERADMIN")preflightStatements.push(db.prepare("SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT 2"));''',
'''  const writeWindow=auth.role==="SUPERADMIN"?(req.client_source==="WEB"?0:7):2;\n  if(writeWindow)preflightStatements.push(db.prepare("SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT ?1").bind(writeWindow));''')
replace('service/src/core.ts',
'''  if(auth.role!=="SUPERADMIN"){\n    const allowed=new Set((preflight[2]?.results??[]).map(r=>String((r as {business_date?:string}).business_date??"")));if(!allowed.has(req.business_date))throw new CoreError("BUSINESS_DATE_NOT_N_N_MINUS_1","PERMISSION",403,false,{allowed:[...allowed]});\n  }''',
'''  if(writeWindow){\n    const allowed=new Set((preflight[2]?.results??[]).map(r=>String((r as {business_date?:string}).business_date??"")));if(!allowed.has(req.business_date))throw new CoreError(auth.role==="SUPERADMIN"?"BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW":"BUSINESS_DATE_NOT_N_N_MINUS_1","PERMISSION",403,false,{allowed:[...allowed]});\n  }''')

# Legacy/PDA compatibility contract: 7 business sessions, never calendar arithmetic.
replace('service/src/entry.ts','ORDER BY sequence_no DESC LIMIT 2','ORDER BY sequence_no DESC LIMIT 7')
replace('service/src/entry.ts','M2_SERVICE_RECENT_N_N_MINUS_1','M2_SERVICE_BUSINESS_WINDOW_7')

# Fallback ingress verifies the source checksum before redacting any historical secret material.
replace('service/src/entry.ts',
'import { currentAuthority } from "./core";',
'import { currentAuthority, sanitizeSensitive } from "./core";')
replace('service/src/entry.ts',
'''  const body=await readJsonBody<{event_id:string;authority_epoch:number;authority_seq:number;service_generation:string;event:Record<string,unknown>;checksum:string}>(request);\n  const eventId=String(body.event_id||"").trim(),generation=String(body.service_generation||"").trim(),checksum=String(body.checksum||"").trim();''',
'''  const body=await readJsonBody<{event_id:string;authority_epoch:number;authority_seq:number;service_generation:string;event:Record<string,unknown>;checksum:string}>(request);\n  const eventId=String(body.event_id||"").trim(),generation=String(body.service_generation||"").trim(),checksum=String(body.checksum||"").trim();''')
replace('service/src/entry.ts',
'''  const a=await currentAuthority(env.DB);\n  const futureFallback=a.mode==="SERVICE_PRIMARY"&&body.authority_epoch===a.authority_epoch+1;''',
'''  const e=body.event as Record<string,unknown>,sourceRaw=[eventId,body.authority_epoch,body.authority_seq,generation,String(e.action||""),String(e.business_date||""),String(e.actor||""),String(e.role||""),String(e.device_id||""),String(e.occurred_at||""),String(e.payload_json||"")].join("|");\n  if(await sha256Hex(sourceRaw)!==checksum)return apiError("FALLBACK_SOURCE_CHECKSUM_MISMATCH","INTEGRITY",409);\n  let cleanPayload:unknown={};try{cleanPayload=sanitizeSensitive(JSON.parse(String(e.payload_json||"{}")));}catch{cleanPayload={};}\n  const cleanEvent={...e,payload_json:JSON.stringify(cleanPayload)},cleanJson=JSON.stringify(cleanEvent),sanitizedChecksum=await sha256Hex(cleanJson);\n  const a=await currentAuthority(env.DB);\n  const futureFallback=a.mode==="SERVICE_PRIMARY"&&body.authority_epoch===a.authority_epoch+1;''')
replace('service/src/entry.ts',
'''  await env.DB.prepare(`INSERT INTO fallback_event_inbox(event_id,authority_epoch,authority_seq,service_generation,event_json,checksum,source,ingest_status,received_at)\n    VALUES(?1,?2,?3,?4,?5,?6,'GOOGLE_FALLBACK','PENDING',?7)`).bind(eventId,body.authority_epoch,body.authority_seq,generation,JSON.stringify(body.event),checksum,nowIso()).run();''',
'''  await env.DB.prepare(`INSERT INTO fallback_event_inbox(event_id,authority_epoch,authority_seq,service_generation,event_json,checksum,source,ingest_status,received_at,source_checksum_verified,sanitized_checksum)\n    VALUES(?1,?2,?3,?4,?5,?6,'GOOGLE_FALLBACK','PENDING',?7,1,?8)`).bind(eventId,body.authority_epoch,body.authority_seq,generation,cleanJson,checksum,nowIso(),sanitizedChecksum).run();''')

# Recovery supports both old rows and new redacted/verified inbox rows.
replace('service/src/recovery.ts',
'interface InboxRow { event_id:string;authority_epoch:number;authority_seq:number;service_generation:string;event_json:string;checksum:string;ingest_status:string; }',
'interface InboxRow { event_id:string;authority_epoch:number;authority_seq:number;service_generation:string;event_json:string;checksum:string;ingest_status:string;source_checksum_verified?:number;sanitized_checksum?:string|null; }')
replace('service/src/recovery.ts',
'''async function verifyRow(row:InboxRow,e:FallbackEnvelope):Promise<void>{\n  const raw=[row.event_id,row.authority_epoch,row.authority_seq,row.service_generation,e.action,e.business_date,e.actor,e.role,e.device_id||"",e.occurred_at||"",e.payload_json].join("|");const digest=await sha256Hex(raw);if(digest!==row.checksum)throw new Error(`FALLBACK_CHECKSUM_MISMATCH:${row.event_id}`);\n}''',
'''async function verifyRow(row:InboxRow,e:FallbackEnvelope):Promise<void>{\n  if(row.source_checksum_verified===1){const digest=await sha256Hex(row.event_json);if(!row.sanitized_checksum||digest!==row.sanitized_checksum)throw new Error(`FALLBACK_SANITIZED_CHECKSUM_MISMATCH:${row.event_id}`);return;}\n  const raw=[row.event_id,row.authority_epoch,row.authority_seq,row.service_generation,e.action,e.business_date,e.actor,e.role,e.device_id||"",e.occurred_at||"",e.payload_json].join("|");const digest=await sha256Hex(raw);if(digest!==row.checksum)throw new Error(`FALLBACK_CHECKSUM_MISMATCH:${row.event_id}`);\n}''')
replace('service/src/recovery.ts',
'SELECT event_id,authority_epoch,authority_seq,service_generation,event_json,checksum,ingest_status FROM fallback_event_inbox WHERE authority_epoch=?1 ORDER BY authority_seq',
'SELECT event_id,authority_epoch,authority_seq,service_generation,event_json,checksum,ingest_status,source_checksum_verified,sanitized_checksum FROM fallback_event_inbox WHERE authority_epoch=?1 ORDER BY authority_seq')

# GAS strips auth/session material before both Service bridge payload and new fallback ledger rows.
replace('google-apps-script/SERVICE_MIGRATION_M2.gs',
'''function ppM2BridgeActor_(auth,body){return {login_id:String(auth.login_id||auth.login||''),role:String(auth.role||'USER'),display_name:String(auth.display_name||auth.login_id||''),device_id:String((body||{})._device_id||'gas-legacy')};}\nfunction ppM2BridgeMutation_(auth,body,action){''',
'''function ppM2BridgeActor_(auth,body){return {login_id:String(auth.login_id||auth.login||''),role:String(auth.role||'USER'),display_name:String(auth.display_name||auth.login_id||''),device_id:String((body||{})._device_id||'gas-legacy')};}\nfunction ppM2SanitizePayload_(value){if(Array.isArray(value))return value.map(ppM2SanitizePayload_);if(value&&typeof value==='object'){const out={};Object.keys(value).forEach(function(k){if(/(^|_)(token|password|verifier|secret|authorization|cookie|oauth)(_|$)/i.test(k))return;out[k]=ppM2SanitizePayload_(value[k]);});return out;}return value;}\nfunction ppM2BridgeMutation_(auth,body,action){''')
replace('google-apps-script/SERVICE_MIGRATION_M2.gs',
'payload:body}};',
'payload:ppM2SanitizePayload_(body)}};')
replace('google-apps-script/SERVICE_MIGRATION_M2.gs',
'''payload=JSON.stringify(body||{}),raw=[eventId,ppM2Epoch_(),seq,ppM2Generation_(),action,date,String(auth.login_id||''),String(auth.role||'USER'),String(body._device_id||''),at,payload].join('|');''',
'''payload=JSON.stringify(ppM2SanitizePayload_(body||{})),raw=[eventId,ppM2Epoch_(),seq,ppM2Generation_(),action,date,String(auth.login_id||''),String(auth.role||'USER'),String(body._device_id||''),at,payload].join('|');''')

# New Service routes: revision/delta, batch mutation, corrections, import and FCM foundation.
replace('service/src/index.ts',
'import { replicatePending } from "./replication";',
'''import { replicatePending } from "./replication";\nimport { dayDeltaV2, masterDeltaV2, syncStatusV2 } from "./sync_contract";\nimport { historicalCorrection } from "./correction";\nimport { importChunk, importCommit, importHistory, importPreview, importRollback, importSchema, importStart } from "./import_engine";\nimport { flushPushOutbox, registerPushDevice, revokePushDevice } from "./push";''')
replace('service/src/index.ts','ORDER BY sequence_no DESC LIMIT 45','ORDER BY sequence_no DESC LIMIT 7')
replace('service/src/index.ts',
'''async function legacyMutation(request:Request,env:Env):Promise<Response>{''',
'''async function mutateBatch(request:Request,env:Env):Promise<Response>{\n  const auth=await requireAuth(request,env),body=await readJsonBody<{events:CanonicalMutationRequest[]}>(request),events=Array.isArray(body.events)?body.events:[];if(!events.length||events.length>100)return apiError("MUTATION_BATCH_INVALID","VALIDATION",400);const results:Record<string,unknown>[]=[];\n  for(const input of events){const localEventId=String(input?.event_id||"");try{const result=await commitMutation(env.DB,env,auth,input),e=result.event,delivered=await broadcastEvent(env,e);results.push({local_event_id:localEventId,status:result.duplicate?"DUPLICATE":"CONFIRMED",canonical_event_id:e.event_id,authority_epoch:e.authority_epoch,authority_seq:e.authority_seq,new_version:e.new_version,error_code:null,conflict:null,realtime_delivered:delivered});}catch(err){if(err instanceof CoreError){const review=err.errorClass==="CONFLICT"||err.errorClass==="RESOURCE";results.push({local_event_id:localEventId,status:review?"REVIEW_REQUIRED":"REJECTED",canonical_event_id:null,authority_epoch:null,authority_seq:null,new_version:null,error_code:err.code,conflict:err.conflict??null,retryable:err.retryable});continue;}throw err;}}\n  return json({ok:true,results});\n}\nasync function legacyMutation(request:Request,env:Env):Promise<Response>{''')
replace('service/src/index.ts',
'''  if(p==="/v1/mutations"&&method==="POST")return mutate(request,env);''',
'''  if(p==="/v1/mutations"&&method==="POST")return mutate(request,env);\n  if(p==="/v1/mutations/batch"&&method==="POST")return mutateBatch(request,env);\n  if(p==="/v1/corrections"&&method==="POST")return historicalCorrection(request,env);''')
replace('service/src/index.ts',
'''  if(p==="/v1/sync/status"&&method==="GET")return syncStatus(request,env);''',
'''  if(p==="/v1/sync/status"&&method==="GET")return syncStatusV2(request,env);\n  if(p==="/v1/delta/day"&&method==="GET")return dayDeltaV2(request,env);\n  if(p==="/v1/delta/master"&&method==="GET")return masterDeltaV2(request,env);''')
replace('service/src/index.ts',
'''  if(p==="/v1/realtime"&&method==="GET")return realtimeConnect(request,env);''',
'''  if(p==="/v1/realtime"&&method==="GET")return realtimeConnect(request,env);\n  if(p==="/v1/push/register"&&method==="POST")return registerPushDevice(request,env);\n  if(p==="/v1/push/revoke"&&method==="POST")return revokePushDevice(request,env);\n  if(p==="/v1/import/schema"&&method==="GET")return importSchema(request,env);\n  if(p==="/v1/import/batches"&&method==="POST")return importStart(request,env);\n  if(p==="/v1/import/history"&&method==="GET")return importHistory(request,env);\n  const im=p.match(/^\\/v1\\/import\\/batches\\/([^/]+)\\/(chunks|preview|commit|rollback)$/);if(im){const id=decodeURIComponent(im[1]!),op=im[2];if(op==="chunks"&&(method==="POST"||method==="PUT"))return importChunk(request,env,id);if(op==="preview"&&method==="POST")return importPreview(request,env,id);if(op==="commit"&&method==="POST")return importCommit(request,env,id);if(op==="rollback"&&method==="POST")return importRollback(request,env,id);}\n''')
replace('service/src/index.ts',
'''  if(p==="/internal/replicate"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);return json(await replicatePending(env.DB,env));}''',
'''  if(p==="/internal/replicate"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);return json(await replicatePending(env.DB,env));}\n  if(p==="/internal/push/flush"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);return json({ok:true,...await flushPushOutbox(env.DB,env)});}''')
replace('service/src/index.ts',
'''  async fetch(request:Request,env:Env):Promise<Response>{try{return await route(request,env);}catch(e){if(e instanceof CoreError)return apiError(e.code,e.errorClass,e.status,e.retryable,undefined,e.conflict);console.log(JSON.stringify({level:"error",kind:"request_failed",path:new URL(request.url).pathname,error:String(e)}));return apiError("INTERNAL_ERROR","INTERNAL",500,true);}},\n  async scheduled(_controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{ctx.waitUntil(replicatePending(env.DB,env).then(()=>undefined).catch(e=>console.log(JSON.stringify({level:"error",kind:"scheduled_replication_failed",error:String(e)}))));},''',
'''  async fetch(request:Request,env:Env):Promise<Response>{const started=Date.now(),requestId=request.headers.get("x-request-id")?.slice(0,100)||crypto.randomUUID(),path=new URL(request.url).pathname;try{const response=await route(request,env);response.headers.set("x-request-id",requestId);console.log(JSON.stringify({level:"info",kind:"request_complete",request_id:requestId,route:path,method:request.method,status:response.status,wall_ms:Date.now()-started}));return response;}catch(e){if(e instanceof CoreError)return apiError(e.code,e.errorClass,e.status,e.retryable,undefined,e.conflict);console.log(JSON.stringify({level:"error",kind:"request_failed",request_id:requestId,route:path,method:request.method,wall_ms:Date.now()-started,error_class:"INTERNAL",error:String(e).slice(0,240)}));return apiError("INTERNAL_ERROR","INTERNAL",500,true);}},\n  async scheduled(_controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{ctx.waitUntil(Promise.all([replicatePending(env.DB,env),flushPushOutbox(env.DB,env)]).then(()=>undefined).catch(e=>console.log(JSON.stringify({level:"error",kind:"scheduled_background_failed",error:String(e).slice(0,240)}))));},''')
replace('service/src/index.ts',
'''realtime:"DURABLE_OBJECT_WEBSOCKET_HIBERNATION",delta:true,offline_outbox:true,legacy_adapter:true,''',
'''realtime:"DURABLE_OBJECT_WEBSOCKET_HIBERNATION",realtime_protocol:"INVALIDATION_V1",delta:true,revision_namespaces:true,business_window:7,mutation_batch:true,offline_outbox:true,fcm_wake:true,import_engine:true,historical_corrections:true,legacy_adapter:true,''')

# Web shell remains local-first but identifies WEB source; labor navigation/content is role fenced.
replace('service/public/app.js',
'''device_id:state.device,schema_version:1},exclusive}}''',
'''device_id:state.device,schema_version:1,client_source:'WEB'},exclusive}}''')
replace('service/public/app.js',
'''function businessView(){const shifts=catalog('VÀO - RA TRONG CA_Ca');return `<section class="panel">''',
'''function businessView(){const shifts=catalog('VÀO - RA TRONG CA_Ca'),laborAllowed=state.account?.role!=='USER';return `<section class="panel">''')
replace('service/public/app.js',
'''</div><div class="card"><h3>Công nhật</h3><input id="laborMnv"''',
'''</div>${laborAllowed?`<div class="card"><h3>Công nhật</h3><input id="laborMnv"''')
replace('service/public/app.js',
'''<button class="primary" id="laborStart">BẮT ĐẦU</button></div></section>`}''',
'''<button class="primary" id="laborStart">BẮT ĐẦU</button></div>`:''}</section>`}''')

print('SESSION1_PATCH_APPLIED')
