import base, { RealtimeHub } from "./index";
import { authenticate, internalAuthorized } from "./auth";
import { bootstrapGoogleStart, bootstrapGoogleStatus, bootstrapGoogleStep } from "./bootstrap_resumable";
import { bootstrapResourceProjectionStep } from "./bootstrap_resources";
import { compatBootstrap, compatDay } from "./compat";
import { currentAuthority, sanitizeSensitive } from "./core";
import { rebuildGoogleStagingFromD1 } from "./dr";
import { importParseXlsx, importTemplateXlsx } from "./import_xlsx";
import { failbackFromFallbackInbox, reconciliationLocked } from "./recovery";
import { resumeFailbackWithLegacyCompat } from "./recovery_resume_compat";
import { apiError, constantTimeEqual, json, nowIso, readJsonBody, sha256Hex } from "./util";

export { RealtimeHub };

interface ClientSyncRow{
  business_date:string;sequence_no:number;max_seq:number|null;
  authority_epoch:number;authority_seq:number;mode:string;scope:string;service_generation:string;updated_at:string;
  server_retention_floor:string|null;projection_pending:number|null;master_revision:number|null;
}

async function m2ClientSyncStatus(db:D1Database):Promise<Record<string,unknown>>{
  const q=`WITH recent AS (
      SELECT business_date,sequence_no FROM business_dates ORDER BY sequence_no DESC LIMIT 7
    ), rev AS (
      SELECT recent.business_date,recent.sequence_no,MAX(COALESCE(events.authority_seq,0)) AS max_seq
      FROM recent LEFT JOIN events ON events.business_date=recent.business_date
      GROUP BY recent.business_date,recent.sequence_no
    ), meta AS (
      SELECT
        (SELECT business_date FROM business_dates ORDER BY sequence_no ASC LIMIT 1) AS server_retention_floor,
        COALESCE((SELECT pending_count FROM replication_status WHERE singleton_id=1),0) AS projection_pending,
        COALESCE((SELECT MAX(source_row) FROM employees),0) AS master_revision
    )
    SELECT rev.business_date,rev.sequence_no,rev.max_seq,
      a.authority_epoch,a.authority_seq,a.mode,a.scope,a.service_generation,a.updated_at,
      meta.server_retention_floor,meta.projection_pending,meta.master_revision
    FROM rev CROSS JOIN authority_state a CROSS JOIN meta
    WHERE a.singleton_id=1 ORDER BY rev.sequence_no DESC`;
  const result=await db.prepare(q).all<ClientSyncRow>(),rows=result.results??[],first=rows[0];
  if(!first)throw new Error("SYNC_STATUS_EMPTY");
  const dayRevisions:Record<string,number>={};for(const r of rows)dayRevisions[r.business_date]=Math.max(1,Number(r.max_seq??0));
  const authority={authority_epoch:first.authority_epoch,authority_seq:first.authority_seq,mode:first.mode,scope:first.scope,service_generation:first.service_generation,updated_at:first.updated_at};
  return{
    ok:true,business_date:first.business_date,server_seq:first.authority_seq,master_revision:Number(first.master_revision??0),last_event_at:first.updated_at,
    projection_pending:Number(first.projection_pending??0),mode:"APP_SERVICE_D1",sync_engine:"M2_SERVICE_BUSINESS_WINDOW_7",
    retention_floor:rows[rows.length-1]?.business_date??first.business_date,server_retention_floor:first.server_retention_floor??rows[rows.length-1]?.business_date??first.business_date,
    retention_epoch:first.authority_epoch,day_revisions:dayRevisions,authority,service_generation:first.service_generation,
    service_telemetry:{db_duration_ms:result.meta.duration,db_rows_read:result.meta.rows_read,served_by_region:result.meta.served_by_region??"",served_by_primary:result.meta.served_by_primary??false}
  };
}

async function legacySync(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);
  const body=await readJsonBody<{action:string;business_date?:string;dates?:unknown[]}>(request),action=String(body.action||"");
  if(action==="sync_status")return json(await m2ClientSyncStatus(env.DB));
  if(action==="sync_day")return json({ok:true,sync_engine:"M2_SERVICE_BUSINESS_WINDOW_7",day:await compatDay(env.DB,String(body.business_date||""))});
  if(action==="sync_bootstrap")return json(await compatBootstrap(env.DB,body.dates));
  return apiError("LEGACY_SYNC_ACTION_UNSUPPORTED","VALIDATION",400);
}

async function recoveryFailback(request:Request,env:Env):Promise<Response>{
  if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);
  const input=await readJsonBody<{fallback_epoch:number;expected_service_epoch:number;confirmation:string;initiated_by?:string}>(request);
  try{return json(await failbackFromFallbackInbox(env.DB,env,input));}catch(e){console.log(JSON.stringify({level:"error",kind:"failback_failed",error:String(e)}));return apiError("FAILBACK_FAILED","INTEGRITY",409,false,String(e).slice(0,500));}
}
async function recoveryResume(request:Request,env:Env):Promise<Response>{
  if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);
  const input=await readJsonBody<{fallback_epoch:number;confirmation:string;initiated_by?:string}>(request);
  try{return json(await resumeFailbackWithLegacyCompat(env.DB,env,input));}catch(e){console.log(JSON.stringify({level:"error",kind:"failback_resume_failed",error:String(e)}));return apiError("FAILBACK_RESUME_FAILED","INTEGRITY",409,false,String(e).slice(0,500));}
}
async function drRebuildGoogle(request:Request,env:Env):Promise<Response>{
  if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);
  try{return json(await rebuildGoogleStagingFromD1(env.DB,env));}catch(e){console.log(JSON.stringify({level:"error",kind:"dr_google_rebuild_failed",error:String(e)}));return apiError("DR_GOOGLE_REBUILD_FAILED","INTEGRITY",409,false,String(e).slice(0,500));}
}

async function resumableBootstrap(request:Request,env:Env,action:"start"|"step"|"status"):Promise<Response>{
  if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);
  try{
    if(action==="start")return json(await bootstrapGoogleStart(env.DB,env));
    const body=await readJsonBody<{run_id?:string}>(request),runId=String(body.run_id||"").trim();
    if(action==="step"){
      if(!runId)return apiError("BOOTSTRAP_RUN_ID_REQUIRED","VALIDATION",400);
      const status=await bootstrapGoogleStatus(env.DB,runId) as {state?:{phase?:string}};
      if(status.state?.phase==="RESOURCES")return json(await bootstrapResourceProjectionStep(env.DB,runId));
      return json(await bootstrapGoogleStep(env.DB,env,runId));
    }
    return json(await bootstrapGoogleStatus(env.DB,runId||undefined));
  }catch(e){console.log(JSON.stringify({level:"error",kind:"resumable_bootstrap_failed",action,error:String(e)}));return apiError("BOOTSTRAP_RESUMABLE_FAILED","INTERNAL",500,true,String(e).slice(0,500));}
}

async function gasBridgeAuthorized(request:Request,env:Env):Promise<boolean>{
  const supplied=request.headers.get("x-gas-bridge-secret")||"";if(!supplied)return false;
  return constantTimeEqual(await sha256Hex(supplied),await sha256Hex(env.GAS_BRIDGE_SHARED_SECRET));
}
async function fallbackIngestFenced(request:Request,env:Env):Promise<Response>{
  if(!await gasBridgeAuthorized(request,env))return apiError("GAS_BRIDGE_UNAUTHORIZED","AUTH",401);
  const body=await readJsonBody<{event_id:string;authority_epoch:number;authority_seq:number;service_generation:string;event:Record<string,unknown>;checksum:string}>(request);
  const eventId=String(body.event_id||"").trim(),generation=String(body.service_generation||"").trim(),checksum=String(body.checksum||"").trim();
  if(!eventId||!generation||!checksum||!Number.isInteger(body.authority_epoch)||!Number.isInteger(body.authority_seq)||body.authority_seq<1||!body.event||typeof body.event!=="object")return apiError("FALLBACK_INGEST_INVALID","VALIDATION",400);
  const e=body.event as Record<string,unknown>,sourceRaw=[eventId,body.authority_epoch,body.authority_seq,generation,String(e.action||""),String(e.business_date||""),String(e.actor||""),String(e.role||""),String(e.device_id||""),String(e.occurred_at||""),String(e.payload_json||"")].join("|");
  if(await sha256Hex(sourceRaw)!==checksum)return apiError("FALLBACK_SOURCE_CHECKSUM_MISMATCH","INTEGRITY",409);
  let cleanPayload:unknown={};try{cleanPayload=sanitizeSensitive(JSON.parse(String(e.payload_json||"{}")));}catch{cleanPayload={};}
  const cleanEvent={...e,payload_json:JSON.stringify(cleanPayload)},cleanJson=JSON.stringify(cleanEvent),sanitizedChecksum=await sha256Hex(cleanJson);
  const a=await currentAuthority(env.DB),futureFallback=a.mode==="SERVICE_PRIMARY"&&body.authority_epoch===a.authority_epoch+1,currentFallback=["GOOGLE_FALLBACK","RECONCILING"].includes(a.mode)&&body.authority_epoch===a.authority_epoch;
  if(!futureFallback&&!currentFallback)return apiError("FALLBACK_EPOCH_NOT_ACCEPTABLE","CONFLICT",409,false,undefined,{current_epoch:a.authority_epoch,current_mode:a.mode,incoming_epoch:body.authority_epoch});
  const existing=await env.DB.prepare("SELECT authority_epoch,authority_seq,checksum FROM fallback_event_inbox WHERE event_id=?1").bind(eventId).first<{authority_epoch:number;authority_seq:number;checksum:string}>();
  if(existing){if(existing.authority_epoch!==body.authority_epoch||existing.authority_seq!==body.authority_seq||existing.checksum!==checksum)return apiError("FALLBACK_EVENT_ID_COLLISION","INTEGRITY",409);return json({ok:true,event_id:eventId,duplicate:true,authority_epoch:body.authority_epoch,authority_seq:body.authority_seq});}
  const seqCollision=await env.DB.prepare("SELECT event_id,checksum FROM fallback_event_inbox WHERE authority_epoch=?1 AND authority_seq=?2").bind(body.authority_epoch,body.authority_seq).first<{event_id:string;checksum:string}>();
  if(seqCollision)return apiError("FALLBACK_SEQUENCE_COLLISION","INTEGRITY",409,false,undefined,{existing_event_id:seqCollision.event_id,incoming_event_id:eventId,authority_epoch:body.authority_epoch,authority_seq:body.authority_seq});
  await env.DB.prepare(`INSERT INTO fallback_event_inbox(event_id,authority_epoch,authority_seq,service_generation,event_json,checksum,source,ingest_status,received_at,source_checksum_verified,sanitized_checksum)
    VALUES(?1,?2,?3,?4,?5,?6,'GOOGLE_FALLBACK','PENDING',?7,1,?8)`).bind(eventId,body.authority_epoch,body.authority_seq,generation,cleanJson,checksum,nowIso(),sanitizedChecksum).run();
  return json({ok:true,event_id:eventId,duplicate:false,staged_for_failback:true,authority_epoch:body.authority_epoch,authority_seq:body.authority_seq});
}

export default {
  async fetch(request:Request,env:Env,_ctx:ExecutionContext):Promise<Response>{
    const u=new URL(request.url),path=u.pathname;
    if(path==="/internal/bootstrap-google/start"&&request.method==="POST")return resumableBootstrap(request,env,"start");
    if(path==="/internal/bootstrap-google/step"&&request.method==="POST")return resumableBootstrap(request,env,"step");
    if(path==="/internal/bootstrap-google/status"&&request.method==="POST")return resumableBootstrap(request,env,"status");
    if(path==="/internal/fallback/ingest"&&request.method==="POST")return fallbackIngestFenced(request,env);
    if(path==="/internal/recovery/failback"&&request.method==="POST")return recoveryFailback(request,env);
    if(path==="/internal/recovery/failback-resume"&&request.method==="POST")return recoveryResume(request,env);
    if(path==="/internal/dr/rebuild-google-staging"&&request.method==="POST")return drRebuildGoogle(request,env);
    if(path==="/v1/import/template"&&request.method==="GET")return importTemplateXlsx(request,env);
    if(path==="/v1/import/xlsx/parse"&&request.method==="POST")return importParseXlsx(request,env);
    if(path==="/v1/legacy-sync"&&request.method==="POST"){
      try{return await legacySync(request,env);}catch(e){console.log(JSON.stringify({level:"error",kind:"legacy_sync_failed",error:String(e)}));return apiError("LEGACY_SYNC_FAILED","INTERNAL",500,true);}
    }
    if(await reconciliationLocked(env.DB)){
      if(path==="/v1/mutations"||path==="/v1/mutations/batch"||path==="/v1/legacy-mutations"||path==="/v1/legacy-mutations/batch"||path==="/internal/legacy-bridge")return apiError("RECONCILING_RETRY","CONFLICT",409,true);
    }
    return base.fetch(request,env);
  },
  async scheduled(controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{return base.scheduled(controller,env,ctx);},
} satisfies ExportedHandler<Env>;
