import { authenticate, createChallenge, createSession, internalAuthorized, logout } from "./auth";
import { bootstrapFromGoogle } from "./bootstrap";
import { commitMutation, CoreError, currentAuthority, delta, transitionAuthority } from "./core";
import { replicatePending, replicationHealth } from "./replication";
import { RealtimeHub } from "./realtime";
import { apiError, json, nowIso, readJsonBody, sha256Hex } from "./util";
import type { CanonicalMutationRequest } from "./domain";

export { RealtimeHub };

async function ensureConfiguredGeneration(env:Env):Promise<void>{
  const a=await env.DB.prepare("SELECT service_generation FROM authority_state WHERE singleton_id=1").first<{service_generation:string}>();
  if(a?.service_generation==="UNCONFIGURED")await env.DB.prepare("UPDATE authority_state SET service_generation=?1,updated_at=?2 WHERE singleton_id=1 AND service_generation='UNCONFIGURED'").bind(env.SERVICE_GENERATION,nowIso()).run();
}

async function requireAuth(request:Request,env:Env){const a=await authenticate(env.DB,env,request);if(!a)throw new CoreError("UNAUTHORIZED","AUTH",401);return a;}
function eventPublic(e:Record<string,unknown>):Record<string,unknown>{return e;}

async function realtimeTicket(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),u=new URL(request.url),date=u.searchParams.get("business_date")||"";if(!/^\d{4}-\d{2}-\d{2}$/.test(date))return apiError("BUSINESS_DATE_INVALID","VALIDATION",400);
  const ticket=crypto.randomUUID(),expires=Date.now()+120_000;await env.DB.prepare("DELETE FROM realtime_tickets WHERE expires_at<?1").bind(Date.now()).run();await env.DB.prepare("INSERT INTO realtime_tickets(ticket_id,login_id,device_id,business_date,expires_at,created_at) VALUES(?1,?2,?3,?4,?5,?6)").bind(ticket,auth.login_id,auth.device_id,date,expires,nowIso()).run();return json({ok:true,ticket,expires_at:expires});
}

async function realtimeConnect(request:Request,env:Env):Promise<Response>{
  if(request.headers.get("Upgrade")!=="websocket")return apiError("WEBSOCKET_REQUIRED","VALIDATION",426);
  const u=new URL(request.url),ticket=u.searchParams.get("ticket")||"";const row=await env.DB.prepare("SELECT ticket_id,login_id,device_id,business_date,expires_at FROM realtime_tickets WHERE ticket_id=?1").bind(ticket).first<{ticket_id:string;login_id:string;device_id:string;business_date:string;expires_at:number}>();
  if(!row||row.expires_at<Date.now())return apiError("REALTIME_TICKET_INVALID","AUTH",401);await env.DB.prepare("DELETE FROM realtime_tickets WHERE ticket_id=?1").bind(ticket).run();
  const hub=env.REALTIME_HUB.getByName(`business:${row.business_date}`);const target=new URL(request.url);target.searchParams.set("device_id",row.device_id);target.searchParams.set("login_id",row.login_id);return hub.fetch(new Request(target,request));
}

async function bootstrapSnapshot(request:Request,env:Env):Promise<Response>{
  await requireAuth(request,env);const u=new URL(request.url),date=u.searchParams.get("business_date")||"";
  const employees=await env.DB.prepare("SELECT mnv,full_name,phone,main_position,supplier,department,site,warehouse,start_date,note FROM employees ORDER BY mnv").all();
  const resources=await env.DB.prepare("SELECT resource_type,resource_id,status_label,available,metadata_json FROM resources ORDER BY resource_type,resource_id").all();
  const catalogs=await env.DB.prepare("SELECT namespace,ordinal,value FROM catalog_values ORDER BY namespace,ordinal").all();
  const sessions=date?await env.DB.prepare("SELECT * FROM attendance_sessions WHERE business_date=?1 ORDER BY mnv").bind(date).all():{results:[]};
  const labor=date?await env.DB.prepare("SELECT * FROM labor_sessions WHERE business_date=?1 ORDER BY mnv,start_at").bind(date).all():{results:[]};
  const a=await currentAuthority(env.DB);return json({ok:true,authority:a,employees:employees.results??[],resources:resources.results??[],catalogs:catalogs.results??[],attendance:sessions.results??[],labor:labor.results??[]});
}

async function syncStatus(request:Request,env:Env):Promise<Response>{
  await requireAuth(request,env);const a=await currentAuthority(env.DB),rep=await replicationHealth(env.DB),dates=await env.DB.prepare("SELECT business_date,sequence_no FROM business_dates ORDER BY sequence_no DESC LIMIT 45").all();
  return json({ok:true,authority:a,server_seq:a.authority_seq,service_generation:a.service_generation,business_dates:dates.results??[],replication:rep,realtime:true,delta_endpoint:"/v1/delta",ws_endpoint:"/v1/realtime"});
}

async function mutate(request:Request,env:Env):Promise<Response>{
  const auth=await requireAuth(request,env),body=await readJsonBody<CanonicalMutationRequest>(request);const result=await commitMutation(env.DB,env,auth,body);const e=result.event;
  const hub=env.REALTIME_HUB.getByName(`business:${e.business_date}`);let delivered=0;try{delivered=await hub.broadcast({event_id:e.event_id,event_type:e.event_type,entity_type:e.entity_type,entity_id:e.entity_id,business_date:e.business_date,authority_epoch:e.authority_epoch,authority_seq:e.authority_seq,service_generation:e.service_generation,new_version:e.new_version});}catch(err){console.log(JSON.stringify({level:"warn",kind:"realtime_broadcast_failed",event_id:e.event_id,error:String(err)}));}
  return json({ok:true,duplicate:result.duplicate,event:eventPublic(e as unknown as Record<string,unknown>),realtime_delivered:delivered},result.duplicate?200:201);
}

async function internalTestAccount(request:Request,env:Env):Promise<Response>{
  if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);const b=await readJsonBody<{login_id:string;verifier:string;role?:"SUPERADMIN"|"ADMIN"|"USER"}>(request);const login=String(b.login_id||"").trim(),verifier=String(b.verifier||"").trim();if(!login||!verifier)return apiError("TEST_ACCOUNT_FIELDS_REQUIRED","VALIDATION",400);const role=b.role??"SUPERADMIN";
  await env.DB.prepare(`INSERT INTO accounts(login_id,verifier,verifier_hash,role,display_name,position,email,status,source_row,source_checksum,is_shadow_test) VALUES(?1,?2,?3,?4,?1,?5,'','ACTIVE',0,'M1_SHADOW_TEST',1)
    ON CONFLICT(login_id) DO UPDATE SET verifier=excluded.verifier,verifier_hash=excluded.verifier_hash,role=excluded.role,display_name=excluded.display_name,position=excluded.position,status='ACTIVE',is_shadow_test=1`).bind(login,verifier,await sha256Hex(verifier),role,role.toLowerCase()).run();return json({ok:true,login_id:login,role});
}

async function route(request:Request,env:Env):Promise<Response>{
  const u=new URL(request.url),p=u.pathname,method=request.method.toUpperCase();
  if(p==="/health"&&method==="GET"){await ensureConfiguredGeneration(env);const a=await currentAuthority(env.DB),rep=await replicationHealth(env.DB);return json({ok:true,service:"pick-pack-1291-service",environment:a.scope==="STAGING_SHADOW"?"staging-shadow":"production",generation:env.SERVICE_GENERATION,authority:a,replication:rep});}
  if(p==="/v1/capabilities"&&method==="GET")return json({ok:true,api_version:"v1",canonical_event_schema:1,auth:"PBKDF2_HMAC_SHA256_CHALLENGE",session_model:"SINGLE_ACTIVE_DEVICE_V1",realtime:"DURABLE_OBJECT_WEBSOCKET_HIBERNATION",delta:true,offline_outbox:true,authority_modes:["SERVICE_PRIMARY","GOOGLE_FALLBACK","OFFLINE_LOCAL","RECONCILING"],production_cutover:(await currentAuthority(env.DB)).scope==="PRODUCTION"});
  if(p==="/v1/authority"&&method==="GET")return json({ok:true,authority:await currentAuthority(env.DB)});
  if(p==="/v1/auth/challenge"&&method==="POST"){const b=await readJsonBody<{login_id:string}>(request);return json(await createChallenge(env.DB,String(b.login_id||"").trim()));}
  if(p==="/v1/auth/login"&&method==="POST"){const b=await readJsonBody<{login_id:string;challenge_id:string;proof:string;device_id:string;device_label?:string}>(request);const out=await createSession(env.DB,env,b);return json(out,((out as {ok?:boolean}).ok===false)?401:200);}
  if(p==="/v1/auth/logout"&&method==="POST"){const a=await requireAuth(request,env);await logout(env.DB,a);return json({ok:true});}
  if(p==="/v1/mutations"&&method==="POST")return mutate(request,env);
  if(p==="/v1/delta"&&method==="GET"){await requireAuth(request,env);const epoch=Number(u.searchParams.get("authority_epoch")||"0"),after=Number(u.searchParams.get("after_seq")||"0"),limit=Number(u.searchParams.get("limit")||"500");return json({ok:true,...await delta(env.DB,epoch,after,limit)});}
  if(p==="/v1/sync/status"&&method==="GET")return syncStatus(request,env);
  if(p==="/v1/bootstrap"&&method==="GET")return bootstrapSnapshot(request,env);
  if(p==="/v1/realtime/ticket"&&method==="POST")return realtimeTicket(request,env);
  if(p==="/v1/realtime"&&method==="GET")return realtimeConnect(request,env);
  if(p==="/internal/bootstrap-google"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);await ensureConfiguredGeneration(env);return json(await bootstrapFromGoogle(env.DB,env));}
  if(p==="/internal/replicate"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);return json(await replicatePending(env.DB,env));}
  if(p==="/internal/test-account"&&method==="POST")return internalTestAccount(request,env);
  if(p==="/internal/authority/transition"&&method==="POST"){if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);const b=await readJsonBody<{expected_epoch:number;mode:"SERVICE_PRIMARY"|"GOOGLE_FALLBACK"|"OFFLINE_LOCAL"|"RECONCILING";scope?:"STAGING_SHADOW"|"PRODUCTION";service_generation?:string;increment_epoch?:boolean}>(request);return json({ok:true,authority:await transitionAuthority(env.DB,b)});}
  return apiError("NOT_FOUND","VALIDATION",404);
}

export default {
  async fetch(request:Request,env:Env):Promise<Response>{try{return await route(request,env);}catch(e){if(e instanceof CoreError)return apiError(e.code,e.errorClass,e.status,e.retryable,undefined,e.conflict);console.log(JSON.stringify({level:"error",kind:"request_failed",path:new URL(request.url).pathname,error:String(e)}));return apiError("INTERNAL_ERROR","INTERNAL",500,true);}},
  async scheduled(_controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{ctx.waitUntil(replicatePending(env.DB,env).then(()=>undefined).catch(e=>console.log(JSON.stringify({level:"error",kind:"scheduled_replication_failed",error:String(e)}))));},
} satisfies ExportedHandler<Env>;
