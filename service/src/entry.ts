import base, { RealtimeHub } from "./index";
import { authenticate, internalAuthorized } from "./auth";
import { compatBootstrap, compatDay, compatSyncStatus } from "./compat";
import { failbackFromFallbackInbox, reconciliationLocked } from "./recovery";
import { apiError, json, readJsonBody } from "./util";

export { RealtimeHub };

async function legacySync(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);
  const body=await readJsonBody<{action:string;business_date?:string;dates?:unknown[]}>(request),action=String(body.action||"");
  if(action==="sync_status")return json(await compatSyncStatus(env.DB));
  if(action==="sync_day")return json({ok:true,sync_engine:"S15_LOCAL_FIRST_45D_SERVICE",day:await compatDay(env.DB,String(body.business_date||""))});
  if(action==="sync_bootstrap")return json(await compatBootstrap(env.DB,body.dates));
  return apiError("LEGACY_SYNC_ACTION_UNSUPPORTED","VALIDATION",400);
}

async function recoveryFailback(request:Request,env:Env):Promise<Response>{
  if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);
  const input=await readJsonBody<{fallback_epoch:number;expected_service_epoch:number;confirmation:string;initiated_by?:string}>(request);
  try{return json(await failbackFromFallbackInbox(env.DB,env,input));}catch(e){console.log(JSON.stringify({level:"error",kind:"failback_failed",error:String(e)}));return apiError("FAILBACK_FAILED","INTEGRITY",409,false,String(e).slice(0,500));}
}

export default {
  async fetch(request:Request,env:Env,_ctx:ExecutionContext):Promise<Response>{
    const u=new URL(request.url),path=u.pathname;
    if(path==="/internal/recovery/failback"&&request.method==="POST")return recoveryFailback(request,env);
    if(path==="/v1/legacy-sync"&&request.method==="POST"){
      try{return await legacySync(request,env);}catch(e){console.log(JSON.stringify({level:"error",kind:"legacy_sync_failed",error:String(e)}));return apiError("LEGACY_SYNC_FAILED","INTERNAL",500,true);}
    }
    if(await reconciliationLocked(env.DB)){
      if(path==="/v1/mutations"||path==="/v1/legacy-mutations"||path==="/internal/legacy-bridge")return apiError("RECONCILING_RETRY","CONFLICT",409,true);
    }
    return base.fetch(request,env);
  },
  async scheduled(controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{return base.scheduled(controller,env,ctx);},
} satisfies ExportedHandler<Env>;
