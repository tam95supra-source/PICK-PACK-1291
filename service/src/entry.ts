import base, { RealtimeHub } from "./index";
import { authenticate } from "./auth";
import { compatBootstrap, compatDay, compatSyncStatus } from "./compat";
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

export default {
  async fetch(request:Request,env:Env,ctx:ExecutionContext):Promise<Response>{
    const u=new URL(request.url);
    if(u.pathname==="/v1/legacy-sync"&&request.method==="POST"){
      try{return await legacySync(request,env);}catch(e){console.log(JSON.stringify({level:"error",kind:"legacy_sync_failed",error:String(e)}));return apiError("LEGACY_SYNC_FAILED","INTERNAL",500,true);}
    }
    return base.fetch(request,env,ctx);
  },
  async scheduled(controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{return base.scheduled(controller,env,ctx);},
} satisfies ExportedHandler<Env>;
