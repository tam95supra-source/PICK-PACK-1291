import { authenticate, createChallenge, createSession, internalAuthorized, logout } from "./auth";
import { bootstrapFromGoogle } from "./bootstrap";
import { commitMutation, CoreError, currentAuthority, delta, transitionAuthority } from "./core";
import { commitLegacyMutation, type LegacyMutationInput } from "./legacy";
import { replicatePending } from "./replication";
import { dayDeltaV2, masterDeltaV2, syncStatusV2 } from "./sync_contract";
import { historicalCorrection } from "./correction";
import { importChunk, importHistory, importPreview, importSchema, importStart } from "./import_engine";
import { importCommitAtomic, importRollbackAtomic } from "./import_atomic";
import { flushPushOutbox, registerPushDevice, revokePushDevice } from "./push";
import { RealtimeHub } from "./realtime";
import { apiError, constantTimeEqual, json, nowIso, readJsonBody, sha256Hex } from "./util";
import type { AuthContext, CanonicalMutationRequest } from "./domain";

export { RealtimeHub };

interface StatusRow {
  business_date:string|null; sequence_no:number|null;
  authority_epoch:number; authority_seq:number; authority_mode:string; authority_scope:string; authority_generation:string; authority_updated_at:string;
  target_kind:string|null; target_identity:string|null; replication_schema_version:number|null; replication_state:string|null; checkpoint:string|null;
  replication_pending_count:number|null; actual_pending_count:number|null; retry_count:number|null; last_attempt_at:string|null; last_success_at:string|null;
  last_error_class:string|null; last_error:string|null; replication_updated_at:string|null;
}

function statusParts(row:StatusRow){
  const authority={authority_epoch:row.authority_epoch,authority_seq:row.authority_seq,mode:row.authority_mode,scope:row.authority_scope,service_generation:row.authority_generation,updated_at:row.authority_updated_at};
  const replication={target_kind:row.target_kind,target_identity:row.target_identity,schema_version:row.replication_schema_version,state:row.replication_state,checkpoint:row.checkpoint,pending_count:Number(row.actual_pending_count??0),retry_count:Number(row.retry_count??0),last_attempt_at:row.last_attempt_at,last_success_at:row.last_success_at,last_error_class:row.last_error_class,last_error:row.last_error,updated_at:row.replication_updated_at};
  return{authority,replication};
}

async function ensureConfiguredGeneration(env:Env):Promise<void>{
  const a=await env.DB.prepare("SELECT service_generation FROM authority_state WHERE singleton_id=1").first<{service_generation:string}>();
  if(a?.service_generation==="UNCONFIGURED")await env.DB.prepare("UPDATE authority_state SET service_generation=?1,updated_at=?2 WHERE singleton_id=1 AND service_generation='UNCONFIGURED'").bind(env.SERVICE_GENERATION,nowIso()).run();
}
async function requireAuth(request:Request,env:Env):Promise<AuthContext>{const a=await authenticate(env.DB,env,request);if(!a)throw new CoreError("UNAUTHORIZED","AUTH",401);return a;}
async function gasBridgeAuthorized(request:Request,env:Env):Promise<boolean>{const supplied=request.headers.get("x-gas-bridge-secret")||"";if(!supplied)return false;return constantTimeEqual(await sha256Hex(supplied),await sha256Hex(env.GAS_BRIDGE_SHARED_SECRET));}
function eventPublic(e:Record<string,unknown>):Record<string,unknown>{return e;}

async function broadcastEvent(env:Env,e:{event_id:string;event_type:string;entity_type:string;entity_id:string;business_date:string;authority_epoch:number;authority_seq:number;service_generation:string;new_version:number}):Promise<number>{
  const hub=env.REALTIME_HUB.getByName(`business:${e.business_date}`) as unknown as {broadcast(event:typeof e):Promise<number>};try{return await hub.broadcast(e);}catch(err){console.log(JSON.stringify({level:"warn",kind:"realtime_broadcast_failed",event_id:e.event_id,error:String(err)}));return 0;}
}

async function healthSnapshot(env:Env):Promise<Response>{
  const q=`SELECT a.authority_epoch,a.authority_seq,a.mode AS authority_mode,a.scope AS authority_scope,a.service_generation AS authority_generation,a.updated_at AS authority_updated_at,
    r.target_kind,r.target_identity,r.schema_version AS replication_schema_version,r.state AS replication_state,r.checkpoint,r.pending_count AS replication_pending_count,r.retry_count,r.last_attempt_at,r.last_success_at,r.last_error_class,r.last_error,r.updated_at AS replication_updated_at,
    (SELECT COUNT(*) FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')) AS actual_pending_count,
    NULL AS business_date,NULL AS sequence_no
    FROM authority_state a LEFT JOIN replication_status r ON r.singleton_id=1 WHERE a.singleton_id=1`;
  const result=await env.DB.prepare(q).first<StatusRow>();if(!result)throw new CoreError("AUTHORITY_STATE_MISSING","INTEGRITY",503,false);
  if(result.authority_generation==="UNCONFIGURED"){
    const at=nowIso();await env.DB.prepare("UPDATE authority_state SET service_generation=?1,updated_at=?2 WHERE singleton_id=1 AND service_generation='UNCONFIGURED'").bind(env.SERVICE_GENERATION,at).run();result.authority_generation=env.SERVICE_GENERATION;result.authority_updated_at=at;
  }
  const {authority,replication}=statusParts(result);return json({ok:true,service:"pick-pack-1291-service",environment:result.authority_scope==="STAGING_SHADOW"?"staging-shadow":"production",generation:env.SERVICE_GENERATION,authority,replication});
}

async function realtimeTicket(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),u=new URL(request.url),scope=u.searchParams.get("scope")==="master"?"master":"day",requested=u.searchParams.get("business_date")||"",date=scope==="master"?"__MASTER__":requested;if(scope==="day"&&!/^\d{4}-\d{2}-\d{2}$/.test(date))return apiError("BUSINESS_DATE_INVALID","VALIDATION",400);
  const ticket=crypto.randomUUID(),expires=Date.now()+120_000,createdAt=nowIso();
  await env.DB.batch([
    env.DB.prepare("DELETE FROM realtime_tickets WHERE expires_at<?1").bind(Date.now()),
    env.DB.prepare("INSERT INTO realtime_tickets(ticket_id,login_id,device_id,business_date,expires_at,created_at) VALUES(?1,?2,?3,?4,?5,?6)").bind(ticket,auth.login_id,auth.device_id,date,expires,createdAt),
  ]);
  return json({ok:true,ticket,expires_at:expires,scope,business_date:scope==="day"?date:null});
}
async function realtimeConnect(request:Request,env:Env):Promise<Response>{
  if(request.headers.get("Upgrade")!=="websocket")return apiError("WEBSOCKET_REQUIRED","VALIDATION",426);
  const u=new URL(request.url),ticket=u.searchParams.get("ticket")||"";const row=await env.DB.prepare("SELECT ticket_id,login_id,device_id,business_date,expires_at FROM realtime_tickets WHERE ticket_id=?1").bind(ticket).first<{ticket_id:string;login_id:string;device_id:string;business_date:string;expires_at:number}>();
  if(!row||row.expires_at<Date.now())return apiError("REALTIME_TICKET_INVALID","AUTH",401);await env.DB.prepare("DELETE FROM realtime_tickets WHERE ticket_id=?1").bind(ticket).run();
  const hub=env.REALTIME_HUB.getByName(row.business_date==="__MASTER__"?"master:global":`business:${row.business_date}`),target=new URL(request.url);target.searchParams.set("device_id",row.device_id);target.searchParams.set("login_id",row.login_id);return hub.fetch(new Request(target,request));
}

async function bootstrapSnapshot(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),u=new URL(request.url),date=u.searchParams.get("business_date")||"";
  if(date&&!(auth.role==="SUPERADMIN"&&u.searchParams.get("client_source")==="WEB")){const allowed=await env.DB.prepare("SELECT 1 x FROM (SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT 7) WHERE business_date=?1").bind(date).first();if(!allowed)return apiError("BUSINESS_DATE_OUTSIDE_VIEW_WINDOW","PERMISSION",403);}
  const results=await env.DB.batch([
    env.DB.prepare("SELECT mnv,full_name,phone,main_position,supplier,department,site,warehouse,start_date,note FROM employees ORDER BY mnv"),
    env.DB.prepare("SELECT resource_type,resource_id,status_label,available,metadata_json FROM resources ORDER BY resource_type,resource_id"),
    env.DB.prepare("SELECT namespace,ordinal,value FROM catalog_values ORDER BY namespace,ordinal"),
    date?env.DB.prepare("SELECT * FROM attendance_sessions WHERE business_date=?1 ORDER BY mnv").bind(date):env.DB.prepare("SELECT * FROM attendance_sessions WHERE 0"),
    date?env.DB.prepare("SELECT * FROM labor_sessions WHERE business_date=?1 ORDER BY mnv,start_at").bind(date):env.DB.prepare("SELECT * FROM labor_sessions WHERE 0"),
    env.DB.prepare("SELECT authority_epoch,authority_seq,mode,scope,service_generation,updated_at FROM authority_state WHERE singleton_id=1"),
  ]);
  const authority=results[5]?.results?.[0];if(!authority)throw new CoreError("AUTHORITY_STATE_MISSING","INTEGRITY",503,false);
  return json({ok:true,authority,employees:results[0]?.results??[],resources:results[1]?.results??[],catalogs:results[2]?.results??[],attendance:results[3]?.results??[],labor:results[4]?.results??[]});
}
async function syncStatus(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),now=nowIso(),cutoff=new Date(Date.now()-60_000).toISOString();
  const q=`WITH recent AS (SELECT business_date,sequence_no FROM business_dates ORDER BY sequence_no DESC LIMIT 7)
    SELECT recent.business_date,recent.sequence_no,
      a.authority_epoch,a.authority_seq,a.mode AS authority_mode,a.scope AS authority_scope,a.service_generation AS authority_generation,a.updated_at AS authority_updated_at,
      r.target_kind,r.target_identity,r.schema_version AS replication_schema_version,r.state AS replication_state,r.checkpoint,r.pending_count AS replication_pending_count,r.retry_count,r.last_attempt_at,r.last_success_at,r.last_error_class,r.last_error,r.updated_at AS replication_updated_at,
      (SELECT COUNT(*) FROM sheet_replication_outbox WHERE status IN ('PENDING','RETRY','INFLIGHT')) AS actual_pending_count
    FROM authority_state a CROSS JOIN recent LEFT JOIN replication_status r ON r.singleton_id=1 WHERE a.singleton_id=1 ORDER BY recent.sequence_no DESC`;
  const heartbeat=`INSERT INTO client_devices(device_id,login_id,platform,app_version,channel,authority_epoch,authority_seq,service_generation,last_seen_at,last_online_at,metadata_json)
    SELECT ?1,?2,'ANDROID','UNKNOWN','UNKNOWN',a.authority_epoch,a.authority_seq,a.service_generation,?3,?3,'{}' FROM authority_state a WHERE a.singleton_id=1
    ON CONFLICT(device_id) DO UPDATE SET login_id=excluded.login_id,authority_epoch=excluded.authority_epoch,authority_seq=excluded.authority_seq,service_generation=excluded.service_generation,last_seen_at=excluded.last_seen_at,last_online_at=excluded.last_online_at
    WHERE client_devices.last_seen_at<?4`;
  const results=await env.DB.batch([env.DB.prepare(q),env.DB.prepare(heartbeat).bind(auth.device_id,auth.login_id,now,cutoff)]),rows=(results[0]?.results??[]) as unknown as StatusRow[],first=rows[0];
  if(!first)throw new CoreError("AUTHORITY_STATE_MISSING","INTEGRITY",503,false);const {authority,replication}=statusParts(first),dates=rows.map(r=>({business_date:r.business_date,sequence_no:r.sequence_no}));
  return json({ok:true,authority,server_seq:first.authority_seq,service_generation:first.authority_generation,business_dates:dates,replication,realtime:true,delta_endpoint:"/v1/delta",ws_endpoint:"/v1/realtime"});
}

async function mutate(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),body=await readJsonBody<CanonicalMutationRequest>(request),result=await commitMutation(env.DB,env,auth,body),e=result.event;
  const delivered=await broadcastEvent(env,{event_id:e.event_id,event_type:e.event_type,entity_type:e.entity_type,entity_id:e.entity_id,business_date:e.business_date,authority_epoch:e.authority_epoch,authority_seq:e.authority_seq,service_generation:e.service_generation,new_version:e.new_version});
  return json({ok:true,duplicate:result.duplicate,event:eventPublic(e as unknown as Record<string,unknown>),realtime_delivered:delivered},result.duplicate?200:201);
}
async function mutateBatch(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),body=await readJsonBody<{events:CanonicalMutationRequest[]}>(request),events=Array.isArray(body.events)?body.events:[];if(!events.length||events.length>100)return apiError("MUTATION_BATCH_INVALID","VALIDATION",400);const results:Record<string,unknown>[]=[];
  for(const input of events){const localEventId=String(input?.event_id||"");try{const result=await commitMutation(env.DB,env,auth,input),e=result.event,delivered=await broadcastEvent(env,e);results.push({local_event_id:localEventId,status:result.duplicate?"DUPLICATE":"CONFIRMED",canonical_event_id:e.event_id,authority_epoch:e.authority_epoch,authority_seq:e.authority_seq,new_version:e.new_version,error_code:null,conflict:null,realtime_delivered:delivered});}catch(err){if(err instanceof CoreError){const review=err.errorClass==="CONFLICT"||err.errorClass==="RESOURCE";results.push({local_event_id:localEventId,status:review?"REVIEW_REQUIRED":"REJECTED",canonical_event_id:null,authority_epoch:null,authority_seq:null,new_version:null,error_code:err.code,conflict:err.conflict??null,retryable:err.retryable});continue;}throw err;}}
  return json({ok:true,results});
}
async function legacyMutation(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),input=await readJsonBody<LegacyMutationInput>(request),result=await commitLegacyMutation(env.DB,env,auth,input),e=result.event as {event_id:string;event_type:string;entity_type:string;entity_id:string;business_date:string;authority_epoch:number;authority_seq:number;service_generation:string;new_version:number};
  const delivered=await broadcastEvent(env,e);return json({...result,realtime_delivered:delivered},result.duplicate?200:201);
}
async function legacyMutationBatch(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),body=await readJsonBody<{events:LegacyMutationInput[]}>(request),events=Array.isArray(body.events)?body.events:[];
  if(!events.length||events.length>100)return apiError("LEGACY_MUTATION_BATCH_INVALID","VALIDATION",400);
  const results:Record<string,unknown>[]=[];
  for(const input of events){const localEventId=String(input?.event_id||"");try{
    const result=await commitLegacyMutation(env.DB,env,auth,input),e=result.event as {event_id:string;event_type:string;entity_type:string;entity_id:string;business_date:string;authority_epoch:number;authority_seq:number;service_generation:string;new_version:number},delivered=await broadcastEvent(env,e);
    results.push({local_event_id:localEventId,status:result.duplicate?"DUPLICATE":"CONFIRMED",canonical_event_id:e.event_id,authority_epoch:e.authority_epoch,authority_seq:e.authority_seq,new_version:e.new_version,error_code:null,conflict:null,realtime_delivered:delivered});
  }catch(err){if(err instanceof CoreError){const review=err.errorClass==="CONFLICT"||err.errorClass==="RESOURCE";results.push({local_event_id:localEventId,status:review?"REVIEW_REQUIRED":"REJECTED",canonical_event_id:null,authority_epoch:null,authority_seq:null,new_version:null,error_code:err.code,conflict:err.conflict??null,retryable:err.retryable});continue;}throw err;}}
  return json({ok:true,results});
}
async function gasLegacyBridge(request:Request,env:Env):Promise<Response>{
  if(!await gasBridgeAuthorized(request,env))return apiError("GAS_BRIDGE_UNAUTHORIZED","AUTH",401);
  const body=await readJsonBody<{actor:{login_id:string;role:"SUPERADMIN"|"ADMIN"|"USER";display_name?:string;device_id?:string};mutation:LegacyMutationInput}>(request),actor=body.actor;
  if(!actor?.login_id||!["SUPERADMIN","ADMIN","USER"].includes(actor.role))return apiError("GAS_BRIDGE_ACTOR_INVALID","VALIDATION",400);
  const auth:AuthContext={login_id:actor.login_id,role:actor.role,display_name:actor.display_name||actor.login_id,device_id:actor.device_id||body.mutation.device_id||"gas-legacy",session_id:"GAS_BRIDGE",verifier_hash:"GAS_BRIDGE"};
  const result=await commitLegacyMutation(env.DB,env,auth,body.mutation),e=result.event as {event_id:string;event_type:string;entity_type:string;entity_id:string;business_date:string;authority_epoch:number;authority_seq:number;service_generation:string;new_version:number};
  const delivered=await broadcastEvent(env,e);return json({...result,realtime_delivered:delivered},result.duplicate?200:201);
}

async function transitionWithAudit(env:Env,input:{expected_epoch:number;mode:"SERVICE_PRIMARY"|"GOOGLE_FALLBACK"|"OFFLINE_LOCAL"|"RECONCILING";scope?:"STAGING_SHADOW"|"PRODUCTION";service_generation?:string;increment_epoch?:boolean;reason?:string;initiated_by?:string;confirmation?:string}):Promise<Record<string,unknown>>{
  const before=await currentAuthority(env.DB),productionPromotion=(input.scope==="PRODUCTION"||before.scope==="PRODUCTION")&&input.mode==="SERVICE_PRIMARY"&&Boolean(input.increment_epoch);
  if(productionPromotion&&input.confirmation!=="OWNER_LOCKED_M2_CUTOVER")throw new CoreError("PRODUCTION_PROMOTION_CONFIRMATION_REQUIRED","PERMISSION",403);
  const after=await transitionAuthority(env.DB,input),at=nowIso();
  await env.DB.prepare(`INSERT INTO authority_transitions(from_epoch,to_epoch,from_mode,to_mode,from_generation,to_generation,reason,initiated_by,checkpoint_epoch,checkpoint_seq,validation_json,created_at)
    VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,'{}',?11)`).bind(before.authority_epoch,after.authority_epoch,before.mode,after.mode,before.service_generation,after.service_generation,String(input.reason||"UNSPECIFIED").slice(0,500),String(input.initiated_by||"M2_INTERNAL").slice(0,180),before.authority_epoch,before.authority_seq,at).run();
  return{ok:true,before,authority:after};
}

async function fallbackIngest(request:Request,env:Env):Promise<Response>{
  if(!await gasBridgeAuthorized(request,env))return apiError("GAS_BRIDGE_UNAUTHORIZED","AUTH",401);const b=await readJsonBody<{event_id:string;authority_epoch:number;authority_seq:number;service_generation:string;event:Record<string,unknown>;checksum:string}>(request),a=await currentAuthority(env.DB);
  if(!["GOOGLE_FALLBACK","RECONCILING"].includes(a.mode))return apiError("FALLBACK_INGEST_NOT_ALLOWED","CONFLICT",409,false,undefined,{mode:a.mode});
  await env.DB.prepare(`INSERT INTO fallback_event_inbox(event_id,authority_epoch,authority_seq,service_generation,event_json,checksum,source,ingest_status,received_at)
    VALUES(?1,?2,?3,?4,?5,?6,'GOOGLE_FALLBACK','PENDING',?7) ON CONFLICT(event_id) DO NOTHING`).bind(b.event_id,b.authority_epoch,b.authority_seq,b.service_generation,JSON.stringify(b.event),b.checksum,nowIso()).run();return json({ok:true,event_id:b.event_id});
}
async function drManifest(env:Env):Promise<Record<string,unknown>>{
  const a=await currentAuthority(env.DB),tables=["events","employees","attendance_sessions","labor_sessions"],counts:Record<string,number>={};for(const t of tables){const c=await env.DB.prepare(`SELECT COUNT(*) n FROM ${t}`).first<{n:number}>();counts[t]=c?.n??0;}
  const raw={authority_epoch:a.authority_epoch,authority_seq:a.authority_seq,service_generation:a.service_generation,event_count:counts.events??0,employee_count:counts.employees??0,attendance_count:counts.attendance_sessions??0,labor_count:counts.labor_sessions??0},checksum=await sha256Hex(JSON.stringify(raw)),manifestId=crypto.randomUUID(),at=nowIso();
  await env.DB.prepare("INSERT INTO dr_manifests(manifest_id,authority_epoch,authority_seq,service_generation,event_count,employee_count,attendance_count,labor_count,checksum,manifest_json,created_at) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)").bind(manifestId,a.authority_epoch,a.authority_seq,a.service_generation,raw.event_count,raw.employee_count,raw.attendance_count,raw.labor_count,checksum,JSON.stringify(raw),at).run();return{ok:true,manifest_id:manifestId,checksum,...raw,created_at:at};
}

async function internalTestAccount(request:Request,env:Env):Promise<Response>{
  if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);const b=await readJsonBody<{login_id:string;verifier:string;role?:"SUPERADMIN"|"ADMIN"|"USER"}>(request),login=String(b.login_id||"").trim(),verifier=String(b.verifier||"").trim();if(!login||!verifier)return apiError("TEST_ACCOUNT_FIELDS_REQUIRED","VALIDATION",400);const role=b.role??"SUPERADMIN";
  await env.DB.prepare(`INSERT INTO accounts(login_id,verifier,verifier_hash,role,display_name,position,email,status,source_row,source_checksum,is_shadow_test) VALUES(?1,?2,?3,?4,?1,?5,'','ACTIVE',0,'M1_SHADOW_TEST',1)
    ON CONFLICT(login_id) DO UPDATE SET verifier=excluded.verifier,verifier_hash=excluded.verifier_hash,role=excluded.role,display_name=excluded.display_name,position=excluded.position,status='ACTIVE',is_shadow_test=1`).bind(login,verifier,await sha256Hex(verifier),role,role.toLowerCase()).run();return json({ok:true,login_id:login,role});
}

async function route(request:Request,env:Env):Promise<Response>{
  const u=new URL(request.url),p=u.pathname,method=request.method.toUpperCase();
  if(p==="/health"&&method==="GET")return healthSnapshot(env);
  if(p==="/v1/capabilities"&&method==="GET")return json({ok:true,api_version:"v1",canonical_event_schema:1,auth:"PBKDF2_HMAC_SHA256_CHALLENGE",session_model:"SINGLE_ACTIVE_DEVICE_V1",realtime:"DURABLE_OBJECT_WEBSOCKET_HIBERNATION",realtime_protocol:"INVALIDATION_V1",delta:true,revision_namespaces:true,business_window:7,mutation_batch:true,offline_outbox:true,fcm_wake:true,import_engine:true,historical_corrections:true,legacy_adapter:true,authority_modes:["SERVICE_PRIMARY","GOOGLE_FALLBACK","OFFLINE_LOCAL","RECONCILING"],production_cutover:(await currentAuthority(env.DB)).scope==="PRODUCTION"});
  if(p==="/v1/authority"&&method==="GET")return json({ok:true,authority:await currentAuthority(env.DB)});
  if(p==="/v1/auth/challenge"&&method==="POST"){const b=await readJsonBody<{login_id:string}>(request);return json(await createChallenge(env.DB,String(b.login_id||"").trim()));}
  if(p==="/v1/auth/login"&&method==="POST"){const b=await readJsonBody<{login_id:string;challenge_id:string;proof:string;device_id:string;device_label?:string}>(request),out=await createSession(env.DB,env,b);return json(out,((out as {ok?:boolean}).ok===false)?401:200);}
  if(p==="/v1/auth/logout"&&method==="POST"){const a=await requireAuth(request,env);await logout(env.DB,a);return json({ok:true});}
  if(p==="/v1/mutations"&&method==="POST")return mutate(request,env);
  if(p==="/v1/mutations/batch"&&method==="POST")return mutateBatch(request,env);
  if(p==="/v1/corrections"&&method==="POST")return historicalCorrection(request,env);
  if(p==="/v1/legacy-mutations"&&method==="POST")return legacyMutation(request,env);
  if(p==="/v1/legacy-mutations/batch"&&method==="POST")return legacyMutationBatch(request,env);
  if(p==="/v1/delta"&&method==="GET"){await requireAuth(request,env);const epoch=Number(u.searchParams.get("authority_epoch")||"0"),after=Number(u.searchParams.get("after_seq")||"0"),limit=Number(u.searchParams.get("limit")||"500");return json({ok:true,...await delta(env.DB,epoch,after,limit)});}
  if(p==="/v1/sync/status"&&method==="GET")return syncStatusV2(request,env);
  if(p==="/v1/delta/day"&&method==="GET")return dayDeltaV2(request,env);
  if(p==="/v1/delta/master"&&method==="GET")return masterDeltaV2(request,env);
  if(p==="/v1/bootstrap"&&method==="GET")return bootstrapSnapshot(request,env);
  if(p==="/v1/realtime/ticket"&&method==="POST")return realtimeTicket(request,env);
  if(p==="/v1/realtime"&&method==="GET")return realtimeConnect(request,env);
  if(p==="/v1/push/register"&&method==="POST")return registerPushDevice(request,env);
  if(p==="/v1/push/revoke"&&method==="POST")return revokePushDevice(request,env);
  if(p==="/v1/import/schema"&&method==="GET")return importSchema(request,env);
  if(p==="/v1/import/batches"&&method==="POST")return importStart(request,env);
  if(p==="/v1/import/history"&&method==="GET")return importHistory(request,env);
  const im=p.match(/^\/v1\/import\/batches\/([^/]+)\/(chunks|preview|commit|rollback)$/);if(im){const id=decodeURIComponent(im[1]!),op=im[2];if(op==="chunks"&&(method==="POST"||method==="PUT"))return importChunk(request,env,id);if(op==="preview"&&method==="POST")return importPreview(request,env,id);if(op==="commit"&&method==="POST")return importCommitAtomic(request,env,id);if(op==="rollback"&&method==="POST")return importRollbackAtomic(request,env,id);}

  if(p==="/internal/legacy-bridge"&&method==="POST")return gasLegacyBridge(request,env);
  if(p==="/internal/fallback/ingest"&&method==="POST")return fallbackIngest(request,env);
  if(p==="/internal/bootstrap-google"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);await ensureConfiguredGeneration(env);return json(await bootstrapFromGoogle(env.DB,env));}
  if(p==="/internal/replicate"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);return json(await replicatePending(env.DB,env));}
  if(p==="/internal/push/flush"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);return json({ok:true,...await flushPushOutbox(env.DB,env)});}
  if(p==="/internal/test-account"&&method==="POST")return internalTestAccount(request,env);
  if(p==="/internal/dr/manifest"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);return json(await drManifest(env));}
  if(p==="/internal/authority/transition"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);const b=await readJsonBody<{expected_epoch:number;mode:"SERVICE_PRIMARY"|"GOOGLE_FALLBACK"|"OFFLINE_LOCAL"|"RECONCILING";scope?:"STAGING_SHADOW"|"PRODUCTION";service_generation?:string;increment_epoch?:boolean;reason?:string;initiated_by?:string;confirmation?:string}>(request);return json(await transitionWithAudit(env,b));}
  return apiError("NOT_FOUND","VALIDATION",404);
}

export default {
  async fetch(request:Request,env:Env):Promise<Response>{const started=Date.now(),requestId=request.headers.get("x-request-id")?.slice(0,100)||crypto.randomUUID(),path=new URL(request.url).pathname;try{const response=await route(request,env);if(response.status!==101)response.headers.set("x-request-id",requestId);console.log(JSON.stringify({level:"info",kind:"request_complete",request_id:requestId,route:path,method:request.method,status:response.status,wall_ms:Date.now()-started}));return response;}catch(e){if(e instanceof CoreError)return apiError(e.code,e.errorClass,e.status,e.retryable,undefined,e.conflict);console.log(JSON.stringify({level:"error",kind:"request_failed",request_id:requestId,route:path,method:request.method,wall_ms:Date.now()-started,error_class:"INTERNAL",error:String(e).slice(0,240)}));return apiError("INTERNAL_ERROR","INTERNAL",500,true);}},
  async scheduled(_controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{ctx.waitUntil(Promise.all([replicatePending(env.DB,env),flushPushOutbox(env.DB,env)]).then(()=>undefined).catch(e=>console.log(JSON.stringify({level:"error",kind:"scheduled_background_failed",error:String(e).slice(0,240)}))));},
} satisfies ExportedHandler<Env>;
