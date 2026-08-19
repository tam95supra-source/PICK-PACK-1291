import entry, { RealtimeHub } from "./entry_hotfix";
import { internalAuthorized } from "./auth";
import { ensureBusinessDateFromRequest } from "./business_date";
import { currentAuthority } from "./core";
import { resumeFailbackFromFallbackInbox } from "./recovery";
import { apiError, constantTimeEqual, json, readJsonBody, sha256Hex } from "./util";

export { RealtimeHub };

async function gasBridgeAuthorized(request:Request,env:Env):Promise<boolean>{
  const supplied=request.headers.get("x-gas-bridge-secret")||"";if(!supplied)return false;
  return constantTimeEqual(await sha256Hex(supplied),await sha256Hex(env.GAS_BRIDGE_SHARED_SECRET));
}

async function resumeFailback(request:Request,env:Env):Promise<Response>{
  if(!await internalAuthorized(request,env))return apiError("INTERNAL_UNAUTHORIZED","AUTH",401);
  const input=await readJsonBody<{fallback_epoch:number;confirmation:string;initiated_by?:string}>(request);
  try{return json(await resumeFailbackFromFallbackInbox(env.DB,env,input));}
  catch(e){console.log(JSON.stringify({level:"error",kind:"failback_resume_failed",error:String(e)}));return apiError("FAILBACK_RESUME_FAILED","INTEGRITY",409,false,String(e).slice(0,500));}
}

export default {
  async fetch(request:Request,env:Env,ctx:ExecutionContext):Promise<Response>{
    const path=new URL(request.url).pathname;
    if(path==="/internal/recovery/failback-resume"&&request.method==="POST")return resumeFailback(request,env);
    if(path==="/internal/gas-bridge-probe"){
      if(!await gasBridgeAuthorized(request,env))return apiError("GAS_BRIDGE_UNAUTHORIZED","AUTH",401);
      return json({ok:true,authority:await currentAuthority(env.DB),service_generation:env.SERVICE_GENERATION});
    }
    if(request.method==="POST"&&["/v1/mutations","/v1/legacy-mutations","/internal/legacy-bridge"].includes(path)){
      await ensureBusinessDateFromRequest(env.DB,request);
    }
    return entry.fetch(request,env,ctx);
  },
  async scheduled(controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{return entry.scheduled(controller,env,ctx);},
} satisfies ExportedHandler<Env>;
